from __future__ import annotations

import io
import json
import os
import asyncio
import platform
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from ai import (
    generate_faqs,
    generate_multilingual_narrations,
    generate_step_narration,
    get_client,
    translate_narration,
    validate_step_alignment,
)
from crawler import crawl_flow, map_intent_to_flows
from models import (
    DemoStep,
    ExportLinkRequest,
    ExportLinkResponse,
    GenerateRequest,
    GenerateResponse,
    HighlightBox,
    LiveStepValidationResponse,
    TranslationRequest,
    TranslationResponse,
)


if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SHARED_DIR = BASE_DIR / "shared"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
SHARED_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="DemoGen API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")

sessions: Dict[str, dict] = {}
NARRATION_CONCURRENCY = max(1, int(os.getenv("NARRATION_CONCURRENCY", "4")))


def _safe_highlight(raw: dict | None) -> HighlightBox:
    raw = raw or {}
    return HighlightBox(
        x=float(raw.get("x", 25)),
        y=float(raw.get("y", 25)),
        width=float(raw.get("width", 50)),
        height=float(raw.get("height", 50)),
    )


def _image_signature(image_path: str) -> list[int]:
    with Image.open(image_path) as image:
        grayscale = ImageOps.grayscale(image).resize((24, 16))
        return list(grayscale.getdata())


def _signature_distance(first: list[int], second: list[int]) -> float:
    if not first or not second or len(first) != len(second):
        return 999.0
    total = sum(abs(a - b) for a, b in zip(first, second))
    return total / len(first)


def _select_relevant_captures(captured_steps: List[dict], flow: List[dict]) -> List[dict]:
    if not captured_steps:
        return []

    distinct_steps: List[dict] = []
    last_signature: list[int] | None = None
    for step in captured_steps:
        try:
            signature = _image_signature(step["screenshot_path"])
        except Exception:
            signature = []
        if last_signature is None or _signature_distance(signature, last_signature) > 7.5:
            distinct_steps.append({**step, "_signature": signature})
            last_signature = signature

    if not distinct_steps:
        distinct_steps = captured_steps[:]

    target_count = len(flow) if flow else min(6, len(distinct_steps))
    target_count = max(1, min(target_count, len(distinct_steps)))

    if len(distinct_steps) == target_count:
        selected_steps = distinct_steps
    elif target_count == 1:
        selected_steps = [distinct_steps[len(distinct_steps) // 2]]
    else:
        indices = []
        for idx in range(target_count):
            candidate = round(idx * (len(distinct_steps) - 1) / (target_count - 1))
            if candidate not in indices:
                indices.append(candidate)
        while len(indices) < target_count:
            indices.append(min(len(distinct_steps) - 1, indices[-1] + 1 if indices else 0))
        selected_steps = [distinct_steps[index] for index in indices[:target_count]]

    final_steps = []
    for idx, captured in enumerate(selected_steps, start=1):
        flow_step = flow[min(idx - 1, len(flow) - 1)] if flow else {}
        final_steps.append(
            {
                **captured,
                "step_number": idx,
                "url": flow_step.get("url", captured.get("url", "")),
                "action": flow_step.get("action", captured.get("action", f"Review captured moment {idx}")),
                "expected_elements": flow_step.get("expected_elements", captured.get("expected_elements", [])),
                "step_purpose": flow_step.get("step_purpose", captured.get("step_purpose", "Explain this important moment in the flow.")),
            }
        )
    return final_steps


async def _build_generate_response(
    session_id: str,
    intent: str,
    persona: str,
    language: str,
    captured_steps: List[dict],
    client,
) -> GenerateResponse:
    total_steps = len(captured_steps)
    semaphore = asyncio.Semaphore(NARRATION_CONCURRENCY)

    async def enrich_step(captured: dict) -> Tuple[int, DemoStep]:
        async with semaphore:
            narration_data = await asyncio.to_thread(
                generate_step_narration,
                captured.get("viewport_screenshot_path") or captured.get("screenshot_path") or "",
                captured.get("page_content", ""),
                captured.get("action", "Open page"),
                captured.get("step_purpose", "Progress toward user goal"),
                persona,
                captured.get("step_number", 1),
                max(total_steps, 1),
                client,
            )
            multilingual = await asyncio.to_thread(
                generate_multilingual_narrations,
                narration_data.get("narration", ""),
                client,
            )

        screenshot_filename = Path(captured.get("screenshot_path", "")).name
        step_model = DemoStep(
            step_number=captured.get("step_number", 1),
            screenshot_url=f"/screenshots/{screenshot_filename}" if screenshot_filename else "",
            narration=narration_data.get("narration") or "",
            api_call=narration_data.get("api_call"),
            code_snippet=narration_data.get("code_snippet"),
            language_narrations={"english": narration_data.get("narration") or "", **multilingual},
            highlight=_safe_highlight(narration_data.get("highlight")),
            page_title=captured.get("page_title", "Untitled page"),
            url=captured.get("url", ""),
            element_description=narration_data.get("element_description") or "Primary interactive area",
        )
        return step_model.step_number, step_model

    enriched_steps = await asyncio.gather(*(enrich_step(captured) for captured in captured_steps))
    enriched_steps.sort(key=lambda item: item[0])
    demo_steps = [step_model for _, step_model in enriched_steps]
    narration_summaries = [f"Step {step.step_number}: {step.narration}" for step in demo_steps]

    faqs = await asyncio.to_thread(generate_faqs, "\n".join(narration_summaries), intent, client)

    response = GenerateResponse(
        session_id=session_id,
        steps=demo_steps,
        faqs=faqs,
        total_steps=len(demo_steps),
        intent=intent,
        persona=persona,
    )

    sessions[session_id] = {
        "intent": intent,
        "persona": persona,
        "language": language,
        "steps": [step.model_dump() for step in demo_steps],
        "faqs": faqs,
    }
    return response


@app.post("/plan-flow")
async def plan_flow(payload: GenerateRequest):
    try:
        intent = payload.intent.strip()
        if not intent:
            raise HTTPException(status_code=400, detail="Intent cannot be empty")
        client = get_client()
        flow = await map_intent_to_flows(intent, client)
        return JSONResponse(content={"steps": flow, "intent": intent, "persona": payload.persona, "language": payload.language})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to plan flow: {exc}") from exc


@app.post("/translate", response_model=TranslationResponse)
async def translate_text(payload: TranslationRequest):
    try:
        cleaned_text = payload.text.strip()
        if not cleaned_text:
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        target_language = payload.target_language.strip().lower() or "english"
        client = get_client()
        translated_text = await asyncio.to_thread(translate_narration, cleaned_text, target_language, client)
        return TranslationResponse(target_language=target_language, translated_text=translated_text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to translate narration: {exc}") from exc


@app.post("/validate/live-step", response_model=LiveStepValidationResponse)
async def validate_live_step(
    intent: str = Form(...),
    step_number: int = Form(...),
    action: str = Form(...),
    step_purpose: str = Form(""),
    expected_elements: str = Form("[]"),
    screenshot: UploadFile = File(...),
):
    temp_path = SCREENSHOTS_DIR / f"validate_{uuid.uuid4().hex}.png"
    try:
        client = get_client()
        raw_expected = json.loads(expected_elements) if expected_elements else []
        if not isinstance(raw_expected, list):
            raw_expected = []

        temp_path.write_bytes(await screenshot.read())
        result = await asyncio.to_thread(
            validate_step_alignment,
            str(temp_path),
            intent.strip(),
            action,
            step_purpose,
            [str(item) for item in raw_expected],
            step_number,
            client,
        )
        return LiveStepValidationResponse(**result)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid expected elements payload: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to validate live step: {exc}") from exc
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


@app.post("/generate", response_model=GenerateResponse)
async def generate_demo(payload: GenerateRequest):
    try:
        intent = payload.intent.strip()
        if not intent:
            raise HTTPException(status_code=400, detail="Intent cannot be empty")

        persona = payload.persona.strip() or "developer"
        language = payload.language.strip() or "english"
        session_id = str(uuid.uuid4())

        client = get_client()
        flow = await map_intent_to_flows(intent, client)
        crawled_steps = await crawl_flow(flow, session_id)
        return await _build_generate_response(session_id, intent, persona, language, crawled_steps, client)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate demo: {exc}") from exc


@app.post("/generate/live-capture", response_model=GenerateResponse)
async def generate_live_capture_demo(
    intent: str = Form(...),
    persona: str = Form("developer"),
    language: str = Form("english"),
    captures: List[UploadFile] = File(...),
):
    try:
        cleaned_intent = intent.strip()
        if not cleaned_intent:
            raise HTTPException(status_code=400, detail="Intent cannot be empty")
        if not captures:
            raise HTTPException(status_code=400, detail="At least one capture is required")

        session_id = str(uuid.uuid4())
        client = get_client()
        flow = await map_intent_to_flows(cleaned_intent, client)

        raw_captures = []
        ordered_captures = sorted(captures, key=lambda upload: upload.filename or "")
        for idx, upload in enumerate(ordered_captures, start=1):
            suffix = Path(upload.filename or f"capture_{idx}.png").suffix or ".png"
            file_name = f"{session_id}_{idx}{suffix.lower()}"
            file_path = SCREENSHOTS_DIR / file_name
            file_bytes = await upload.read()
            file_path.write_bytes(file_bytes)
            raw_captures.append(
                {
                    "step_number": idx,
                    "screenshot_path": str(file_path),
                    "viewport_screenshot_path": str(file_path),
                    "url": "",
                    "page_title": Path(upload.filename or f"capture_{idx}.png").stem.replace("_", " ").replace("-", " ").title(),
                    "page_content": f"Live recording frame captured from the user's NeevCloud session. Source file: {upload.filename or file_name}",
                    "action": f"Captured moment {idx}",
                    "expected_elements": [],
                    "step_purpose": "Review this captured moment and determine whether it belongs in the final walkthrough.",
                    "is_login_page": False,
                }
            )

        selected_steps = _select_relevant_captures(raw_captures, flow)
        return await _build_generate_response(
            session_id,
            cleaned_intent,
            persona.strip() or "developer",
            language.strip() or "english",
            selected_steps,
            client,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate live-capture demo: {exc}") from exc


@app.post("/export/link", response_model=ExportLinkResponse)
async def export_link(payload: ExportLinkRequest):
    try:
        share_id = str(uuid.uuid4())
        output = {
            "uuid": share_id,
            "intent": payload.intent,
            "total_steps": len(payload.steps),
            "steps": [step.model_dump() for step in payload.steps],
        }
        out_path = SHARED_DIR / f"{share_id}.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        return ExportLinkResponse(share_url=f"http://localhost:8000/share/{share_id}", uuid=share_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to export share link: {exc}") from exc


@app.get("/share/{share_id}")
async def get_shared_demo(share_id: str):
    target = SHARED_DIR / f"{share_id}.json"
    if not target.exists():
        raise HTTPException(status_code=404, detail="Share link not found")
    try:
        return JSONResponse(content=json.loads(target.read_text(encoding="utf-8")))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read shared demo: {exc}") from exc


@app.post("/export/pdf")
async def export_pdf(payload: ExportLinkRequest):
    try:
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        page_width, page_height = letter

        for step in payload.steps:
            y = page_height - inch
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(inch, y, f"Step {step.step_number}")
            y -= 20

            image_path = SCREENSHOTS_DIR / Path(step.screenshot_url).name
            if image_path.exists():
                with Image.open(image_path) as img:
                    img_w, img_h = img.size

                max_w = page_width - 2 * inch
                max_h = page_height * 0.5
                scale = min(max_w / img_w, max_h / img_h)
                draw_w = img_w * scale
                draw_h = img_h * scale
                pdf.drawImage(str(image_path), inch, y - draw_h, width=draw_w, height=draw_h, preserveAspectRatio=True)
                y -= draw_h + 20

            pdf.setFont("Helvetica", 11)
            narration_lines = step.narration.split("\n")
            for line in narration_lines:
                for chunk in [line[i : i + 100] for i in range(0, len(line), 100)] or [""]:
                    if y < inch:
                        pdf.showPage()
                        y = page_height - inch
                        pdf.setFont("Helvetica", 11)
                    pdf.drawString(inch, y, chunk)
                    y -= 14

            if step.api_call:
                y -= 6
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(inch, y, "API Call:")
                y -= 14
                pdf.setFont("Helvetica", 10)
                pdf.drawString(inch, y, step.api_call)

            pdf.showPage()

        pdf.save()
        buffer.seek(0)
        headers = {"Content-Disposition": f'attachment; filename="demogen_{uuid.uuid4().hex[:8]}.pdf"'}
        return StreamingResponse(buffer, media_type="application/pdf", headers=headers)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to export PDF: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

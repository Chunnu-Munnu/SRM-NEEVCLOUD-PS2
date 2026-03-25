from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from utils import clamp_percent, extract_json_block


DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


SUPPORTED_LANGUAGE_NAMES = {
    "english": "English",
    "hindi": "Hindi (Devanagari script)",
    "tamil": "Tamil (Tamil script)",
    "kannada": "Kannada (Kannada script)",
}


def get_client() -> Optional[genai.Client]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text.strip()

    try:
        chunks = []
        for cand in getattr(response, "candidates", []) or []:
            content = getattr(cand, "content", None)
            parts = getattr(content, "parts", []) if content else []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)
        return "\n".join(chunks).strip()
    except Exception:
        return ""


def generate_step_narration(
    screenshot_path: str,
    page_content: str,
    action: str,
    step_purpose: str,
    persona: str,
    step_number: int,
    total_steps: int,
    client: Optional[genai.Client],
) -> Dict[str, Any]:
    fallback = {
        "narration": f"Step {step_number}: {action}. This step helps achieve the goal by {step_purpose.lower()}.",
        "api_call": None,
        "code_snippet": None,
        "highlight": {"x": 25, "y": 25, "width": 50, "height": 50},
        "element_description": "Primary interactive area",
    }

    if client is None:
        return fallback

    try:
        image_bytes = Path(screenshot_path).read_bytes()
    except Exception:
        return fallback

    system_prompt = (
        "You are an expert product demo narrator for NeevCloud, a cloud GPU platform used by ML engineers and enterprises. "
        "Generate precise, screen-grounded narration based on visible UI, never generic filler. "
        "Persona rules: for 'new user' use simple encouraging explanations; for 'developer' be technical and mention API endpoints, CLI equivalents, and automation; "
        "for 'enterprise admin' emphasize governance, permissions, cost management, and compliance considerations. "
        "Return JSON only."
    )

    user_text = (
        f"Action: {action}\n"
        f"Step purpose: {step_purpose}\n"
        f"Page content snippet: {page_content[:800]}\n"
        f"Persona: {persona}\n"
        f"Progress: step {step_number} of {total_steps}.\n\n"
        "Return a JSON object with EXACT keys: narration, api_call, code_snippet, highlight, element_description.\n"
        "- narration: 1-2 sentences tailored to persona\n"
        "- api_call: METHOD /path or null\n"
        "- code_snippet: complete Python requests example or null\n"
        "- highlight: object with x,y,width,height as 0..100 percentages\n"
        "- element_description: short label for highlighted element"
    )

    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[image_part, user_text],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=900,
                temperature=0.3,
                response_mime_type="application/json",
            ),
        )
        parsed = extract_json_block(_response_text(response))
        highlight = parsed.get("highlight") if isinstance(parsed, dict) else None
        highlight = highlight or {}
        return {
            "narration": parsed.get("narration") or fallback["narration"],
            "api_call": parsed.get("api_call"),
            "code_snippet": parsed.get("code_snippet"),
            "highlight": {
                "x": clamp_percent(highlight.get("x"), 25),
                "y": clamp_percent(highlight.get("y"), 25),
                "width": clamp_percent(highlight.get("width"), 50),
                "height": clamp_percent(highlight.get("height"), 50),
            },
            "element_description": parsed.get("element_description") or "Primary interactive area",
        }
    except Exception:
        return fallback


def validate_step_alignment(
    screenshot_path: str,
    intent: str,
    action: str,
    step_purpose: str,
    expected_elements: List[str],
    step_number: int,
    client: Optional[genai.Client],
) -> Dict[str, Any]:
    fallback = {
        "step_number": step_number,
        "is_match": False,
        "should_capture": False,
        "confidence": 0,
        "message": "AI validation is unavailable right now. If the shared tab clearly shows this step, you can still capture it manually.",
        "recommended_action": action,
        "observed_elements": expected_elements[:3],
    }

    if client is None:
        return fallback

    try:
        image_bytes = Path(screenshot_path).read_bytes()
    except Exception:
        return fallback

    expected_text = ", ".join(expected_elements) if expected_elements else "No explicit element list provided"
    prompt = (
        "You are an interactive NeevCloud demo copilot. Look at the screenshot and decide whether the user is on the correct screen for the planned step. "
        "Be strict enough to prevent bad captures, but helpful. Return JSON only.\n\n"
        f"Overall intent: {intent}\n"
        f"Step number: {step_number}\n"
        f"Expected action: {action}\n"
        f"Why this step matters: {step_purpose}\n"
        f"Expected visible elements: {expected_text}\n\n"
        "Return a JSON object with EXACT keys: is_match, should_capture, confidence, message, recommended_action, observed_elements.\n"
        "- is_match: boolean\n"
        "- should_capture: boolean; true only if this frame is good enough to use in the final walkthrough\n"
        "- confidence: integer 0 to 100\n"
        "- message: one short sentence telling the user whether they are on the right screen\n"
        "- recommended_action: one short instruction for what to do next\n"
        "- observed_elements: array of 2 to 5 UI elements you can visibly identify"
    )

    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=[image_part, prompt],
            config=types.GenerateContentConfig(
                max_output_tokens=350,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        parsed = extract_json_block(_response_text(response))
        observed = parsed.get("observed_elements") if isinstance(parsed, dict) else []
        if not isinstance(observed, list):
            observed = []
        confidence_raw = parsed.get("confidence", 0)
        try:
            confidence = max(0, min(100, int(confidence_raw)))
        except (TypeError, ValueError):
            confidence = 0
        is_match = bool(parsed.get("is_match"))
        should_capture = bool(parsed.get("should_capture"))
        return {
            "step_number": step_number,
            "is_match": is_match,
            "should_capture": should_capture,
            "confidence": confidence,
            "message": str(parsed.get("message") or fallback["message"]).strip(),
            "recommended_action": str(parsed.get("recommended_action") or action).strip(),
            "observed_elements": [str(item).strip() for item in observed[:5] if str(item).strip()],
        }
    except Exception:
        return fallback


def translate_narration(
    text: str,
    target_language: str,
    client: Optional[genai.Client],
) -> str:
    cleaned_target = (target_language or "").strip().lower()
    if cleaned_target in ("", "english"):
        return text

    target_label = SUPPORTED_LANGUAGE_NAMES.get(cleaned_target)
    if not target_label:
        return text
    if client is None or not text.strip():
        return text

    prompt = (
        f"Translate this NeevCloud product-demo narration into {target_label}. "
        "Keep the meaning accurate, keep product names like NeevCloud unchanged, and keep the tone professional but friendly. "
        "Return only the translated text, with no JSON and no extra commentary.\n\n"
        f"Narration: {text}"
    )

    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=350,
                temperature=0.2,
            ),
        )
        translated = _response_text(response)
        return translated or text
    except Exception:
        return text


def generate_multilingual_narrations(
    english_narration: str,
    client: Optional[genai.Client],
) -> Dict[str, str]:
    fallback = {"hindi": "", "tamil": "", "kannada": ""}
    if client is None:
        return fallback

    prompt = (
        "Translate and culturally adapt this technical product-demo narration into Hindi (Devanagari), Tamil (Tamil script), and Kannada (Kannada script). "
        "Maintain professional but friendly tone. Return ONLY JSON with keys: hindi, tamil, kannada.\n\n"
        f"English narration: {english_narration}"
    )

    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=450,
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        parsed = extract_json_block(_response_text(response))
        return {
            "hindi": str(parsed.get("hindi", "")).strip(),
            "tamil": str(parsed.get("tamil", "")).strip(),
            "kannada": str(parsed.get("kannada", "")).strip(),
        }
    except Exception:
        return fallback


def generate_faqs(steps_summary: str, intent: str, client: Optional[genai.Client]) -> list:
    if client is None:
        from utils import default_faqs

        return default_faqs(intent)

    prompt = (
        "You are generating FAQs after a NeevCloud interactive demo.\n"
        "Intent: " + intent + "\n\n"
        "Narration summary:\n"
        + steps_summary
        + "\n\n"
        "Generate EXACTLY 7 FAQs in JSON list format. "
        "Each item must include keys: question, answer. Include common errors, best practices, pricing implications, and next steps where relevant. "
        "Return JSON only."
    )

    try:
        response = client.models.generate_content(
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1200,
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        parsed = extract_json_block(_response_text(response))
        if isinstance(parsed, list) and parsed:
            cleaned = []
            for item in parsed[:7]:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question", "")).strip()
                answer = str(item.get("answer", "")).strip()
                if question and answer:
                    cleaned.append({"question": question, "answer": answer})
            if len(cleaned) == 7:
                return cleaned

        from utils import default_faqs

        return default_faqs(intent)
    except Exception:
        from utils import default_faqs

        return default_faqs(intent)

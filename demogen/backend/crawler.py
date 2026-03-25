from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from PIL import Image, ImageDraw
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
except Exception:
    stealth_sync = None

from utils import default_flow, extract_json_block


DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
PROFILE_DIR = Path(os.path.dirname(__file__)) / "browser_profile"
MANUAL_CAPTURE_DIR = Path(os.path.dirname(__file__)) / "manual_capture"
CDP_URL = os.getenv("BROWSER_CDP_URL", "").strip()
PREFER_MANUAL_CAPTURES = os.getenv("PREFER_MANUAL_CAPTURES", "false").strip().lower() == "true"
FALLBACK_BROWSERS = [
    None,
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
HUMAN_CHECK_TOKENS = [
    "are you human",
    "verify you are human",
    "captcha",
    "security check",
    "challenge",
    "checking your browser",
    "cf-challenge",
    "just a moment",
    "performing security verification",
    "verifying you are human",
]


async def map_intent_to_flows(intent: str, client: Optional[genai.Client]) -> list:
    if client is None:
        return default_flow(intent)

    prompt = f"""
You are a navigation planning assistant for the NeevCloud cloud GPU portal.
Known portal sections:
- Dashboard at /dashboard
- GPU Instances at /instances
- Launch New Instance at /instances/new
- Billing and Credits at /billing
- API Keys at /settings/api-keys
- SSH Keys at /settings/ssh-keys
- Storage Volumes at /storage
- Container Registry at /registry
- Network Settings at /network
- Support at /support

User intent: {intent}

Return a JSON array of 5 to 7 ordered steps where each element has:
- url (full URL starting with https://console.ai.neevcloud.com)
- action (string describing what the user is doing on this page)
- expected_elements (array of strings)
- step_purpose (string explaining why this step matters)

Return only valid JSON (no markdown).
""".strip()

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=DEFAULT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=1000, temperature=0.2),
        )
        content = getattr(response, "text", "") or ""
        parsed = extract_json_block(content)
        if isinstance(parsed, list) and parsed:
            normalized = []
            for step in parsed:
                if not isinstance(step, dict):
                    continue
                url = str(step.get("url", "")).strip()
                if not url.startswith("https://console.ai.neevcloud.com"):
                    continue
                normalized.append(
                    {
                        "url": url,
                        "action": str(step.get("action", "Open page")).strip() or "Open page",
                        "expected_elements": step.get("expected_elements", [])
                        if isinstance(step.get("expected_elements"), list)
                        else [],
                        "step_purpose": str(step.get("step_purpose", "Progress the task")).strip() or "Progress the task",
                    }
                )
            if normalized:
                return normalized
        return default_flow(intent)
    except Exception:
        return default_flow(intent)


def _write_placeholder_screenshot(path: str, title: str, subtitle: str) -> None:
    image = Image.new("RGB", (1280, 800), "#0b1220")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 1240, 760), outline="#18d4c0", width=3)
    draw.text((80, 90), title[:120], fill="#ffffff")
    draw.text((80, 150), subtitle[:500], fill="#a9c2d9")
    image.save(path)


def _looks_like_human_check(content: str, page_url: str) -> bool:
    haystack = f"{content}\n{page_url}".lower()
    return any(token in haystack for token in HUMAN_CHECK_TOKENS)


def _wait_for_human_check_resolution(page: Any, timeout_seconds: int = 120) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            content = page.content()
            page_url = page.url
        except Exception:
            return False

        if not _looks_like_human_check(content, page_url):
            return True

        time.sleep(2)

    return False


def _apply_stealth(page: Any) -> None:
    if stealth_sync is None:
        return
    try:
        stealth_sync(page)
    except Exception:
        pass


def _load_manual_captures(session_id: str, flow_steps: list) -> list:
    screenshots_dir = Path(os.path.dirname(__file__)) / "screenshots"
    MANUAL_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    image_files = []
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        image_files.extend(MANUAL_CAPTURE_DIR.glob(pattern))
    image_files = sorted(image_files)

    if not image_files:
        return []

    results: List[Dict[str, Any]] = []
    for idx, image_path in enumerate(image_files, start=1):
        target_name = f"{session_id}_{idx}{image_path.suffix.lower()}"
        target_path = screenshots_dir / target_name
        shutil.copy2(image_path, target_path)

        flow = flow_steps[min(idx - 1, len(flow_steps) - 1)] if flow_steps else {}
        label = image_path.stem.replace("_", " ").replace("-", " ").strip() or f"Manual step {idx}"
        results.append(
            {
                "step_number": idx,
                "screenshot_path": str(target_path),
                "viewport_screenshot_path": str(target_path),
                "url": flow.get("url", "https://console.ai.neevcloud.com"),
                "page_title": label.title(),
                "page_content": f"Manual screenshot captured from a verified user session. Source file: {image_path.name}",
                "action": flow.get("action", f"Review {label}"),
                "expected_elements": flow.get("expected_elements", []),
                "step_purpose": flow.get("step_purpose", "Walk through the user journey from captured screenshots."),
                "is_login_page": False,
            }
        )
    return results


def _all_results_blocked(results: list) -> bool:
    if not results:
        return False
    blocked = 0
    for item in results:
        body = f"{item.get('page_title', '')}\n{item.get('page_content', '')}\n{item.get('url', '')}".lower()
        if any(token in body for token in HUMAN_CHECK_TOKENS):
            blocked += 1
    return blocked == len(results)


def _connect_existing_browser(playwright: Any):
    if not CDP_URL:
        return None, None, None

    browser = playwright.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0] if browser.contexts else None
    if context is None:
        raise RuntimeError(f"Connected to {CDP_URL} but found no browser context")
    return browser, context, f"manual browser via CDP ({CDP_URL})"


def _launch_browser(playwright: Any):
    launch_errors: List[str] = []
    launch_args = [
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-blink-features=AutomationControlled",
    ]

    if CDP_URL:
        try:
            return _connect_existing_browser(playwright)
        except Exception as exc:
            launch_errors.append(f"CDP {CDP_URL}: {exc}")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    for executable_path in FALLBACK_BROWSERS[1:]:
        if not executable_path or not Path(executable_path).exists():
            continue
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                executable_path=executable_path,
                headless=False,
                args=launch_args,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            return None, context, f"{executable_path} (persistent profile)"
        except Exception as exc:
            launch_errors.append(f"{executable_path} (persistent profile): {exc}")

    for executable_path in FALLBACK_BROWSERS:
        launch_kwargs: Dict[str, Any] = {"headless": False, "args": launch_args}
        label = "bundled-chromium"

        if executable_path:
            if not Path(executable_path).exists():
                continue
            launch_kwargs["executable_path"] = executable_path
            label = executable_path

        try:
            browser = playwright.chromium.launch(**launch_kwargs)
            return browser, None, label
        except Exception as exc:
            launch_errors.append(f"{label}: {exc}")

    for executable_path in FALLBACK_BROWSERS:
        launch_kwargs = {"headless": True, "args": launch_args}
        label = "bundled-chromium-headless"

        if executable_path:
            if not Path(executable_path).exists():
                continue
            launch_kwargs["executable_path"] = executable_path
            label = f"{executable_path} (headless)"

        try:
            browser = playwright.chromium.launch(**launch_kwargs)
            return browser, None, label
        except Exception as exc:
            launch_errors.append(f"{label}: {exc}")

    raise RuntimeError(" ; ".join(launch_errors) or "Unable to launch any supported browser")


def _crawl_flow_sync(flow_steps: list, session_id: str) -> list:
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)

    results: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        try:
            browser, context, browser_label = _launch_browser(p)
        except Exception as exc:
            error_summary = str(exc)
            fallback_results: List[Dict[str, Any]] = []

            for idx, step in enumerate(flow_steps, start=1):
                full_filename = f"{session_id}_{idx}.png"
                viewport_filename = f"{session_id}_{idx}_viewport.png"
                full_path = os.path.join(screenshots_dir, full_filename)
                viewport_path = os.path.join(screenshots_dir, viewport_filename)

                _write_placeholder_screenshot(full_path, f"NeevCloud capture fallback - Step {idx}", f"Browser launch failed. {error_summary}")
                _write_placeholder_screenshot(viewport_path, f"NeevCloud capture fallback - Step {idx}", f"Browser launch failed. {error_summary}")

                fallback_results.append(
                    {
                        "step_number": idx,
                        "screenshot_path": full_path,
                        "viewport_screenshot_path": viewport_path,
                        "url": step.get("url", ""),
                        "page_title": f"Fallback capture for step {idx}",
                        "page_content": error_summary,
                        "action": step.get("action", "Open page"),
                        "expected_elements": step.get("expected_elements", []),
                        "step_purpose": step.get("step_purpose", "Progress the task"),
                        "is_login_page": False,
                    }
                )

            return fallback_results

        if context is None:
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            page = context.new_page()
        else:
            page = context.pages[0] if context.pages else context.new_page()

        if not CDP_URL:
            page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = window.chrome || { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                """
            )
            _apply_stealth(page)

        for idx, step in enumerate(flow_steps, start=1):
            try:
                url = step.get("url", "https://console.ai.neevcloud.com/dashboard")
                page.goto(url, timeout=20000)

                try:
                    page.wait_for_load_state("networkidle", timeout=12000)
                except PlaywrightTimeoutError:
                    pass
                except Exception:
                    pass

                content = page.content()
                page_url = page.url
                human_check = _looks_like_human_check(content, page_url)
                human_check_resolved = True
                if human_check:
                    human_check_resolved = _wait_for_human_check_resolution(page)
                    try:
                        content = page.content()
                        page_url = page.url
                    except Exception:
                        content = ""

                time.sleep(1.5)

                try:
                    page_title = page.title()
                except Exception:
                    page_title = f"Step {idx}"
                try:
                    body_text = page.evaluate("() => (document.body && document.body.innerText) ? document.body.innerText : ''")
                except Exception:
                    body_text = ""
                body_text = (body_text or "")[:800]

                full_filename = f"{session_id}_{idx}.png"
                viewport_filename = f"{session_id}_{idx}_viewport.png"
                full_path = os.path.join(screenshots_dir, full_filename)
                viewport_path = os.path.join(screenshots_dir, viewport_filename)

                try:
                    page.screenshot(path=full_path, full_page=True)
                    page.screenshot(path=viewport_path, full_page=False)
                except Exception as exc:
                    _write_placeholder_screenshot(full_path, f"NeevCloud capture fallback - Step {idx}", str(exc))
                    _write_placeholder_screenshot(viewport_path, f"NeevCloud capture fallback - Step {idx}", str(exc))

                try:
                    content = page.content().lower()
                except Exception:
                    content = ""
                is_login_page = any(token in content for token in ["sign in", "log in", "login"])
                if human_check and not human_check_resolved:
                    body_text = (
                        f"Human verification page detected for {url}. Solve the verification and log in using the opened browser, "
                        "then run Generate Demo again to reuse the saved browser profile or manual browser session.\n\n" + body_text
                    )

                results.append(
                    {
                        "step_number": idx,
                        "screenshot_path": full_path,
                        "viewport_screenshot_path": viewport_path,
                        "url": page_url,
                        "page_title": page_title or f"Step {idx}",
                        "page_content": f"{body_text}\n\nBrowser: {browser_label}",
                        "action": step.get("action", "Open page"),
                        "expected_elements": step.get("expected_elements", []),
                        "step_purpose": step.get("step_purpose", "Progress the task"),
                        "is_login_page": is_login_page,
                    }
                )
            except Exception as step_error:
                results.append(
                    {
                        "step_number": idx,
                        "screenshot_path": "",
                        "viewport_screenshot_path": "",
                        "url": step.get("url", ""),
                        "page_title": f"Step {idx} (capture failed)",
                        "page_content": str(step_error),
                        "action": step.get("action", "Open page"),
                        "expected_elements": step.get("expected_elements", []),
                        "step_purpose": step.get("step_purpose", "Progress the task"),
                        "is_login_page": False,
                    }
                )

        try:
            if CDP_URL:
                browser.close()
            else:
                context.close()
                if browser is not None:
                    browser.close()
        except Exception:
            pass

    return results


async def crawl_flow(flow_steps: list, session_id: str) -> list:
    if PREFER_MANUAL_CAPTURES:
        manual_results = _load_manual_captures(session_id, flow_steps)
        if manual_results:
            return manual_results
    live_results = await asyncio.to_thread(_crawl_flow_sync, flow_steps, session_id)
    if _all_results_blocked(live_results):
        manual_results = _load_manual_captures(session_id, flow_steps)
        if manual_results:
            return manual_results
    return live_results

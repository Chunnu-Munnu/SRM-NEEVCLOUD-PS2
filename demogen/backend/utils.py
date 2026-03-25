from __future__ import annotations

import json
from typing import Any, Dict, List


def clamp_percent(value: Any, default: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(100.0, num))


def extract_json_block(raw_text: str) -> Any:
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty model response")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start_obj = text.find("{")
    start_arr = text.find("[")
    start_candidates = [idx for idx in (start_obj, start_arr) if idx != -1]
    if not start_candidates:
        raise ValueError("No JSON object/array found")
    start = min(start_candidates)

    end_obj = text.rfind("}")
    end_arr = text.rfind("]")
    end = max(end_obj, end_arr)
    if end <= start:
        raise ValueError("No valid JSON closing bracket found")

    return json.loads(text[start : end + 1])


def default_flow(intent: str) -> List[Dict[str, Any]]:
    base = "https://console.ai.neevcloud.com"
    return [
        {
            "url": f"{base}/dashboard",
            "action": "Review dashboard overview",
            "expected_elements": ["Usage cards", "Navigation sidebar", "Recent activity"],
            "step_purpose": f"Establish context for goal: {intent}",
        },
        {
            "url": f"{base}/instances",
            "action": "Open GPU instances list",
            "expected_elements": ["Instance table", "Launch button", "Status indicators"],
            "step_purpose": "Find the compute area relevant to the requested NeevCloud task.",
        },
        {
            "url": f"{base}/instances/new",
            "action": "Start launching a new instance",
            "expected_elements": ["Instance configuration form", "GPU selection", "Launch CTA"],
            "step_purpose": "Reach the primary provisioning workflow.",
        },
        {
            "url": f"{base}/settings/ssh-keys",
            "action": "Review SSH key or access configuration",
            "expected_elements": ["SSH key list", "Add key button", "Access configuration"],
            "step_purpose": "Show how secure access is configured before using the resource.",
        },
        {
            "url": f"{base}/billing",
            "action": "Review cost, credits, or billing implications",
            "expected_elements": ["Credits", "Billing summary", "Usage details"],
            "step_purpose": "Explain the pricing or account impact of the workflow.",
        },
    ]


def default_faqs(intent: str) -> List[Dict[str, str]]:
    return [
        {
            "question": "What should I verify before creating a new GPU instance?",
            "answer": "Check available credits, region availability, GPU type, and SSH key setup to avoid launch failures.",
        },
        {
            "question": "How do I control costs while testing?",
            "answer": "Use smaller instance sizes first, stop idle instances, and monitor usage from the billing page regularly.",
        },
        {
            "question": "Can this flow be automated with an API?",
            "answer": "Yes. Most UI actions map to REST operations for listing, creating, and managing compute resources programmatically.",
        },
        {
            "question": "What if I hit quota errors?",
            "answer": "Review account limits, active instances, and credits. Then retry with a smaller GPU profile or request a limit increase.",
        },
        {
            "question": "How do teams share access safely?",
            "answer": "Use role-based access, separate API keys per service, and rotate credentials periodically.",
        },
        {
            "question": "Where do I troubleshoot launch issues?",
            "answer": "Start from instance event logs, then verify network rules, SSH keys, and image compatibility.",
        },
        {
            "question": f"What are the next steps after completing '{intent}'?",
            "answer": "Validate workload performance, capture the final configuration as a template, and document repeatable setup steps for your team.",
        },
    ]

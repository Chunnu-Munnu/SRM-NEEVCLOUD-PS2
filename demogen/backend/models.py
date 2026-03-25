from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    intent: str
    persona: str = "developer"
    language: str = "english"


class HighlightBox(BaseModel):
    x: float = Field(default=25.0)
    y: float = Field(default=25.0)
    width: float = Field(default=50.0)
    height: float = Field(default=50.0)


class DemoStep(BaseModel):
    step_number: int
    screenshot_url: str
    narration: str
    api_call: Optional[str] = None
    code_snippet: Optional[str] = None
    language_narrations: Dict[str, str] = Field(default_factory=dict)
    highlight: HighlightBox = Field(default_factory=HighlightBox)
    page_title: str
    url: str
    element_description: str = "Main action area"


class GenerateResponse(BaseModel):
    session_id: str
    steps: List[DemoStep]
    faqs: List[Dict[str, str]]
    total_steps: int
    intent: str
    persona: str


class ExportLinkRequest(BaseModel):
    steps: List[DemoStep]
    intent: str


class ExportLinkResponse(BaseModel):
    share_url: str
    uuid: str


class LiveStepValidationResponse(BaseModel):
    step_number: int
    is_match: bool = False
    should_capture: bool = False
    confidence: int = 0
    message: str = ""
    recommended_action: str = ""
    observed_elements: List[str] = Field(default_factory=list)


class TranslationRequest(BaseModel):
    text: str
    target_language: str


class TranslationResponse(BaseModel):
    target_language: str
    translated_text: str

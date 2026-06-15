from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateOut(BaseModel):
    id: str
    code: str
    display_name: str
    description: str | None = None
    category: str
    caller_persona: str
    reason_code: str
    sender_persona_key: str
    sender_display_name: str
    supports_contact_save: bool = True
    is_custom: bool = False
    supported_channels: list[str]
    call_max_duration_seconds: int | None = None
    preview_opening_line: str | None = None
    preview_sms_body: str | None = None


class TemplateListResponse(BaseModel):
    templates: list[TemplateOut]


class CreateCustomTemplateBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    category: str
    persona: str
    reason: str
    urgency: str = "normal"
    channels: list[str] = Field(min_length=1)
    voice_style: str = "neutral"
    call_max_seconds: int | None = None


class TemplateOptionItem(BaseModel):
    code: str
    label: str


class TemplateOptionsResponse(BaseModel):
    personas: list[TemplateOptionItem]
    reasons: list[TemplateOptionItem]
    categories: list[str]
    urgencies: list[str]
    voice_styles: list[str]
    channels: list[str]
    call_seconds_min: int
    call_seconds_max: int
    call_seconds_default: int

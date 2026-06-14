from __future__ import annotations

from pydantic import BaseModel


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
    supported_channels: list[str]
    call_max_duration_seconds: int | None = None
    preview_opening_line: str | None = None
    preview_sms_body: str | None = None


class TemplateListResponse(BaseModel):
    templates: list[TemplateOut]

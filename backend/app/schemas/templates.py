from __future__ import annotations

from pydantic import BaseModel, Field


class TemplateChoicesOut(BaseModel):
    """What the editor opens with; the same fields the create and update bodies take."""

    display_name: str
    description: str | None = None
    category: str
    persona: str
    reason: str
    channels: list[str]
    urgency: str
    outcome: str
    setting: str
    tone: str
    detail_profile: str
    discretion_level: str
    formality: str
    expected_response: str
    followup_behavior: str
    continuity_scope: str
    context_modules: list[str] = Field(default_factory=list)
    voice_style: str
    call_max_seconds: int | None = None


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
    is_edited: bool = False
    original_id: str | None = None
    choices: TemplateChoicesOut | None = None
    supported_channels: list[str]
    call_max_duration_seconds: int | None = None
    preview_opening_line: str | None = None
    preview_sms_body: str | None = None


class TemplateListResponse(BaseModel):
    templates: list[TemplateOut]


class CreateCustomTemplateBody(BaseModel):
    """Structured custom-template inputs. All coded fields; the backend rejects
    anything outside the approved catalogs. No free-form provider content."""

    display_name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=255)
    category: str
    persona: str
    reason: str
    channels: list[str] = Field(min_length=1)
    # Richer shared-core meaning (sensible defaults so a minimal payload works).
    urgency: str = "medium"
    outcome: str = "step_out_briefly"
    setting: str = "casual_hangout"
    tone: str = "casual"
    detail_profile: str = "minimal"
    discretion_level: str = "normal"
    formality: str = "neutral"
    expected_response: str = "no_reply_needed"
    followup_behavior: str = "one_touch_only"
    continuity_scope: str = "one_off"
    context_modules: list[str] = Field(default_factory=list)
    # Existing channel knobs.
    voice_style: str = "neutral"
    call_max_seconds: int | None = None

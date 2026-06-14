from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateRequestBody(BaseModel):
    # extra="forbid" is load-bearing: it rejects any attempt to smuggle a
    # destination phone number (e.g. "to", "phone_number", "target") in the body.
    model_config = ConfigDict(extra="forbid")

    client_request_id: str = Field(min_length=1, max_length=128)
    template_id: str
    channel: Literal["call", "sms"]
    delay_seconds: int | None = None
    scheduled_at: datetime | None = None


class SenderIdentityOut(BaseModel):
    sender_binding_id: str
    sender_persona_key: str | None = None
    sender_display_name: str | None = None
    sender_phone_e164: str | None = None
    contact_prompt_recommended: bool = False


class CreateRequestResponse(BaseModel):
    request_id: str
    channel: str
    status: str
    execute_at: datetime
    credits_available: int
    cancelable: bool
    sender_identity: SenderIdentityOut | None = None


class AttemptSummary(BaseModel):
    status: str
    provider_status: str | None = None
    duration_seconds: int | None = None
    failure_reason: str | None = None


class RequestDetail(BaseModel):
    request_id: str
    channel: str
    status: str
    scheduled_kind: str
    execute_at: datetime
    requested_at: datetime
    cancelable: bool
    last_error_code: str | None = None
    latest_attempt: AttemptSummary | None = None
    sender_identity: SenderIdentityOut | None = None


class CancelResponse(BaseModel):
    request_id: str
    status: str

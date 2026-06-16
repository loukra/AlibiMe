from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HistoryItem(BaseModel):
    request_id: str
    channel: str
    template_label: str
    requested_at: datetime
    execute_at: datetime
    final_status: str
    cancelable: bool = False
    duration_seconds: int | None = None
    delivered_preview: str | None = None
    sender_binding_id: str | None = None
    sender_persona_key: str | None = None
    sender_display_name: str | None = None
    sender_phone_e164: str | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    limit: int
    offset: int
    has_more: bool

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HistoryItem(BaseModel):
    request_id: str
    channel: str
    template_label: str
    requested_at: datetime
    final_status: str
    duration_seconds: int | None = None
    delivered_preview: str | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]
    limit: int
    offset: int
    has_more: bool

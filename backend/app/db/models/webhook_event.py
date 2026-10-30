from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_pk
from app.db.models.enums import WebhookProcessingStatus


class WebhookEvent(Base):
    """Append-only webhook log: the parsed event, stored before processing.
    Provider voice and SMS reports keep no raw payload (see webhook_ingest)."""

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="uq_provider_external_event"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    received_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(16), default=WebhookProcessingStatus.received.value, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

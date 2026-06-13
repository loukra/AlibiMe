from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, uuid_fk, uuid_pk
from app.db.models.enums import CallAttemptStatus, MessageAttemptStatus


class CallAttempt(Base, TimestampMixin):
    __tablename__ = "call_attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    request_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    provider_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), default=CallAttemptStatus.created.value, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ringing_at: Mapped[datetime | None] = mapped_column(nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_payload_sanitized_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)


class MessageAttempt(Base, TimestampMixin):
    __tablename__ = "message_attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    request_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    provider_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), default=MessageAttemptStatus.created.value, nullable=False
    )
    queued_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    estimated_cost_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_payload_sanitized_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)

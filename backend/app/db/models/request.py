from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, uuid_fk, uuid_pk
from app.db.models.enums import RequestStatus, ScheduledKind


class Request(Base, TimestampMixin):
    """User intent to receive a call or message. No free target-number field exists."""

    __tablename__ = "requests"
    __table_args__ = (
        # Idempotency: one request per (user, client_request_id).
        UniqueConstraint("user_id", "client_request_id", name="uq_user_client_request"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("templates.id"), nullable=False)
    template_version_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("template_versions.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(8), nullable=False)
    primary_phone_number_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("phone_numbers.id"), nullable=False)
    service_identity_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("service_identities.id"), nullable=True
    )
    # Stable sender binding resolved at create time (SMS), plus an immutable
    # snapshot so history renders correctly even if inventory changes later.
    sender_binding_id: Mapped[uuid.UUID | None] = uuid_fk(
        ForeignKey("user_sender_bindings.id"), nullable=True
    )
    sender_persona_key: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sender_display_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sender_phone_e164_snapshot: Mapped[str | None] = mapped_column(String(32), nullable=True)
    client_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(nullable=False)
    execute_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(24), default=RequestStatus.scheduled.value, nullable=False, index=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scheduled_kind: Mapped[str] = mapped_column(
        String(16), default=ScheduledKind.immediate.value, nullable=False
    )
    request_plan_snapshot_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    credit_cost_units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    credits_reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

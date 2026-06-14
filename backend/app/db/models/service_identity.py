from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_pk
from app.db.models.enums import IdentityType, ServiceIdentityStatus


class ServiceIdentity(Base):
    """Service-controlled outbound identity (sender). Never a third party's number."""

    __tablename__ = "service_identities"

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Provider-native sender handle. For Twilio SMS this is the phone-number SID
    # (PNxxxx); kept generic so a Vapi voice sender can reuse the same column.
    external_identity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Optional Twilio Messaging Service (MGxxxx) to send through, and the Vapi
    # phone-number id for later voice reuse — Twilio/Vapi specifics kept at the
    # infrastructure edge, not in the domain.
    twilio_messaging_service_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vapi_phone_number_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_value: Mapped[str] = mapped_column(String(64), nullable=False)
    identity_type: Mapped[str] = mapped_column(
        String(32), default=IdentityType.phone_number.value, nullable=False
    )
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    capability_outbound_voice: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    capability_outbound_sms: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=ServiceIdentityStatus.active.value, nullable=False
    )
    # Optional internal label for the pool, e.g. "primary-sms-de".
    display_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

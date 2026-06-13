from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_pk


class OtpVerification(Base):
    """Tracks an in-flight OTP verification (provider-agnostic).

    Stores only the phone hash + encrypted phone, never the raw number. The
    code is stored hashed; mock provider also keeps a debug copy in dev.
    """

    __tablename__ = "otp_verifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_verification_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phone_e164_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    line_type: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    locale: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(8), default="sms", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

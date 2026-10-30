from __future__ import annotations

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base


class FreeAllowanceClaim(Base):
    """Phone numbers (as HMAC hash) that already got the free starter credits.

    Kept when an account is deleted so deleting and signing up again doesn't
    hand out free credits twice. Holds no personal data beyond the hash.
    """

    __tablename__ = "free_allowance_claims"

    phone_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    claimed_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)


class FirstPurchaseBonusClaim(Base):
    """Phone numbers (as HMAC hash) that already got the first-purchase bonus,
    kept across account deletion like ``FreeAllowanceClaim``."""

    __tablename__ = "first_purchase_bonus_claims"

    phone_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    claimed_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)

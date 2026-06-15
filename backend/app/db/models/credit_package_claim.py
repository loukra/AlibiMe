from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.db.base import Base, uuid_fk, uuid_pk
from app.db.models.enums import CreditPackageClaimStatus, FulfillmentMode


class CreditPackageClaim(Base):
    """Audit record of a credit-package acquisition (free-dev grant now, paid
    store purchase later). Separate from the ledger so the purchase intent has a
    stable home and grants can be made idempotent and, later, validated against a
    store transaction."""

    __tablename__ = "credit_package_claims"
    __table_args__ = (
        # Idempotency: one claim per (user, client_request_id) so repeated taps
        # never grant twice.
        UniqueConstraint("user_id", "client_request_id", name="uq_claim_user_client_request"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("plans.id"), nullable=True)
    plan_code: Mapped[str] = mapped_column(String(48), nullable=False)
    credits_granted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fulfillment_mode: Mapped[str] = mapped_column(
        String(24), default=FulfillmentMode.free_dev.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=CreditPackageClaimStatus.pending.value, nullable=False
    )
    client_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    store_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    granted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

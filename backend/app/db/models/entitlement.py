from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_fk, uuid_pk
from app.db.models.enums import EntitlementStatus


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    plan_id: Mapped[uuid.UUID] = uuid_fk(ForeignKey("plans.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default=EntitlementStatus.active.value, nullable=False
    )
    starts_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    external_customer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    external_entitlement_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)

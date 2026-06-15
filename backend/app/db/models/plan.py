from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from app.db.models.enums import FulfillmentMode, PlanKind


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default=PlanKind.one_time.value, nullable=False)
    included_credit_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    store_product_ids_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Catalog / fulfillment metadata for the user-facing credit-package picker.
    # Nullable so existing free/subscription plans need no values; credit packs
    # are seeded with these set. Keeps the door open for paid store purchases
    # without changing the user-facing flow.
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    badge_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fulfillment_mode: Mapped[str] = mapped_column(
        String(24), default=FulfillmentMode.free_dev.value, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)

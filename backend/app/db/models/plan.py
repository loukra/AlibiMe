from __future__ import annotations

import uuid

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from app.db.models.enums import PlanKind


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default=PlanKind.one_time.value, nullable=False)
    included_credit_units: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    store_product_ids_json: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

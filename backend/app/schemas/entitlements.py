from __future__ import annotations

from pydantic import BaseModel


class EntitlementItem(BaseModel):
    plan_code: str | None = None
    status: str


class EntitlementsResponse(BaseModel):
    credits_available: int
    active_entitlements: list[EntitlementItem]

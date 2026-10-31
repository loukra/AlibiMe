from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.credit_packages import CreditCosts


class EntitlementSummaryItem(BaseModel):
    plan_code: str | None = None
    status: str


class ActiveRequestSummary(BaseModel):
    request_id: str
    channel: str
    status: str
    execute_at: str


class MeResponse(BaseModel):
    id: str
    locale: str
    timezone: str
    phone_number_masked: str | None = None
    credits_available: int
    active_entitlements: list[EntitlementSummaryItem] = []
    active_request: ActiveRequestSummary | None = None
    # What a call and a text cost, so the send button can show its price.
    credit_costs: CreditCosts


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: Literal["en", "de"] | None = None
    timezone: str | None = Field(default=None, max_length=64)

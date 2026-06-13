from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    display_name: str | None = None
    phone_number_masked: str | None = None
    credits_available: int
    active_entitlements: list[EntitlementSummaryItem] = []
    active_request: ActiveRequestSummary | None = None


class MeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: Literal["en", "de"] | None = None
    timezone: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=120)

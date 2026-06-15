from __future__ import annotations

from pydantic import BaseModel, Field


class CreditPackageOut(BaseModel):
    code: str
    display_name: str
    credits: int
    fulfillment_mode: str
    price_label: str
    badge_text: str | None = None
    active: bool
    sort_order: int


class CreditPackagesResponse(BaseModel):
    packages: list[CreditPackageOut]


class AcquirePackageBody(BaseModel):
    client_request_id: str = Field(min_length=1, max_length=128)


class AcquirePackageResponse(BaseModel):
    claim_id: str
    status: str
    granted_credits: int
    credits_available: int
    plan_code: str

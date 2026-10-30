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
    # App Store product to buy for app_store_iap packs; the app shows the
    # store's localized price instead of price_label when it has it.
    store_product_id: str | None = None


class CreditCosts(BaseModel):
    call: int
    sms: int


class CreditPackagesResponse(BaseModel):
    packages: list[CreditPackageOut]
    credit_costs: CreditCosts


class RedeemBody(BaseModel):
    signed_transaction: str = Field(min_length=1, max_length=20000)


class AcquirePackageBody(BaseModel):
    client_request_id: str = Field(min_length=1, max_length=128)


class AcquirePackageResponse(BaseModel):
    claim_id: str
    status: str
    granted_credits: int
    credits_available: int
    plan_code: str

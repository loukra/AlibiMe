from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.core.config import settings
from app.domain.billing import credit_packages
from app.schemas.credit_packages import (
    AcquirePackageBody,
    AcquirePackageResponse,
    CreditCosts,
    CreditPackageOut,
    CreditPackagesResponse,
    RedeemBody,
)

router = APIRouter(prefix="/v1/credit-packages", tags=["credit-packages"])


@router.get("", response_model=CreditPackagesResponse)
def list_packages(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> CreditPackagesResponse:
    packages = credit_packages.list_active_packages(db)
    return CreditPackagesResponse(
        packages=[
            CreditPackageOut(
                code=p.code,
                display_name=p.display_name or p.code.replace("_", " ").title(),
                credits=p.included_credit_units,
                fulfillment_mode=p.fulfillment_mode,
                price_label=credit_packages.price_label(p),
                badge_text=p.badge_text,
                active=p.active,
                sort_order=p.sort_order,
                store_product_id=credit_packages.store_product_id(p),
            )
            for p in packages
        ],
        credit_costs=CreditCosts(call=settings.call_credit_cost, sms=settings.sms_credit_cost),
    )


@router.post("/redeem", response_model=AcquirePackageResponse)
def redeem(
    body: RedeemBody,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> AcquirePackageResponse:
    """Grant the credits of an App Store purchase (StoreKit 2 signed transaction)."""
    result = credit_packages.redeem_store_transaction(db, ctx.user.id, body.signed_transaction)
    return AcquirePackageResponse(**result)


@router.post("/{code}/acquire", response_model=AcquirePackageResponse)
def acquire_package(
    code: str,
    body: AcquirePackageBody,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> AcquirePackageResponse:
    result = credit_packages.acquire_package(
        db,
        ctx.user.id,
        code=code,
        client_request_id=body.client_request_id,
    )
    return AcquirePackageResponse(**result)

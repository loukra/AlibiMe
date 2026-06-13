from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.domain.billing.entitlements import entitlement_summary
from app.schemas.entitlements import EntitlementItem, EntitlementsResponse

router = APIRouter(prefix="/v1/entitlements", tags=["entitlements"])


@router.get("", response_model=EntitlementsResponse)
def get_entitlements(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> EntitlementsResponse:
    summary = entitlement_summary(db, ctx.user.id)
    return EntitlementsResponse(
        credits_available=summary["credits_available"],
        active_entitlements=[EntitlementItem(**e) for e in summary["active_entitlements"]],
    )

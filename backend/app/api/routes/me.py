from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.domain.billing.entitlements import entitlement_summary
from app.domain.requests.service import get_active_request
from app.domain.users.service import masked_primary_number
from app.schemas.me import (
    ActiveRequestSummary,
    EntitlementSummaryItem,
    MeResponse,
    MeUpdate,
)

router = APIRouter(prefix="/v1/me", tags=["me"])


def _build_me(db: Session, user) -> MeResponse:
    summary = entitlement_summary(db, user.id)
    active = get_active_request(db, user.id)
    active_summary = None
    if active:
        active_summary = ActiveRequestSummary(
            request_id=str(active.id),
            channel=active.channel,
            status=active.status,
            execute_at=active.execute_at.isoformat(),
        )
    return MeResponse(
        id=str(user.id),
        locale=user.locale,
        timezone=user.timezone,
        display_name=user.display_name,
        phone_number_masked=masked_primary_number(db, user.id),
        credits_available=summary["credits_available"],
        active_entitlements=[EntitlementSummaryItem(**e) for e in summary["active_entitlements"]],
        active_request=active_summary,
    )


@router.get("", response_model=MeResponse)
def get_me(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    return _build_me(db, ctx.user)


@router.patch("", response_model=MeResponse)
def patch_me(
    body: MeUpdate,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MeResponse:
    user = ctx.user
    if body.locale is not None:
        user.locale = body.locale
    if body.timezone is not None:
        user.timezone = body.timezone
    if body.display_name is not None:
        user.display_name = body.display_name
    db.commit()
    return _build_me(db, user)

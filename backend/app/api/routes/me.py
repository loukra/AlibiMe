from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import CurrentContext, get_current_context, get_db
from app.core.config import settings
from app.domain.billing.entitlements import entitlement_summary
from app.domain.profile import context as profile_context
from app.domain.requests.service import get_active_request
from app.domain.users import first_names
from app.domain.users.service import delete_account, masked_primary_number
from app.schemas.context_profile import ContextProfileBody, ContextProfileOut
from app.schemas.credit_packages import CreditCosts
from app.schemas.me import (
    ActiveRequestSummary,
    EntitlementSummaryItem,
    FirstNamesResponse,
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
        first_name=user.first_name,
        phone_number_masked=masked_primary_number(db, user.id),
        credits_available=summary["credits_available"],
        active_entitlements=[EntitlementSummaryItem(**e) for e in summary["active_entitlements"]],
        active_request=active_summary,
        credit_costs=CreditCosts(call=settings.call_credit_cost, sms=settings.sms_credit_cost),
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
    if body.first_name is not None:
        user.first_name = first_names.require(body.first_name) if body.first_name.strip() else None
    db.commit()
    return _build_me(db, user)


@router.get("/first-names", response_model=FirstNamesResponse)
def search_first_names(
    q: str = Query(default="", max_length=40),
    ctx: CurrentContext = Depends(get_current_context),
) -> FirstNamesResponse:
    return FirstNamesResponse(names=first_names.search(q))


@router.delete("", status_code=204)
def delete_me(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Response:
    """Delete the account and its data. The session token stops working."""
    delete_account(db, ctx.user.id)
    return Response(status_code=204)


@router.get("/context-profile", response_model=ContextProfileOut)
def get_context_profile(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ContextProfileOut:
    profile = profile_context.get_profile(db, ctx.user.id)
    return ContextProfileOut(**profile_context.profile_to_dict(profile))


@router.put("/context-profile", response_model=ContextProfileOut)
def put_context_profile(
    body: ContextProfileBody,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ContextProfileOut:
    # Only fields explicitly sent are written (so a partial save doesn't clear
    # the rest); send an explicit null to clear a field.
    values = body.model_dump(exclude_unset=True)
    profile = profile_context.upsert_profile(db, ctx.user.id, values)
    return ContextProfileOut(**profile_context.profile_to_dict(profile))

"""Entitlement summaries + free onboarding allowance."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.credit_ledger import CreditLedger
from app.db.models.free_allowance_claim import FreeAllowanceClaim
from app.db.models.entitlement import Entitlement
from app.db.models.enums import (
    CreditReferenceType,
    EntitlementSource,
    EntitlementStatus,
)
from app.db.models.plan import Plan
from app.core.logging import get_logger
from app.domain.billing import credits
from app.providers.device_check import DeviceCheckUnavailable, get_device_check

logger = get_logger("entitlements")

# Virtual numbers cost nothing to get in bulk, so they don't get free credits.
# They can still use the app and buy credits.
_NO_FREE_CREDIT_LINE_TYPES = {"non_fixed_voip"}


def entitlement_summary(db: Session, user_id: uuid.UUID) -> dict:
    rows = db.execute(
        select(Entitlement, Plan)
        .join(Plan, Plan.id == Entitlement.plan_id, isouter=True)
        .where(
            Entitlement.user_id == user_id,
            Entitlement.status == EntitlementStatus.active.value,
        )
    ).all()
    active = [
        {"plan_code": plan.code if plan else None, "status": ent.status}
        for ent, plan in rows
    ]
    return {
        "credits_available": credits.current_balance(db, user_id),
        "active_entitlements": active,
    }


def grant_free_test_allowance(
    db: Session,
    user_id: uuid.UUID,
    phone_hash: str | None = None,
    *,
    line_type: str | None = None,
    device_token: str | None = None,
) -> None:
    """Grant the one-time free onboarding allowance, if enabled and not used.

    With ``phone_hash`` the allowance is once per phone number, so a deleted and
    recreated account doesn't get it again. Virtual numbers get none, and with
    DeviceCheck on it is also once per iPhone: no device token, no free credits.
    """
    if not settings.feature_free_test_request or settings.free_test_credits <= 0:
        return
    if line_type in _NO_FREE_CREDIT_LINE_TYPES:
        return
    already = db.execute(
        select(CreditLedger.id).where(CreditLedger.user_id == user_id).limit(1)
    ).first()
    if already:
        return
    if phone_hash is not None and db.get(FreeAllowanceClaim, phone_hash) is not None:
        return
    device_check = get_device_check()
    if device_check is not None:
        if not device_token:
            return
        try:
            if device_check.already_claimed(device_token):
                return
        except DeviceCheckUnavailable as exc:
            # Apple unreachable: the phone-number check still holds.
            logger.warning("device_check_unavailable", extra={"error": str(exc)})
            device_check = None
    if phone_hash is not None:
        db.add(FreeAllowanceClaim(phone_hash=phone_hash))
    free_plan = db.execute(select(Plan).where(Plan.code == "free")).scalar_one_or_none()
    ent = Entitlement(
        user_id=user_id,
        source=EntitlementSource.promo.value,
        plan_id=free_plan.id if free_plan else None,
        status=EntitlementStatus.active.value,
    )
    db.add(ent)
    db.flush()
    credits.grant(
        db,
        user_id,
        settings.free_test_credits,
        reference_type=CreditReferenceType.purchase,
        reference_id=ent.id,
        notes="free onboarding allowance",
    )
    if device_check is not None:
        try:
            device_check.mark_claimed(device_token)
        except DeviceCheckUnavailable as exc:
            logger.warning("device_check_unavailable", extra={"error": str(exc)})

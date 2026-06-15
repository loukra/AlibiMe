"""Credit-package catalog + acquisition.

Reuses the existing ``plans`` table (credit packs are ``kind = one_time`` plans
that grant ``included_credit_units``) and the ledger-based credit accounting.
Every acquisition is recorded as a ``CreditPackageClaim`` (audit trail +
idempotency) and credits are granted through the normal ledger path — even while
packages are free in the current ``free_dev`` phase.

The same claim + ledger path is what a future ``app_store_iap`` flow will reuse
after validating a store transaction; only the fulfillment branch changes.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError, NotFound, ValidationFailed
from app.db.models.credit_package_claim import CreditPackageClaim
from app.db.models.enums import (
    CreditPackageClaimStatus,
    CreditReferenceType,
    FulfillmentMode,
    PlanKind,
)
from app.db.models.plan import Plan
from app.domain.billing import credits


class PackageNotAcquirable(AppError):
    code = "package_not_acquirable"
    http_status = 409
    default_message = "This credit package can no longer be acquired."


def is_credit_package(plan: Plan) -> bool:
    """A credit package is an active one-time plan that grants credits."""
    return (
        plan.active
        and plan.kind == PlanKind.one_time.value
        and (plan.included_credit_units or 0) > 0
    )


def price_label(plan: Plan) -> str:
    """Human-facing price string, controlled by package metadata so it can change
    when packages become paid without any frontend change."""
    if plan.fulfillment_mode == FulfillmentMode.free_dev.value:
        return "Free for now"
    if plan.price_minor is not None and plan.currency_code:
        return f"{plan.price_minor / 100:.2f} {plan.currency_code}"
    return "—"


def list_active_packages(db: Session) -> list[Plan]:
    """All packages shown in the Add Credits sheet, ordered for direct display."""
    plans = (
        db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order))
        .scalars()
        .all()
    )
    return [p for p in plans if is_credit_package(p)]


def _claim_result(db: Session, claim: CreditPackageClaim, user_id: uuid.UUID) -> dict:
    return {
        "claim_id": str(claim.id),
        "status": claim.status,
        "granted_credits": claim.credits_granted,
        "credits_available": credits.current_balance(db, user_id),
        "plan_code": claim.plan_code,
    }


def acquire_package(
    db: Session,
    user_id: uuid.UUID,
    *,
    code: str,
    client_request_id: str,
) -> dict:
    """Acquire a credit package. Idempotent on (user, client_request_id).

    Current phase: ``free_dev`` packages grant immediately via the ledger. A
    ``app_store_iap`` package is rejected here until the paid flow lands (the
    claim/ledger path is already shared, so only this branch needs to change).
    """
    if not client_request_id:
        raise ValidationFailed("client_request_id is required.")

    # Idempotency: a prior claim for this (user, client_request_id) wins.
    existing = db.execute(
        select(CreditPackageClaim).where(
            CreditPackageClaim.user_id == user_id,
            CreditPackageClaim.client_request_id == client_request_id,
        )
    ).scalars().first()
    if existing is not None:
        return _claim_result(db, existing, user_id)

    plan = db.execute(select(Plan).where(Plan.code == code)).scalar_one_or_none()
    if plan is None:
        raise NotFound("Credit package not found.")
    if not is_credit_package(plan):
        raise PackageNotAcquirable()

    claim = CreditPackageClaim(
        user_id=user_id,
        plan_id=plan.id,
        plan_code=plan.code,
        credits_granted=0,
        fulfillment_mode=plan.fulfillment_mode,
        status=CreditPackageClaimStatus.pending.value,
        client_request_id=client_request_id,
    )
    db.add(claim)
    db.flush()

    if plan.fulfillment_mode == FulfillmentMode.free_dev.value:
        credits.grant(
            db,
            user_id,
            plan.included_credit_units,
            reference_type=CreditReferenceType.purchase,
            reference_id=claim.id,
            notes=f"credit package {plan.code} ({plan.fulfillment_mode})",
        )
        claim.credits_granted = plan.included_credit_units
        claim.status = CreditPackageClaimStatus.granted.value
        claim.granted_at = utcnow()
        db.commit()
        return _claim_result(db, claim, user_id)

    # Paid fulfillment is not implemented in this pass. Record the failed intent
    # so the audit trail is complete, then surface a clear error.
    claim.status = CreditPackageClaimStatus.failed.value
    claim.failure_reason = "store purchase not supported yet"
    db.commit()
    raise PackageNotAcquirable("Paid purchases aren't available yet.")

"""Credit-package catalog + acquisition.

Reuses the existing ``plans`` table (credit packs are ``kind = one_time`` plans
that grant ``included_credit_units``) and the ledger-based credit accounting.
Every acquisition is recorded as a ``CreditPackageClaim`` (audit trail +
idempotency) and credits are granted through the normal ledger path — even while
packages are free in the current ``free_dev`` phase.

Paid packs (``app_store_iap``) go through ``redeem_store_transaction``: the app
buys with StoreKit, we verify Apple's signed transaction and grant through the
same claim + ledger path. Refunds take the credits back.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.errors import AppError, NotFound, ValidationFailed
from app.core.config import settings
from app.db.models.credit_package_claim import CreditPackageClaim
from app.db.models.free_allowance_claim import FirstPurchaseBonusClaim
from app.db.models.enums import (
    CreditPackageClaimStatus,
    CreditReferenceType,
    FulfillmentMode,
    PlanKind,
)
from app.db.models.plan import Plan
from app.domain.billing import credits
from app.domain.billing.store import InvalidStoreTransaction, StoreVerifier, get_store_verifier


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


_CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}


def price_label(plan: Plan) -> str:
    """Human-facing price string, controlled by package metadata so it can change
    when packages become paid without any frontend change."""
    if plan.fulfillment_mode == FulfillmentMode.free_dev.value:
        return "Free for now"
    if plan.price_minor is not None and plan.currency_code:
        symbol = _CURRENCY_SYMBOLS.get(plan.currency_code)
        amount = f"{plan.price_minor / 100:.2f}"
        return f"{symbol}{amount}" if symbol else f"{amount} {plan.currency_code}"
    return "—"


def store_product_id(plan: Plan) -> str | None:
    return (plan.store_product_ids_json or {}).get("app_store")


def list_active_packages(db: Session) -> list[Plan]:
    """All packages shown in the Add Credits sheet, ordered for direct display."""
    plans = (
        db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order))
        .scalars()
        .all()
    )
    return [p for p in plans if is_credit_package(p)]


def _phone_hash(db: Session, user_id: uuid.UUID) -> str | None:
    from app.domain.users.service import get_primary_phone

    phone = get_primary_phone(db, user_id)
    return phone.phone_hash if phone else None


def first_purchase_bonus(db: Session, user_id: uuid.UUID) -> int:
    """Bonus credits this user's next store purchase would get (0 once used)."""
    bonus = settings.first_purchase_bonus_credits
    if bonus <= 0:
        return 0
    phone_hash = _phone_hash(db, user_id)
    if phone_hash is None or db.get(FirstPurchaseBonusClaim, phone_hash) is not None:
        return 0
    return bonus


def _claim_result(db: Session, claim: CreditPackageClaim, user_id: uuid.UUID) -> dict:
    return {
        "claim_id": str(claim.id),
        "status": claim.status,
        # Includes a first-purchase bonus, so refunds take that back too.
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

    # Paid packs are bought in the App Store and redeemed with the signed
    # transaction; this free path can't hand them out.
    claim.status = CreditPackageClaimStatus.failed.value
    claim.failure_reason = "paid package needs a store transaction"
    db.commit()
    raise PackageNotAcquirable("This package is bought in the App Store.")


class TransactionAlreadyRedeemed(AppError):
    code = "transaction_already_redeemed"
    http_status = 409
    default_message = "This purchase was already used on another account."


def redeem_store_transaction(
    db: Session,
    user_id: uuid.UUID,
    signed_transaction: str,
    verifier: StoreVerifier | None = None,
) -> dict:
    """Grant the credits of a verified App Store purchase. Idempotent per
    transaction: the app may send the same one again (e.g. after a crash before
    it finished the transaction) and gets the same claim back."""
    tx = (verifier or get_store_verifier()).verify_transaction(signed_transaction)
    if tx.revoked:
        raise InvalidStoreTransaction("This purchase was refunded.")
    if tx.app_account_token and tx.app_account_token.lower() != str(user_id).lower():
        raise TransactionAlreadyRedeemed()

    existing = db.execute(
        select(CreditPackageClaim).where(CreditPackageClaim.store_transaction_id == tx.transaction_id)
    ).scalars().first()
    if existing is not None:
        if existing.user_id != user_id:
            raise TransactionAlreadyRedeemed()
        return _claim_result(db, existing, user_id)

    plan = next((p for p in list_active_packages(db) if store_product_id(p) == tx.product_id), None)
    if plan is None or plan.fulfillment_mode != FulfillmentMode.app_store_iap.value:
        raise NotFound("No credit package for this product.")

    claim = CreditPackageClaim(
        user_id=user_id,
        plan_id=plan.id,
        plan_code=plan.code,
        credits_granted=plan.included_credit_units,
        fulfillment_mode=plan.fulfillment_mode,
        status=CreditPackageClaimStatus.granted.value,
        client_request_id=f"appstore:{tx.transaction_id}",
        store_transaction_id=tx.transaction_id,
        granted_at=utcnow(),
    )
    db.add(claim)
    db.flush()
    credits.grant(
        db,
        user_id,
        plan.included_credit_units,
        reference_type=CreditReferenceType.purchase,
        reference_id=claim.id,
        notes=f"App Store {tx.product_id} ({tx.transaction_id})",
    )
    bonus = first_purchase_bonus(db, user_id)
    if bonus:
        db.add(FirstPurchaseBonusClaim(phone_hash=_phone_hash(db, user_id)))
        credits.grant(
            db,
            user_id,
            bonus,
            reference_type=CreditReferenceType.purchase,
            reference_id=claim.id,
            notes="first purchase bonus",
        )
        claim.credits_granted += bonus
    db.commit()
    return _claim_result(db, claim, user_id)


def refund_store_transaction(db: Session, transaction_id: str) -> bool:
    """Take back the credits of a refunded purchase. The balance may go below
    zero if they were already spent; new requests are then refused until the
    user tops up. Returns False when there was nothing to refund."""
    claim = db.execute(
        select(CreditPackageClaim).where(CreditPackageClaim.store_transaction_id == transaction_id)
    ).scalars().first()
    if claim is None or claim.status != CreditPackageClaimStatus.granted.value:
        return False
    credits.refund(db, claim.user_id, claim.credits_granted, claim.id)
    claim.status = CreditPackageClaimStatus.refunded.value
    db.commit()
    return True

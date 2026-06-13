"""Reconcile requests/attempts stuck in non-terminal states for too long."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.db.models.enums import RequestStatus
from app.db.models.request import Request
from app.domain.billing import credits

logger = get_logger("worker.reconciliation")

# A request stuck mid-dispatch (worker died) — safe to fail + release credits.
DISPATCHING_TIMEOUT = timedelta(minutes=5)
# Accepted/active but never reported terminal by the provider.
INFLIGHT_TIMEOUT = timedelta(minutes=30)


def reconcile(db: Session, now=None) -> dict:
    now = now or utcnow()
    failed_dispatching = 0
    failed_inflight = 0

    stuck_dispatching = db.execute(
        select(Request).where(
            Request.status == RequestStatus.dispatching.value,
            Request.updated_at < now - DISPATCHING_TIMEOUT,
        )
    ).scalars().all()
    for req in stuck_dispatching:
        if req.credits_reserved:
            credits.release(db, req.user_id, req.credit_cost_units, req.id)
            req.credits_reserved = False
        req.status = RequestStatus.failed.value
        req.last_error_code = "internal_timeout"
        req.last_error_message = "Dispatch did not complete in time."
        req.updated_at = now
        failed_dispatching += 1

    stuck_inflight = db.execute(
        select(Request).where(
            Request.status.in_(
                [RequestStatus.provider_accepted.value, RequestStatus.active.value]
            ),
            Request.updated_at < now - INFLIGHT_TIMEOUT,
        )
    ).scalars().all()
    for req in stuck_inflight:
        # Credit already captured on acceptance; do not release.
        req.status = RequestStatus.failed.value
        req.last_error_code = "internal_timeout"
        req.last_error_message = "No terminal provider event received in time."
        req.updated_at = now
        failed_inflight += 1

    db.commit()
    result = {"failed_dispatching": failed_dispatching, "failed_inflight": failed_inflight}
    if failed_dispatching or failed_inflight:
        logger.info("reconciliation_swept", extra={"provider": "reconcile"})
    return result

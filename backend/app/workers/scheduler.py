"""Worker loop: dispatch due requests, reconcile, and periodically clean up."""
from __future__ import annotations

import time

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.workers import cleanup, dispatch, reconciliation

logger = get_logger("worker.scheduler")

DISPATCH_INTERVAL_SECONDS = 2
RECONCILE_EVERY_TICKS = 30   # ~1 min
CLEANUP_EVERY_TICKS = 1800   # ~1 hour


def tick(tick_no: int) -> None:
    db = SessionLocal()
    try:
        outcomes = dispatch.run_once(db)
        if outcomes:
            logger.info("dispatch_batch", extra={"provider": "scheduler"})
        if tick_no % RECONCILE_EVERY_TICKS == 0:
            reconciliation.reconcile(db)
        if tick_no % CLEANUP_EVERY_TICKS == 0:
            cleanup.cleanup(db)
    finally:
        db.close()


def run_forever() -> None:  # pragma: no cover - long-running loop
    logger.info("worker_started", extra={"provider": "scheduler"})
    tick_no = 0
    while True:
        tick_no += 1
        try:
            tick(tick_no)
        except Exception:
            logger.exception("worker_tick_failed", extra={"provider": "scheduler"})
        time.sleep(DISPATCH_INTERVAL_SECONDS)

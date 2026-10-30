"""Worker process entrypoint: ``python -m app.workers.run``."""
from __future__ import annotations

from app.core.config import assert_deployable
from app.core.logging import configure_logging
from app.workers.scheduler import run_forever

if __name__ == "__main__":  # pragma: no cover
    configure_logging()
    assert_deployable()
    run_forever()

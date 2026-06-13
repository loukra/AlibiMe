"""Worker process entrypoint: ``python -m app.workers.run``."""
from __future__ import annotations

from app.workers.scheduler import run_forever

if __name__ == "__main__":  # pragma: no cover
    run_forever()

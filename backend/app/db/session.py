"""Engine + session management."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _make_engine(url: str) -> Engine:
    connect_args = {}
    if url.startswith("sqlite"):
        # Allow use across threads (uvicorn workers / tests) and shorten lock waits.
        connect_args = {"check_same_thread": False}
    engine = create_engine(
        url,
        future=True,
        pool_pre_ping=not url.startswith("sqlite"),
        connect_args=connect_args,
    )
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _):  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _make_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

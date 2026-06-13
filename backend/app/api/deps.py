"""FastAPI dependencies: DB session + current authenticated user/session."""
from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.errors import Unauthorized
from app.db.session import get_db as _get_db
from app.domain.auth import service as auth_service
from app.db.models.user import User
from app.db.models.user_session import UserSession


def get_db() -> Iterator[Session]:
    yield from _get_db()


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        raise Unauthorized("Missing Authorization header.")
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


class CurrentContext:
    def __init__(self, user: User, session: UserSession):
        self.user = user
        self.session = session


def get_current_context(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentContext:
    token = _extract_token(authorization)
    user, session = auth_service.resolve_session(db, token)
    return CurrentContext(user=user, session=session)

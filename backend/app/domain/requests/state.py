"""Request status transition guards."""
from __future__ import annotations

from app.core.errors import AppError
from app.db.models.enums import RequestStatus

# Allowed forward transitions for a request.
_ALLOWED: dict[str, set[str]] = {
    RequestStatus.scheduled.value: {
        RequestStatus.dispatching.value,
        RequestStatus.canceled.value,
        RequestStatus.expired.value,
    },
    RequestStatus.dispatching.value: {
        RequestStatus.provider_accepted.value,
        RequestStatus.active.value,
        RequestStatus.failed.value,
        RequestStatus.scheduled.value,  # retry: back to scheduled for re-dispatch
        RequestStatus.canceled.value,
    },
    RequestStatus.provider_accepted.value: {
        RequestStatus.active.value,
        RequestStatus.completed.value,
        RequestStatus.failed.value,
    },
    RequestStatus.active.value: {
        RequestStatus.completed.value,
        RequestStatus.failed.value,
    },
    # terminal states
    RequestStatus.completed.value: set(),
    RequestStatus.failed.value: set(),
    RequestStatus.canceled.value: set(),
    RequestStatus.expired.value: set(),
}

# A request can be canceled via the API only before the provider has accepted it.
# We treat `scheduled` as the safe cancelable window; once `dispatching`, the
# worker holds a row lock and cancellation is best-effort at the provider.
CANCELABLE_STATUSES = {RequestStatus.scheduled.value}


class InvalidTransition(AppError):
    code = "invalid_transition"
    http_status = 409
    default_message = "Invalid request state transition."


def can_transition(old: str, new: str) -> bool:
    return new in _ALLOWED.get(old, set())


def assert_transition(old: str, new: str) -> None:
    if old == new:
        return
    if not can_transition(old, new):
        raise InvalidTransition(f"Cannot transition request from '{old}' to '{new}'.")


def is_cancelable(status: str) -> bool:
    return status in CANCELABLE_STATUSES

import pytest

from app.db.models.enums import RequestStatus
from app.domain.requests import state


def test_allowed_transition():
    assert state.can_transition(
        RequestStatus.scheduled.value, RequestStatus.dispatching.value
    )


def test_disallowed_transition_raises():
    with pytest.raises(state.InvalidTransition):
        state.assert_transition(
            RequestStatus.completed.value, RequestStatus.active.value
        )


def test_same_status_is_noop():
    state.assert_transition(RequestStatus.active.value, RequestStatus.active.value)


def test_cancelable_only_when_scheduled():
    assert state.is_cancelable(RequestStatus.scheduled.value)
    assert not state.is_cancelable(RequestStatus.provider_accepted.value)
    assert not state.is_cancelable(RequestStatus.completed.value)


def test_terminal_states_have_no_exits():
    for terminal in (
        RequestStatus.completed.value,
        RequestStatus.failed.value,
        RequestStatus.canceled.value,
        RequestStatus.expired.value,
    ):
        assert not state.can_transition(terminal, RequestStatus.active.value)

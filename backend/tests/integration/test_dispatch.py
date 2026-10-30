from datetime import timedelta

from sqlalchemy import select

from app.core.clock import utcnow
from app.db.models.attempts import CallAttempt, MessageAttempt
from app.db.models.request import Request
from app.db.session import SessionLocal
from app.providers.voice.mock import MockVoiceCallProvider
from app.workers import dispatch
from tests.conftest import get_template_id, signup


def _create_call(client, headers, template="boss_travel_assignment", crid="c1"):
    tid = get_template_id(client, headers, template)
    return client.post(
        "/v1/requests",
        headers=headers,
        json={"client_request_id": crid, "template_id": tid, "channel": "call", "delay_seconds": 0},
    ).json()["request_id"]


def _create_sms(client, headers, crid="c1"):
    tid = get_template_id(client, headers, "safety_checkin")
    return client.post(
        "/v1/requests",
        headers=headers,
        json={"client_request_id": crid, "template_id": tid, "channel": "sms", "delay_seconds": 0},
    ).json()["request_id"]


def _run_dispatch(**kwargs):
    db = SessionLocal()
    try:
        return dispatch.run_once(db, now=utcnow() + timedelta(seconds=5), **kwargs)
    finally:
        db.close()


def test_dispatch_call_success(client, db):
    a = signup(client)
    rid = _create_call(client, a["headers"])
    outcomes = _run_dispatch()
    assert outcomes == ["dispatched"]

    db.expire_all()
    req = db.get(Request, __import__("uuid").UUID(rid))
    assert req.status == "provider_accepted"
    assert req.credits_reserved is True
    assert req.request_plan_snapshot_json["template_code"] == "boss_travel_assignment"
    attempt = db.execute(
        select(CallAttempt).where(CallAttempt.request_id == req.id)
    ).scalar_one()
    assert attempt.provider_call_id


def test_dispatch_sms_success(client, db):
    a = signup(client)
    rid = _create_sms(client, a["headers"])
    outcomes = _run_dispatch()
    assert outcomes == ["dispatched"]
    db.expire_all()
    req = db.get(Request, __import__("uuid").UUID(rid))
    assert req.status == "provider_accepted"
    attempt = db.execute(
        select(MessageAttempt).where(MessageAttempt.request_id == req.id)
    ).scalar_one()
    assert attempt.provider_message_id


def test_dispatch_retries_transient_pre_dial_failure(client, db):
    a = signup(client)
    rid = _create_call(client, a["headers"])
    # Fail the first create_outbound_call, succeed on the retry.
    provider = MockVoiceCallProvider(fail_pre_dial_times=1)
    outcomes = _run_dispatch(voice_provider=provider)
    assert outcomes == ["dispatched"]

    db.expire_all()
    req = db.get(Request, __import__("uuid").UUID(rid))
    assert req.status == "provider_accepted"
    attempts = db.execute(
        select(CallAttempt).where(CallAttempt.request_id == req.id)
    ).scalars().all()
    assert len(attempts) == 2  # one failed pre-dial + one accepted


def test_dispatch_exhausts_retries_then_fails_and_releases_credit(client, db):
    a = signup(client)
    rid = _create_call(client, a["headers"])
    provider = MockVoiceCallProvider(fail_pre_dial_times=5)  # always fails
    outcomes = _run_dispatch(voice_provider=provider)
    assert outcomes == ["failed"]

    db.expire_all()
    req = db.get(Request, __import__("uuid").UUID(rid))
    assert req.status == "failed"
    assert req.last_error_code == "provider_unavailable"
    assert req.credits_reserved is False  # released

    # Credit was released, so balance is back to the free allowance.
    me = client.get("/v1/me", headers=a["headers"]).json()
    assert me["credits_available"] == 3


def test_scheduled_future_request_not_dispatched_early(client, db):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 300},
    )
    # Dispatch "now" — the request executes in 5 minutes, so nothing is claimed.
    db2 = SessionLocal()
    try:
        outcomes = dispatch.run_once(db2, now=utcnow())
    finally:
        db2.close()
    assert outcomes == []


class _CapturingVoice(MockVoiceCallProvider):
    def create_outbound_call(self, plan):
        self.plan = plan
        return super().create_outbound_call(plan)


def test_cross_border_call_is_capped_to_one_billed_minute(client, db):
    # Default test phone is German, the seeded sender line is a US number.
    a = signup(client)
    _create_call(client, a["headers"])  # boss template allows 90 s
    voice = _CapturingVoice()
    _run_dispatch(voice_provider=voice)
    assert voice.plan.max_duration_seconds == 55


def test_same_country_call_keeps_template_length(client, db):
    a = signup(client, phone="+14155550199")
    _create_call(client, a["headers"])
    voice = _CapturingVoice()
    _run_dispatch(voice_provider=voice)
    assert voice.plan.max_duration_seconds == 90

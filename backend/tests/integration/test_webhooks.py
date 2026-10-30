import uuid
from datetime import timedelta

from sqlalchemy import select

from app.core.clock import utcnow
from app.db.models.attempts import CallAttempt, MessageAttempt
from app.db.session import SessionLocal
from app.providers.messaging.mock import MockMessageProvider
from app.providers.voice.mock import MockVoiceCallProvider
from app.workers import dispatch
from tests.conftest import get_template_id, signup


def _dispatch_now():
    db = SessionLocal()
    try:
        return dispatch.run_once(db, now=utcnow() + timedelta(seconds=5))
    finally:
        db.close()


def _provider_call_id(rid: str) -> str:
    db = SessionLocal()
    try:
        a = db.execute(
            select(CallAttempt).where(CallAttempt.request_id == uuid.UUID(rid))
        ).scalars().first()
        return a.provider_call_id
    finally:
        db.close()


def _provider_message_id(rid: str) -> str:
    db = SessionLocal()
    try:
        a = db.execute(
            select(MessageAttempt).where(MessageAttempt.request_id == uuid.UUID(rid))
        ).scalars().first()
        return a.provider_message_id
    finally:
        db.close()


def test_voice_webhook_drives_request_to_completed(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    rid = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 0},
    ).json()["request_id"]
    _dispatch_now()

    call_id = _provider_call_id(rid)
    for event in MockVoiceCallProvider.simulate_lifecycle(call_id, duration_seconds=30):
        resp = client.post("/v1/webhooks/voice", json=event)
        assert resp.status_code == 200

    detail = client.get(f"/v1/requests/{rid}", headers=a["headers"]).json()
    assert detail["status"] == "completed"
    assert detail["latest_attempt"]["duration_seconds"] == 30


def test_sms_webhook_drives_request_to_completed(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "safety_checkin")
    rid = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "sms", "delay_seconds": 0},
    ).json()["request_id"]
    _dispatch_now()

    msg_id = _provider_message_id(rid)
    for event in MockMessageProvider.simulate_lifecycle(msg_id):
        assert client.post("/v1/webhooks/sms", json=event).status_code == 200

    detail = client.get(f"/v1/requests/{rid}", headers=a["headers"]).json()
    assert detail["status"] == "completed"


def test_webhook_is_idempotent(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    rid = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 0},
    ).json()["request_id"]
    _dispatch_now()
    call_id = _provider_call_id(rid)

    event = {
        "event_id": "evt-dup-1",
        "type": "call.completed",
        "provider_call_id": call_id,
        "duration_seconds": 12,
        "ended_reason": "completed",
    }
    first = client.post("/v1/webhooks/voice", json=event)
    second = client.post("/v1/webhooks/voice", json=event)
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"


def test_unanswered_call_resolves_to_no_answer(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    rid = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "na1", "template_id": tid, "channel": "call", "delay_seconds": 0},
    ).json()["request_id"]
    _dispatch_now()

    call_id = _provider_call_id(rid)
    # Rang, then ended unanswered (DND / declined).
    for event in [
        {"event_id": f"na-{call_id}-1", "type": "call.ringing", "provider_call_id": call_id},
        {"event_id": f"na-{call_id}-2", "type": "call.completed", "provider_call_id": call_id,
         "ended_reason": "customer-did-not-answer"},
    ]:
        assert client.post("/v1/webhooks/voice", json=event).status_code == 200

    detail = client.get(f"/v1/requests/{rid}", headers=a["headers"]).json()
    assert detail["status"] == "no_answer"


def test_stored_webhook_keeps_no_transcript_text_or_numbers(client):
    """Provider reports can carry the transcript, the message text and phone
    numbers; the webhook log keeps only the parsed fields."""
    from app.db.models.webhook_event import WebhookEvent

    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    rid = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c-raw", "template_id": tid, "channel": "call", "delay_seconds": 0},
    ).json()["request_id"]
    _dispatch_now()

    call_id = _provider_call_id(rid)
    for event in MockVoiceCallProvider.simulate_lifecycle(call_id, duration_seconds=30):
        event = {**event, "transcript": "User: I really have to go.",
                 "customer": {"number": "+491701234567"}}
        assert client.post("/v1/webhooks/voice", json=event).status_code == 200

    db = SessionLocal()
    try:
        stored = db.execute(select(WebhookEvent.payload_json)).scalars().all()
    finally:
        db.close()
    assert stored
    for payload in stored:
        assert set(payload) == {"provider_ref_id", "mapped_status", "fields"}
        assert "I really have to go" not in str(payload)
        assert "+491701234567" not in str(payload)

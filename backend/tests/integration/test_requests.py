from datetime import timedelta

from app.core.clock import utcnow
from tests.conftest import get_template_id, signup


def _boss(client, headers):
    return get_template_id(client, headers, "boss_travel_assignment")


def test_create_immediate_call(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 0},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "scheduled"
    assert body["channel"] == "call"
    assert body["credits_available"] == 3
    assert body["cancelable"] is True


def test_create_immediate_sms(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "safety_checkin")
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "sms", "delay_seconds": 0},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["channel"] == "sms"


def test_create_delayed_request(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 30},
    )
    assert resp.status_code == 201
    rid = resp.json()["request_id"]
    detail = client.get(f"/v1/requests/{rid}", headers=a["headers"]).json()
    assert detail["scheduled_kind"] == "delayed"


def test_create_exact_time_request(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    when = (utcnow() + timedelta(hours=2)).isoformat()
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "scheduled_at": when},
    )
    assert resp.status_code == 201, resp.text
    rid = resp.json()["request_id"]
    detail = client.get(f"/v1/requests/{rid}", headers=a["headers"]).json()
    assert detail["scheduled_kind"] == "exact_time"


def test_exact_time_out_of_window_rejected(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    when = (utcnow() + timedelta(hours=25)).isoformat()
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "scheduled_at": when},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_schedule_window"


def test_both_timing_modes_rejected(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    when = (utcnow() + timedelta(hours=2)).isoformat()
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={
            "client_request_id": "c1", "template_id": tid, "channel": "call",
            "delay_seconds": 30, "scheduled_at": when,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_invalid_delay_value_rejected(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 17},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_idempotent_create(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    payload = {"client_request_id": "same", "template_id": tid, "channel": "call", "delay_seconds": 0}
    r1 = client.post("/v1/requests", headers=a["headers"], json=payload)
    r2 = client.post("/v1/requests", headers=a["headers"], json=payload)
    assert r1.json()["request_id"] == r2.json()["request_id"]


def test_cancel_scheduled_request(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    rid = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 300},
    ).json()["request_id"]
    resp = client.post(f"/v1/requests/{rid}/cancel", headers=a["headers"])
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"


def test_multiple_pending_allowed_then_capped(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    # Several pending jobs can coexist (a queue).
    for i in range(3):
        r = client.post(
            "/v1/requests",
            headers=a["headers"],
            json={"client_request_id": f"c{i}", "template_id": tid, "channel": "call", "delay_seconds": 300},
        )
        assert r.status_code == 201, r.text
    # Over the cap is rejected.
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c9", "template_id": tid, "channel": "call", "delay_seconds": 300},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "active_request_exists"


def test_history_lists_requests(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 300},
    )
    resp = client.get("/v1/history", headers=a["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["channel"] == "call"


def test_history_exposes_pending_with_execute_at_and_cancelable(client):
    a = signup(client)
    tid = _boss(client, a["headers"])
    client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "p1", "template_id": tid, "channel": "call", "delay_seconds": 300},
    )
    items = client.get("/v1/history", headers=a["headers"]).json()["items"]
    pending = next(i for i in items if i["final_status"] == "scheduled")
    assert pending["execute_at"]
    assert pending["cancelable"] is True


def test_me_says_whether_anything_was_sent(client):
    # The app walks a new user through a first alibi until this turns true.
    a = signup(client)
    assert client.get("/v1/me", headers=a["headers"]).json()["has_requests"] is False
    tid = get_template_id(client, a["headers"], "safety_checkin")
    client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "sms", "delay_seconds": 300},
    )
    assert client.get("/v1/me", headers=a["headers"]).json()["has_requests"] is True

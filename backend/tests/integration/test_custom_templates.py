"""Custom templates: structured creation, scoping, validation, dispatch reuse."""
from tests.conftest import signup


def _create(client, headers, **overrides):
    body = {
        "display_name": "My boss call",
        "category": "work",
        "persona": "boss",
        "reason": "urgent_work_issue",
        "urgency": "high",
        "channels": ["call", "sms"],
        "voice_style": "neutral",
        "call_max_seconds": 60,
    }
    body.update(overrides)
    return client.post("/v1/templates", headers=headers, json=body)


def test_options_lists_allowed_choices(client):
    a = signup(client)
    resp = client.get("/v1/templates/options", headers=a["headers"])
    assert resp.status_code == 200, resp.text
    opts = resp.json()
    persona_codes = {p["code"] for p in opts["personas"]}
    assert {"boss", "best_friend"} <= persona_codes
    assert opts["personas"][0]["label"]  # localized label present
    assert "call" in opts["channels"] and "sms" in opts["channels"]
    assert opts["call_seconds_min"] <= opts["call_seconds_default"] <= opts["call_seconds_max"]


def test_create_custom_template_composes_both_channels(client):
    a = signup(client)
    resp = _create(client, a["headers"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_custom"] is True
    assert set(body["supported_channels"]) == {"call", "sms"}
    # Wording is composed from approved skeletons (persona/reason filled in).
    assert body["preview_opening_line"] and "manager" in body["preview_opening_line"]
    assert body["preview_sms_body"]
    assert body["call_max_duration_seconds"] == 60


def test_custom_template_appears_only_for_owner(client):
    a = signup(client)
    _create(client, a["headers"], display_name="Owner only")
    # Owner sees system + their custom.
    mine = client.get("/v1/templates", headers=a["headers"]).json()["templates"]
    assert any(t["display_name"] == "Owner only" and t["is_custom"] for t in mine)

    b = signup(client, phone="+491700000002")
    theirs = client.get("/v1/templates", headers=b["headers"]).json()["templates"]
    assert all(not t["is_custom"] for t in theirs)
    assert not any(t["display_name"] == "Owner only" for t in theirs)


def test_create_rejects_unknown_persona(client):
    a = signup(client)
    resp = _create(client, a["headers"], persona="celebrity")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_create_rejects_empty_channels(client):
    a = signup(client)
    resp = _create(client, a["headers"], channels=[])
    assert resp.status_code == 422


def test_call_only_custom_template_cannot_be_texted(client):
    a = signup(client)
    created = _create(client, a["headers"], channels=["call"]).json()
    assert created["supported_channels"] == ["call"]
    assert created["preview_sms_body"] is None

    # Scheduling it as SMS is rejected (existing channel validation).
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={
            "client_request_id": "co-1",
            "template_id": created["id"],
            "channel": "sms",
            "delay_seconds": 0,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "template_channel_not_supported"


def test_custom_template_dispatches_via_existing_pipeline(client):
    a = signup(client)
    created = _create(client, a["headers"], channels=["call"]).json()
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={
            "client_request_id": "co-2",
            "template_id": created["id"],
            "channel": "call",
            "delay_seconds": 0,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] in ("scheduled", "dispatching", "provider_accepted")


def test_delete_custom_template(client):
    a = signup(client)
    created = _create(client, a["headers"]).json()
    assert client.delete(f"/v1/templates/{created['id']}", headers=a["headers"]).status_code == 204
    remaining = client.get("/v1/templates", headers=a["headers"]).json()["templates"]
    assert not any(t["id"] == created["id"] for t in remaining)


def test_cannot_delete_system_template(client):
    a = signup(client)
    system = next(
        t for t in client.get("/v1/templates", headers=a["headers"]).json()["templates"]
        if not t["is_custom"]
    )
    assert client.delete(f"/v1/templates/{system['id']}", headers=a["headers"]).status_code == 404

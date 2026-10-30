"""Custom templates: structured creation, scoping, validation, dispatch reuse."""
from tests.conftest import signup


def _create(client, headers, **overrides):
    body = {
        "display_name": "My boss call",
        "category": "work",
        "persona": "manager",
        "reason": "work_urgent_task",
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
    assert {"manager", "best_friend"} <= persona_codes
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
    # Wording is composed from approved skeletons. The caller never names their
    # role: the saved contact shows who is calling.
    assert body["preview_opening_line"]
    assert "manager" not in body["preview_opening_line"]
    assert body["preview_sms_body"] and "manager" not in body["preview_sms_body"]
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


def _catalog(client, headers):
    return client.get("/v1/templates", headers=headers).json()["templates"]


def _boss(client, headers):
    return next(t for t in _catalog(client, headers) if t["code"] == "boss_travel_assignment")


def _edit_body(choices, **changes):
    body = {k: v for k, v in choices.items() if v is not None}
    body.update(changes)
    return body


def test_every_template_carries_the_editor_choices(client):
    a = signup(client)
    boss = _boss(client, a["headers"])
    # A built-in maps onto the editor's catalog.
    assert boss["choices"]["persona"] == "manager"
    assert boss["choices"]["reason"] == "work_travel_assignment"
    assert boss["choices"]["category"] == "work"
    assert set(boss["choices"]["channels"]) == set(boss["supported_channels"])
    own = _create(client, a["headers"], urgency="immediate").json()
    assert own["choices"]["urgency"] == "immediate"
    assert own["choices"]["call_max_seconds"] == 60


def test_edit_own_template(client):
    a = signup(client)
    own = _create(client, a["headers"]).json()
    resp = client.put(
        f"/v1/templates/{own['id']}",
        headers=a["headers"],
        json=_edit_body(own["choices"], display_name="Renamed", channels=["sms"]),
    )
    assert resp.status_code == 200, resp.text
    edited = resp.json()
    assert edited["id"] == own["id"] and edited["is_custom"] is True
    assert edited["display_name"] == "Renamed"
    assert edited["supported_channels"] == ["sms"]
    names = [t["display_name"] for t in _catalog(client, a["headers"])]
    assert "Renamed" in names and "My boss call" not in names


def test_cannot_edit_another_users_template(client):
    a = signup(client)
    own = _create(client, a["headers"]).json()
    b = signup(client, phone="+491700000002")
    resp = client.put(
        f"/v1/templates/{own['id']}", headers=b["headers"], json=_edit_body(own["choices"])
    )
    assert resp.status_code == 404


def test_cannot_request_another_users_template(client):
    a = signup(client)
    own = _create(client, a["headers"]).json()
    b = signup(client, phone="+491700000002")
    resp = client.post(
        "/v1/requests",
        headers=b["headers"],
        json={"client_request_id": "x-1", "template_id": own["id"], "channel": "call",
              "delay_seconds": 0},
    )
    assert resp.status_code == 404


def test_editing_a_built_in_replaces_it_for_that_user_only(client):
    a = signup(client)
    boss = _boss(client, a["headers"])
    resp = client.put(
        f"/v1/templates/{boss['id']}",
        headers=a["headers"],
        json=_edit_body(boss["choices"], display_name="Boss, my way", urgency="immediate"),
    )
    assert resp.status_code == 200, resp.text
    copy = resp.json()
    assert copy["id"] != boss["id"]
    assert copy["is_custom"] is False and copy["is_edited"] is True
    assert copy["original_id"] == boss["id"]
    assert copy["category"] == boss["category"]

    mine = _catalog(client, a["headers"])
    assert [t["id"] for t in mine if t["display_name"] == "Boss, my way"] == [copy["id"]]
    assert not any(t["id"] == boss["id"] for t in mine)

    # Editing it again (by either id) updates the same copy.
    again = client.put(
        f"/v1/templates/{boss['id']}",
        headers=a["headers"],
        json=_edit_body(copy["choices"], display_name="Boss, again"),
    ).json()
    assert again["id"] == copy["id"]
    assert sum(1 for t in _catalog(client, a["headers"]) if t["is_edited"]) == 1

    b = signup(client, phone="+491700000002")
    assert _boss(client, b["headers"])["display_name"] == boss["display_name"]


def test_reset_brings_the_built_in_back(client):
    a = signup(client)
    boss = _boss(client, a["headers"])
    copy = client.put(
        f"/v1/templates/{boss['id']}",
        headers=a["headers"],
        json=_edit_body(boss["choices"], display_name="Boss, my way"),
    ).json()
    # Use the copy once, so past requests still point at it after the reset.
    used = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "r-1", "template_id": copy["id"], "channel": "call",
              "delay_seconds": 300},
    )
    assert used.status_code == 201, used.text

    assert client.delete(f"/v1/templates/{copy['id']}", headers=a["headers"]).status_code == 204
    mine = _catalog(client, a["headers"])
    assert _boss(client, a["headers"])["id"] == boss["id"]
    assert not any(t["is_edited"] for t in mine)
    history = client.get("/v1/history", headers=a["headers"])
    assert history.status_code == 200

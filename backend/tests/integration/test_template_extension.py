"""Extended custom templates (richer fields + user context profile)."""
from tests.conftest import signup


def _create(client, headers, **overrides):
    body = {
        "display_name": "Leave the date",
        "category": "social_exit",
        "persona": "roommate",
        "reason": "home_problem",
        "channels": ["call", "sms"],
        "urgency": "high",
        "outcome": "leave_now",
        "setting": "date",
        "tone": "apologetic",
        "detail_profile": "contextual",
        "discretion_level": "public_safe",
        "formality": "casual",
        "expected_response": "say_on_my_way",
        "followup_behavior": "one_touch_only",
        "continuity_scope": "one_off",
        "context_modules": ["home"],
    }
    body.update(overrides)
    return client.post("/v1/templates", headers=headers, json=body)


def test_options_includes_new_catalogs(client):
    a = signup(client)
    opts = client.get("/v1/templates/options", headers=a["headers"]).json()
    for key in ("outcomes", "settings", "tones", "detail_profiles", "discretion_levels",
                "expected_responses", "followup_behaviors", "continuity_scopes",
                "context_modules", "profile"):
        assert key in opts, key
    assert "work_industries" in opts["profile"]
    assert {p["code"] for p in opts["personas"]} >= {"manager", "roommate", "partner"}


def test_create_with_rich_fields(client):
    a = signup(client)
    resp = _create(client, a["headers"])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["is_custom"] is True
    assert set(body["supported_channels"]) == {"call", "sms"}
    # Outcome drives the ask.
    assert "head out now" in (body["preview_opening_line"] or "")


def test_create_rejects_bad_outcome(client):
    a = signup(client)
    resp = _create(client, a["headers"], outcome="teleport")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_context_profile_get_default_empty(client):
    a = signup(client)
    prof = client.get("/v1/me/context-profile", headers=a["headers"]).json()
    assert prof["work_industry_code"] is None
    assert prof["home_responsibility_codes_json"] is None


def test_context_profile_put_and_partial_update(client):
    a = signup(client)
    # Set work + home.
    r1 = client.put("/v1/me/context-profile", headers=a["headers"], json={
        "work_setting_code": "site_field",
        "living_setup_code": "with_roommate",
        "home_responsibility_codes_json": ["pets", "deliveries"],
    })
    assert r1.status_code == 200, r1.text
    assert r1.json()["work_setting_code"] == "site_field"

    # Partial update must not clear the untouched field.
    r2 = client.put("/v1/me/context-profile", headers=a["headers"], json={
        "family_proximity_code": "nearby",
    })
    body = r2.json()
    assert body["family_proximity_code"] == "nearby"
    assert body["work_setting_code"] == "site_field"  # preserved
    assert body["home_responsibility_codes_json"] == ["pets", "deliveries"]


def test_context_profile_rejects_invalid_code(client):
    a = signup(client)
    resp = client.put("/v1/me/context-profile", headers=a["headers"],
                      json={"work_setting_code": "moon_base"})
    assert resp.status_code == 422


def test_context_profile_anchor_flows_into_composition(client):
    a = signup(client)
    client.put("/v1/me/context-profile", headers=a["headers"],
               json={"living_setup_code": "with_roommate"})
    # persona=partner so "roommate" can only come from the home anchor, not the
    # caller greeting. detail_profile=contextual + context_modules=[home].
    created = _create(client, a["headers"], persona="partner").json()
    assert "roommate" in (created["preview_opening_line"] or "").lower()


def test_no_profile_falls_back_to_generic(client):
    a = signup(client)
    # No profile set; same template still composes (generic, no anchor).
    created = _create(client, a["headers"], persona="partner", context_modules=["home"]).json()
    assert created["preview_opening_line"]
    assert "roommate" not in (created["preview_opening_line"] or "").lower()


def test_call_variables_threaded_to_plan(client, db):
    """A dispatched call carries the full coded-parameter + context variable set."""
    import uuid
    from app.db.models.request import Request
    from app.workers.dispatch import _build_plan, _resolve_dispatch_identity

    a = signup(client)
    # Set some context so it flows into the variables.
    client.put("/v1/me/context-profile", headers=a["headers"],
               json={"work_setting_code": "site_field"})
    created = _create(client, a["headers"], persona="manager", reason="work_urgent_task",
                      category="work", context_modules=["work"], channels=["call"]).json()
    resp = client.post("/v1/requests", headers=a["headers"], json={
        "client_request_id": "cv-1", "template_id": created["id"],
        "channel": "call", "delay_seconds": 0,
    })
    rid = uuid.UUID(resp.json()["request_id"])

    db.expire_all()
    request = db.get(Request, rid)
    identity = _resolve_dispatch_identity(db, request)
    plan = _build_plan(db, request, identity)
    v = plan.call_variables
    assert v["caller_label"]
    assert v["reason_summary"]
    assert v["outcome"] == "leave now"        # from the rich draft
    assert v["forbidden_facts"]
    assert "site field" in v["user_context"]  # profile anchor surfaced
    assert v["target_turn_count"]

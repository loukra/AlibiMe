"""Contract tests: OpenAPI generation + stable response shapes for the iOS client."""
from tests.conftest import get_template_id, signup


def test_openapi_schema_generates(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]
    for path in (
        "/v1/auth/phone/start",
        "/v1/auth/phone/confirm",
        "/v1/requests",
        "/v1/templates",
        "/v1/history",
        "/v1/entitlements",
        "/v1/credit-packages",
        "/v1/webhooks/voice",
    ):
        assert path in paths


def test_health_endpoints(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_create_request_response_shape(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 0},
    )
    body = resp.json()
    assert set(body.keys()) == {
        "request_id", "channel", "status", "execute_at", "credits_available",
        "cancelable", "sender_identity",
    }
    # A call request resolves no SMS sender binding in this pass.
    assert body["sender_identity"] is None


def test_error_envelope_shape(client):
    resp = client.get("/v1/me")  # unauthenticated
    body = resp.json()
    assert set(body["error"].keys()) == {"code", "message", "retryable", "request_id"}


def test_templates_catalog_shape(client):
    a = signup(client)
    resp = client.get("/v1/templates", headers=a["headers"])
    templates = resp.json()["templates"]
    assert len(templates) == 6
    sample = templates[0]
    for key in (
        "id", "code", "display_name", "category", "caller_persona",
        "reason_code", "supported_channels",
        "sender_persona_key", "sender_display_name", "supports_contact_save",
    ):
        assert key in sample

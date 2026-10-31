from app.providers.otp.mock import MOCK_OTP_CODE
from tests.conftest import DEFAULT_PHONE, signup


def test_start_returns_verification(client):
    resp = client.post(
        "/v1/auth/phone/start",
        json={"phone_number": DEFAULT_PHONE, "device_id": "d1", "locale": "en"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verification_id"]
    assert body["channel"] == "sms"
    assert body["expires_in_seconds"] > 0


def test_confirm_creates_session_and_masks_phone(client):
    start = client.post("/v1/auth/phone/start", json={"phone_number": DEFAULT_PHONE})
    vid = start.json()["verification_id"]
    resp = client.post(
        "/v1/auth/phone/confirm", json={"verification_id": vid, "code": MOCK_OTP_CODE}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_token"]
    assert body["user"]["phone_number_masked"].startswith("+49")
    assert "*" in body["user"]["phone_number_masked"]


def test_confirm_wrong_code_rejected(client):
    start = client.post("/v1/auth/phone/start", json={"phone_number": DEFAULT_PHONE})
    vid = start.json()["verification_id"]
    resp = client.post("/v1/auth/phone/confirm", json={"verification_id": vid, "code": "000000"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_failed"


def test_me_returns_free_credits(client):
    a = signup(client)
    resp = client.get("/v1/me", headers=a["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["credits_available"] == 3
    assert body["phone_number_masked"].startswith("+49")
    assert body["active_request"] is None


def test_logout_revokes_session(client):
    a = signup(client)
    assert client.post("/v1/auth/logout", headers=a["headers"]).status_code == 200
    resp = client.get("/v1/me", headers=a["headers"])
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_relogin_reuses_same_user(client):
    a1 = signup(client)
    a2 = signup(client)
    assert a1["user_id"] == a2["user_id"]


def test_unauthenticated_me_is_401(client):
    resp = client.get("/v1/me")
    assert resp.status_code == 401


def test_me_says_what_a_call_and_a_text_cost(client, auth):
    costs = client.get("/v1/me", headers=auth["headers"]).json()["credit_costs"]
    assert costs == {"call": 1, "sms": 1}  # the test env charges one credit each

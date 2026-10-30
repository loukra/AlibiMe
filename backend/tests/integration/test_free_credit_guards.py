"""Free credits: none for virtual numbers, and once per iPhone with DeviceCheck."""
from __future__ import annotations

import pytest

from app.providers import device_check as dc
from app.providers.otp.mock import MOCK_OTP_CODE
from tests.conftest import DEFAULT_PHONE, SECOND_PHONE, signup

VOIP_PHONE = "+445612345678"  # a UK 056 number, VoIP by its range


def _balance(client, headers) -> int:
    return client.get("/v1/me", headers=headers).json()["credits_available"]


def _signup_with(client, phone: str, *, device_id: str = "test-device", token: str | None = None) -> dict:
    start = client.post("/v1/auth/phone/start", json={"phone_number": phone, "device_id": device_id})
    assert start.status_code == 200, start.text
    body = {"verification_id": start.json()["verification_id"], "code": MOCK_OTP_CODE,
            "device_id": device_id}
    if token is not None:
        body["device_check_token"] = token
    confirm = client.post("/v1/auth/phone/confirm", json=body)
    assert confirm.status_code == 200, confirm.text
    return {"Authorization": f"Bearer {confirm.json()['session_token']}"}


@pytest.fixture
def device_check(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "device_check", "mock")
    dc._mock_claimed.clear()
    yield
    dc._mock_claimed.clear()


def test_virtual_number_signs_up_without_free_credits(client):
    headers = _signup_with(client, VOIP_PHONE)
    assert _balance(client, headers) == 0


def test_carrier_lookup_overrides_the_number_range(client, monkeypatch):
    from app.providers.otp.mock import MockOtpProvider
    from app.providers.types import NumberLookup

    monkeypatch.setattr(MockOtpProvider, "lookup_number",
                        lambda self, e164: NumberLookup(valid=True, line_type="non_fixed_voip"))
    headers = _signup_with(client, DEFAULT_PHONE)  # a mobile range, but the carrier says VoIP
    assert _balance(client, headers) == 0


def test_without_device_check_mobile_numbers_still_get_free_credits(client):
    assert _balance(client, signup(client)["headers"]) == 3


def test_second_number_on_the_same_iphone_gets_none(client, device_check):
    first = _signup_with(client, DEFAULT_PHONE, token="iphone-a")
    second = _signup_with(client, SECOND_PHONE, token="iphone-a")
    assert _balance(client, first) == 3
    assert _balance(client, second) == 0


def test_other_iphone_gets_its_own(client, device_check):
    _signup_with(client, DEFAULT_PHONE, token="iphone-a")
    assert _balance(client, _signup_with(client, SECOND_PHONE, token="iphone-b")) == 3


def test_no_device_token_no_free_credits_with_apple(client, monkeypatch):
    from app.core.config import settings

    class NeverAsked:
        def already_claimed(self, token):
            raise AssertionError("no token, nothing to ask")

        def mark_claimed(self, token):
            raise AssertionError("no token, nothing to mark")

    monkeypatch.setattr(settings, "device_check", "apple")
    monkeypatch.setattr("app.domain.billing.entitlements.get_device_check", lambda: NeverAsked())
    headers = _signup_with(client, DEFAULT_PHONE)
    assert _balance(client, headers) == 0


def test_apple_unreachable_falls_back_to_the_phone_check(client, monkeypatch):
    class Down:
        def already_claimed(self, token):
            raise dc.DeviceCheckUnavailable("timeout")

        def mark_claimed(self, token):
            raise dc.DeviceCheckUnavailable("timeout")

    monkeypatch.setattr("app.domain.billing.entitlements.get_device_check", lambda: Down())
    assert _balance(client, _signup_with(client, DEFAULT_PHONE, token="iphone-a")) == 3


def test_simulator_uses_the_device_id_locally(client, device_check):
    _signup_with(client, DEFAULT_PHONE, device_id="sim-1")
    assert _balance(client, _signup_with(client, SECOND_PHONE, device_id="sim-1")) == 0

"""App Review sign-in: a fixed number and code, no SMS, credits topped up."""
from __future__ import annotations

import pytest

from app.providers.otp.mock import MOCK_OTP_CODE, MockOtpProvider
from tests.conftest import DEFAULT_PHONE, signup

REVIEW_PHONE = "+491709876543"
REVIEW_CODE = "48151623"


@pytest.fixture
def review(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "review_phone_number", "+49 170 9876543")  # spaces as typed in .env
    monkeypatch.setattr(settings, "review_otp_code", REVIEW_CODE)
    monkeypatch.setattr(settings, "review_credits", 10)


def _start(client, phone: str):
    return client.post("/v1/auth/phone/start", json={"phone_number": phone, "device_id": "review-device"})


def _confirm(client, verification_id: str, code: str):
    return client.post("/v1/auth/phone/confirm", json={
        "verification_id": verification_id, "code": code, "device_id": "review-device"})


def _sign_in(client, code: str = REVIEW_CODE) -> dict:
    start = _start(client, REVIEW_PHONE)
    assert start.status_code == 200, start.text
    confirm = _confirm(client, start.json()["verification_id"], code)
    assert confirm.status_code == 200, confirm.text
    return {"Authorization": f"Bearer {confirm.json()['session_token']}"}


def _balance(client, headers) -> int:
    return client.get("/v1/me", headers=headers).json()["credits_available"]


def test_review_number_signs_in_with_its_code_and_sends_no_sms(client, review, monkeypatch):
    def no_sms(*args, **kwargs):
        raise AssertionError("no SMS or lookup for the review number")

    monkeypatch.setattr(MockOtpProvider, "start_verification", no_sms)
    monkeypatch.setattr(MockOtpProvider, "lookup_number", no_sms)
    headers = _sign_in(client)
    assert _balance(client, headers) == 10


def test_review_number_refuses_any_other_code(client, review):
    start = _start(client, REVIEW_PHONE)
    for code in (MOCK_OTP_CODE, "48151624", ""):
        assert _confirm(client, start.json()["verification_id"], code).status_code != 200


def test_each_review_sign_in_tops_up_to_the_review_credits(client, review, monkeypatch):
    from app.core.config import settings

    assert _balance(client, _sign_in(client)) == 10
    monkeypatch.setattr(settings, "review_credits", 12)
    assert _balance(client, _sign_in(client)) == 12
    monkeypatch.setattr(settings, "review_credits", 4)  # never takes credits away
    assert _balance(client, _sign_in(client)) == 12


def test_other_numbers_keep_the_real_provider(client, review):
    assert client.get("/v1/me", headers=signup(client, DEFAULT_PHONE)["headers"]) \
        .json()["credits_available"] == 3


def test_without_review_settings_the_review_code_fails(client):
    start = _start(client, REVIEW_PHONE)
    assert _confirm(client, start.json()["verification_id"], REVIEW_CODE).status_code != 200

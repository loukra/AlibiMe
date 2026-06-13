"""Unit tests for Twilio webhook signature verification."""
from __future__ import annotations

from app.core.twilio_webhook import compute_twilio_signature, verify_twilio_signature

URL = "https://example.test/v1/webhooks/sms"
PARAMS = {"MessageSid": "SM123", "MessageStatus": "delivered", "To": "+14155550123"}
TOKEN = "test_auth_token"


def test_matches_twilio_documentation_example():
    # The canonical example from Twilio's "Validating Requests" docs. Proves the
    # algorithm matches Twilio's real signing, not just our own round-trip.
    token = "12345"
    url = "https://mycompany.com/myapp.php?foo=1&bar=2"
    params = {
        "CallSid": "CA1234567890ABCDE",
        "Caller": "+14158675309",
        "Digits": "1234",
        "From": "+14158675309",
        "To": "+18005551212",
    }
    assert compute_twilio_signature(url, params, token) == "RSOYDt4T1cUTdK1PDd93/VVr8B8="
    assert verify_twilio_signature(url, params, "RSOYDt4T1cUTdK1PDd93/VVr8B8=", token)


def test_roundtrip_valid():
    sig = compute_twilio_signature(URL, PARAMS, TOKEN)
    assert verify_twilio_signature(URL, PARAMS, sig, TOKEN)


def test_param_order_independent():
    sig = compute_twilio_signature(URL, PARAMS, TOKEN)
    reordered = {"To": "+14155550123", "MessageStatus": "delivered", "MessageSid": "SM123"}
    assert verify_twilio_signature(URL, reordered, sig, TOKEN)


def test_tampered_param_fails():
    sig = compute_twilio_signature(URL, PARAMS, TOKEN)
    tampered = dict(PARAMS, MessageStatus="failed")
    assert not verify_twilio_signature(URL, tampered, sig, TOKEN)


def test_wrong_token_fails():
    sig = compute_twilio_signature(URL, PARAMS, TOKEN)
    assert not verify_twilio_signature(URL, PARAMS, sig, "different_token")


def test_wrong_url_fails():
    sig = compute_twilio_signature(URL, PARAMS, TOKEN)
    assert not verify_twilio_signature("https://evil.test/hook", PARAMS, sig, TOKEN)


def test_missing_signature_fails():
    assert not verify_twilio_signature(URL, PARAMS, None, TOKEN)
    assert not verify_twilio_signature(URL, PARAMS, "", TOKEN)


def test_missing_token_fails():
    assert not verify_twilio_signature(URL, PARAMS, "anything", None)


def test_malformed_input_does_not_raise():
    # Defensive: never crash on odd values, just return False.
    assert verify_twilio_signature(URL, {"k": None}, "sig", TOKEN) is False

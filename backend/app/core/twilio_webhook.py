"""Twilio webhook signature verification.

Twilio signs each webhook with ``X-Twilio-Signature``: an HMAC-SHA1, keyed by
the account Auth Token, over the exact callback URL concatenated with the POST
parameters sorted by key (key+value, no separators), base64-encoded.

https://www.twilio.com/docs/usage/security#validating-requests

Design notes:
  - Verify against the *configured* public callback URL (the exact string Twilio
    signed), not the request URL the app sees behind a tunnel/proxy — otherwise
    scheme/host differences cause false rejections.
  - Never raise: malformed input returns False so the caller responds 403, the
    app never crashes on a bad/forged signature.
"""
from __future__ import annotations

import base64
import hashlib
import hmac


def compute_twilio_signature(url: str, params: dict, auth_token: str) -> str:
    data = url + "".join(f"{k}{'' if params[k] is None else params[k]}" for k in sorted(params))
    mac = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("ascii")


def verify_twilio_signature(url: str, params: dict, signature: str | None, auth_token: str | None) -> bool:
    """True iff `signature` matches Twilio's HMAC for (url, params, auth_token)."""
    if not signature or not auth_token or not url:
        return False
    try:
        # Coerce all values to str (form values already are; be defensive).
        normalized = {str(k): ("" if v is None else str(v)) for k, v in params.items()}
        expected = compute_twilio_signature(url, normalized, auth_token)
    except Exception:
        return False
    return hmac.compare_digest(expected, signature)

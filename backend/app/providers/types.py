"""Shared provider DTOs and exceptions.

Provider-specific details stay behind these abstractions (load-bearing invariant
#11). The rest of the app only ever sees these neutral types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --- Exceptions ---

class ProviderError(Exception):
    """Base provider error. Non-retryable unless `retryable` is True."""

    retryable: bool = False

    def __init__(self, message: str, *, retryable: bool | None = None):
        super().__init__(message)
        self.message = message
        if retryable is not None:
            self.retryable = retryable


class TransientProviderError(ProviderError):
    """A pre-dispatch technical failure that is safe to retry.

    Examples: network timeout before provider acknowledgement, transient 5xx,
    temporary connection error. NEVER raised once a human-facing outcome has
    happened (ring/connect/sent/delivered).
    """

    retryable = True


class ProviderRejected(ProviderError):
    """Provider refused the request (e.g. invalid number). Not retryable."""

    retryable = False


# --- Request plan (resolved snapshot handed to providers) ---

@dataclass
class RequestPlan:
    request_id: str
    channel: str  # "call" | "sms"
    # template snapshot
    template_code: str
    template_version: int
    locale: str
    caller_persona: str
    reason_code: str
    # rendered content
    rendered_opening_line: str | None = None
    rendered_sms_body: str | None = None
    allowed_followup_facts: list[str] = field(default_factory=list)
    # call config
    call_system_prompt: str | None = None
    voice_profile_code: str | None = None
    max_duration_seconds: int | None = None
    supports_interruptions: bool = False
    # sender + destination (internal only)
    service_identity_value: str | None = None
    service_identity_type: str | None = None
    target_phone_e164: str | None = None  # decrypted at dispatch; never logged
    target_phone_number_id: str | None = None
    # optional personalization
    user_first_name: str | None = None
    # mock-only behavior hints (ignored by real providers)
    mock_behavior: dict[str, Any] = field(default_factory=dict)


# --- OTP results ---

@dataclass
class OtpStartResult:
    provider_verification_id: str
    channel: str  # "sms" | "call"
    expires_in_seconds: int
    debug_code: str | None = None  # mock/dev only


@dataclass
class OtpConfirmResult:
    success: bool


@dataclass
class NumberLookup:
    valid: bool
    line_type: str = "unknown"
    country_code: str | None = None


# --- Voice / message dispatch results ---

@dataclass
class ProviderCallResult:
    provider_call_id: str
    status: str
    accepted: bool
    estimated_cost_minor: int | None = None
    raw: dict[str, Any] | None = None


@dataclass
class ProviderMessageResult:
    provider_message_id: str
    status: str
    accepted: bool
    estimated_cost_minor: int | None = None
    raw: dict[str, Any] | None = None


# --- Webhook parsing ---

@dataclass
class WebhookParseResult:
    external_event_id: str | None
    event_type: str | None
    provider_ref_id: str | None  # provider_call_id or provider_message_id
    mapped_status: str | None     # neutral attempt status
    fields: dict[str, Any] = field(default_factory=dict)

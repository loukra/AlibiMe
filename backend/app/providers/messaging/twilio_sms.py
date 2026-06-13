"""Real one-way outbound SMS via Twilio Programmable Messaging.

https://www.twilio.com/docs/messaging/api/message-resource

Requires (env vars, from the Twilio console):

- ``TWILIO_ACCOUNT_SID``  — account SID (starts with "AC...")
- ``TWILIO_AUTH_TOKEN``   — account auth token
- and a sender, one of:
    - ``TWILIO_MESSAGING_SERVICE_SID`` — a Messaging Service SID (starts "MG...")
    - ``TWILIO_SMS_FROM_NUMBER``       — a Twilio phone number in E.164

Optional:
- ``TWILIO_STATUS_CALLBACK_URL`` — public URL of this app's ``/v1/webhooks/sms``
  so Twilio posts delivery-status updates (sent/delivered/failed). Without it,
  a request stays at ``provider_accepted`` (the send was accepted) and is swept
  by reconciliation after the inflight timeout.

Implements the same ``MessageProvider`` interface as ``MockMessageProvider``.
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.db.models.enums import MessageAttemptStatus
from app.providers.messaging.base import MessageProvider
from app.providers.types import (
    ProviderMessageResult,
    ProviderRejected,
    RequestPlan,
    TransientProviderError,
    WebhookParseResult,
)

_API_BASE = "https://api.twilio.com/2010-04-01"

# Twilio MessageStatus -> our neutral MessageAttemptStatus.
_STATUS_MAP = {
    "accepted": MessageAttemptStatus.queued.value,
    "queued": MessageAttemptStatus.queued.value,
    "scheduled": MessageAttemptStatus.queued.value,
    "sending": MessageAttemptStatus.queued.value,
    "sent": MessageAttemptStatus.sent.value,
    "delivered": MessageAttemptStatus.delivered.value,
    "undelivered": MessageAttemptStatus.failed_post_send.value,
    "failed": MessageAttemptStatus.failed_post_send.value,
}


class TwilioMessagingProvider(MessageProvider):
    """Outbound SMS via Twilio. One-way only (MVP)."""

    name = "twilio_messaging"

    def __init__(self) -> None:
        if not (settings.twilio_account_sid and settings.twilio_auth_token):
            raise RuntimeError(
                "TwilioMessagingProvider requires TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
            )
        if not (settings.twilio_messaging_service_sid or settings.twilio_sms_from_number):
            raise RuntimeError(
                "TwilioMessagingProvider requires a sender: set TWILIO_MESSAGING_SERVICE_SID "
                "or TWILIO_SMS_FROM_NUMBER."
            )
        self._auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        self._account_sid = settings.twilio_account_sid
        self._messaging_service_sid = settings.twilio_messaging_service_sid
        self._from_number = settings.twilio_sms_from_number
        self._status_callback = settings.twilio_status_callback_url

    def send_sms(self, plan: RequestPlan) -> ProviderMessageResult:
        if not plan.target_phone_e164:
            raise ProviderRejected("No destination number resolved for SMS dispatch.")
        if not plan.rendered_sms_body:
            raise ProviderRejected("Template produced no SMS body.")

        data: dict[str, str] = {"To": plan.target_phone_e164, "Body": plan.rendered_sms_body}
        # Prefer a Messaging Service; fall back to a fixed From number, then to
        # the service identity selected by the dispatcher.
        if self._messaging_service_sid:
            data["MessagingServiceSid"] = self._messaging_service_sid
        elif self._from_number:
            data["From"] = self._from_number
        elif plan.service_identity_value:
            data["From"] = plan.service_identity_value
        else:
            raise ProviderRejected("No Twilio sender (messaging service or from number) available.")
        if self._status_callback:
            data["StatusCallback"] = self._status_callback

        url = f"{_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        resp = self._post(url, data)
        self._raise_for_status(resp)
        body = resp.json()
        status = _STATUS_MAP.get(body.get("status", ""), MessageAttemptStatus.queued.value)
        return ProviderMessageResult(
            provider_message_id=body["sid"],
            status=status,
            accepted=True,
            estimated_cost_minor=_price_to_minor(body.get("price")),
            raw=body,
        )

    def cancel_sms(self, provider_message_id: str) -> bool:
        # Only possible while still queued/accepted; best effort.
        url = f"{_API_BASE}/Accounts/{self._account_sid}/Messages/{provider_message_id}.json"
        try:
            resp = httpx.post(url, auth=self._auth, data={"Status": "canceled"}, timeout=10.0)
        except httpx.TransportError:
            return False
        return resp.status_code < 400

    def parse_webhook(self, payload: dict) -> WebhookParseResult:
        # Twilio status callbacks are form-encoded; the route normalizes them to
        # a dict before we get here.
        message_sid = payload.get("MessageSid") or payload.get("SmsSid")
        message_status = payload.get("MessageStatus") or payload.get("SmsStatus")
        error_code = payload.get("ErrorCode")
        # Twilio doesn't send a unique event id; dedupe per (message, status).
        external_event_id = (
            f"{message_sid}:{message_status}" if message_sid and message_status else None
        )
        return WebhookParseResult(
            external_event_id=external_event_id,
            event_type=message_status,
            provider_ref_id=message_sid,
            mapped_status=_STATUS_MAP.get(message_status or ""),
            fields={"failure_reason": error_code},
        )

    def _post(self, url: str, data: dict) -> httpx.Response:
        try:
            return httpx.post(url, auth=self._auth, data=data, timeout=10.0)
        except httpx.TransportError as exc:
            raise TransientProviderError(f"Twilio request failed: {exc}") from exc

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        # 5xx / 429 are pre-send transient failures (safe to retry once).
        if resp.status_code >= 500 or resp.status_code == 429:
            raise TransientProviderError(f"Twilio returned {resp.status_code}: {resp.text}")
        if resp.status_code >= 400:
            raise ProviderRejected(f"Twilio returned {resp.status_code}: {resp.text}")


def _price_to_minor(price) -> int | None:
    """Twilio returns price as a signed decimal string in account currency
    (e.g. "-0.0075"), or null at creation. Convert the magnitude to minor units."""
    if price is None:
        return None
    try:
        return int(round(abs(float(price)) * 100))
    except (TypeError, ValueError):
        return None

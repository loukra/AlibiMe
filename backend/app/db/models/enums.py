"""String enums for status fields. Stored as plain strings for portability."""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.value


class UserStatus(StrEnum):
    active = "active"
    blocked = "blocked"
    deleted = "deleted"


class PhoneStatus(StrEnum):
    pending = "pending"
    verified = "verified"
    replaced = "replaced"
    revoked = "revoked"


class LineType(StrEnum):
    mobile = "mobile"
    landline = "landline"
    fixed_voip = "fixed_voip"
    non_fixed_voip = "non_fixed_voip"
    unknown = "unknown"


class SessionStatus(StrEnum):
    active = "active"
    revoked = "revoked"
    expired = "expired"


class Channel(StrEnum):
    call = "call"
    sms = "sms"


class ScheduledKind(StrEnum):
    immediate = "immediate"
    delayed = "delayed"
    exact_time = "exact_time"


class RequestStatus(StrEnum):
    scheduled = "scheduled"
    dispatching = "dispatching"
    provider_accepted = "provider_accepted"
    active = "active"  # call only: ringing or connected
    completed = "completed"
    no_answer = "no_answer"  # call only: delivered but not answered (DND, declined, voicemail)
    failed = "failed"
    canceled = "canceled"
    expired = "expired"


# Terminal request states.
TERMINAL_REQUEST_STATUSES = {
    RequestStatus.completed,
    RequestStatus.no_answer,
    RequestStatus.failed,
    RequestStatus.canceled,
    RequestStatus.expired,
}

# A request is considered "active/live" (counts against the one-live-request rule)
# while it is not terminal.
LIVE_REQUEST_STATUSES = {
    RequestStatus.scheduled,
    RequestStatus.dispatching,
    RequestStatus.provider_accepted,
    RequestStatus.active,
}


class CallAttemptStatus(StrEnum):
    created = "created"
    provider_requested = "provider_requested"
    queued = "queued"
    ringing = "ringing"
    in_progress = "in_progress"
    ended = "ended"
    failed_pre_dial = "failed_pre_dial"
    failed_post_dial = "failed_post_dial"
    canceled = "canceled"


class MessageAttemptStatus(StrEnum):
    created = "created"
    provider_requested = "provider_requested"
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    failed_pre_send = "failed_pre_send"
    failed_post_send = "failed_post_send"
    canceled = "canceled"


class IdentityType(StrEnum):
    phone_number = "phone_number"
    alphanumeric_sender_id = "alphanumeric_sender_id"


class ServiceIdentityStatus(StrEnum):
    active = "active"
    warming = "warming"
    disabled = "disabled"


class SenderBindingStatus(StrEnum):
    """Lifecycle of a stable user+persona+channel -> sender line binding."""

    active = "active"
    orphaned = "orphaned"  # bound line removed/disabled; reallocate on next send
    released = "released"  # admin cleanup only (MVP: unused at runtime)


class PlanKind(StrEnum):
    one_time = "one_time"
    subscription = "subscription"


class FulfillmentMode(StrEnum):
    """How a credit package is paid for. ``free_dev`` grants immediately and must
    be disabled before a public paid release; ``app_store_iap`` requires a
    validated store transaction (added in a later pass)."""

    free_dev = "free_dev"
    app_store_iap = "app_store_iap"


class CreditPackageClaimStatus(StrEnum):
    pending = "pending"
    granted = "granted"
    failed = "failed"
    canceled = "canceled"


class EntitlementSource(StrEnum):
    app_store = "app_store"
    play_store = "play_store"
    revenuecat = "revenuecat"
    admin = "admin"
    promo = "promo"


class EntitlementStatus(StrEnum):
    active = "active"
    expired = "expired"
    canceled = "canceled"


class CreditEntryType(StrEnum):
    grant = "grant"
    reserve = "reserve"
    capture = "capture"
    release = "release"
    refund = "refund"
    admin_adjustment = "admin_adjustment"


class CreditReferenceType(StrEnum):
    purchase = "purchase"
    subscription_renewal = "subscription_renewal"
    request = "request"
    attempt = "attempt"
    manual = "manual"


class TemplateCategory(StrEnum):
    work = "work"
    family = "family"
    social = "social"
    logistics = "logistics"
    safety = "safety"


class WebhookProcessingStatus(StrEnum):
    received = "received"
    processed = "processed"
    duplicate = "duplicate"
    failed = "failed"

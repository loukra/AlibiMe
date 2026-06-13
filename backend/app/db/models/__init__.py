"""Import all models so Base.metadata is fully populated."""
from app.db.base import Base
from app.db.models.artifact import RequestArtifact
from app.db.models.attempts import CallAttempt, MessageAttempt
from app.db.models.credit_ledger import CreditLedger
from app.db.models.device import Device
from app.db.models.entitlement import Entitlement
from app.db.models.otp_verification import OtpVerification
from app.db.models.phone import PhoneNumber
from app.db.models.plan import Plan
from app.db.models.rate_limit import RateLimitCounter
from app.db.models.request import Request
from app.db.models.service_identity import ServiceIdentity
from app.db.models.template import Template, TemplateVersion
from app.db.models.usage_daily import UsageDaily
from app.db.models.user import User
from app.db.models.user_session import UserSession
from app.db.models.webhook_event import WebhookEvent

__all__ = [
    "Base",
    "RequestArtifact",
    "CallAttempt",
    "MessageAttempt",
    "CreditLedger",
    "Device",
    "Entitlement",
    "OtpVerification",
    "PhoneNumber",
    "Plan",
    "RateLimitCounter",
    "Request",
    "ServiceIdentity",
    "Template",
    "TemplateVersion",
    "UsageDaily",
    "User",
    "UserSession",
    "WebhookEvent",
]

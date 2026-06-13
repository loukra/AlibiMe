"""Provider selection by configuration. Default mode is ``mock`` everywhere."""
from __future__ import annotations

from app.core.config import settings
from app.providers.messaging.base import MessageProvider
from app.providers.messaging.mock import MockMessageProvider
from app.providers.otp.base import OtpProvider
from app.providers.otp.mock import MockOtpProvider
from app.providers.voice.base import VoiceProvider
from app.providers.voice.mock import MockVoiceCallProvider


def get_otp_provider() -> OtpProvider:
    if settings.otp_provider == "mock":
        return MockOtpProvider()
    if settings.otp_provider == "twilio_verify":
        from app.providers.otp.twilio_verify import TwilioVerifyProvider

        return TwilioVerifyProvider()
    raise ValueError(f"Unknown OTP_PROVIDER: {settings.otp_provider}")


def get_voice_provider() -> VoiceProvider:
    if settings.voice_provider == "mock":
        return MockVoiceCallProvider()
    if settings.voice_provider == "vapi":
        from app.providers.voice.vapi import VapiVoiceProvider

        return VapiVoiceProvider()
    raise ValueError(f"Unknown VOICE_PROVIDER: {settings.voice_provider}")


def get_message_provider() -> MessageProvider:
    if settings.message_provider == "mock":
        return MockMessageProvider()
    if settings.message_provider == "twilio_messaging":
        from app.providers.messaging.twilio_sms import TwilioMessagingProvider

        return TwilioMessagingProvider()
    raise ValueError(f"Unknown MESSAGE_PROVIDER: {settings.message_provider}")

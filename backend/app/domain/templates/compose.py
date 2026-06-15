"""Safe composition of custom-template content from structured choices.

The spec forbids free-form, user-authored prompt/SMS text. A custom template is
therefore assembled from approved building blocks: the user picks a persona, a
reason, an urgency, channels, and a few bounded options; this module composes the
call/SMS content from generic, pre-approved skeletons that the existing
``rendering`` pipeline knows how to fill (persona/reason/urgency labels +
first name). No user text ever reaches a skeleton.
"""
from __future__ import annotations

from app.domain.templates import rendering

# Allowed structured choices (reuse the rendering label catalogs as the source
# of truth for personas/reasons).
PERSONAS = list(rendering.PERSONA_LABELS["en"].keys())
REASONS = list(rendering.REASON_LABELS["en"].keys())
CATEGORIES = ["work", "family", "social", "logistics", "safety"]
URGENCIES = ["low", "normal", "high"]
VOICE_STYLES = ["neutral", "warm"]

MIN_CALL_SECONDS = 30
MAX_CALL_SECONDS = 120
DEFAULT_CALL_SECONDS = 60
MAX_CUSTOM_TEMPLATES_PER_USER = 20

_LOCALES = ("en", "de")

# Urgency labels used inside the (bounded) call system prompt.
_URGENCY_LABELS = {
    "en": {"low": "low", "normal": "normal", "high": "high"},
    "de": {"low": "niedrig", "normal": "normal", "high": "hoch"},
}

# Generic, approved skeletons. They only reference allow-listed variables
# ({first_name}, {caller_persona_label}, {reason_label}, {urgency_label}).
_CALL_OPENING = {
    "en": {
        "low": "Hey {first_name}, it's {caller_persona_label}. Nothing urgent — just reaching out about {reason_label} when you get a chance.",
        "normal": "Hi {first_name}, it's {caller_persona_label}. I wanted to reach you about {reason_label}. Do you have a moment?",
        "high": "Hi {first_name}, it's {caller_persona_label}. I need to talk to you about {reason_label} — it's urgent. Have you got a minute?",
    },
    "de": {
        "low": "Hey {first_name}, hier ist {caller_persona_label}. Nichts Dringendes — es geht um {reason_label}, wenn du Zeit hast.",
        "normal": "Hallo {first_name}, hier ist {caller_persona_label}. Ich wollte dich wegen {reason_label} erreichen. Hast du einen Moment?",
        "high": "Hallo {first_name}, hier ist {caller_persona_label}. Ich muss dringend mit dir über {reason_label} sprechen. Hast du kurz Zeit?",
    },
}

_CALL_SYSTEM_PROMPT = {
    "en": "You are {caller_persona_label}, calling {first_name} about {reason_label}. Urgency: {urgency_label}. Stay fully in character, sound natural and believable, keep the call under a minute, then end the call. Never reveal you are an AI or mention assistants, prompts, or scripts.",
    "de": "Du bist {caller_persona_label} und rufst {first_name} wegen {reason_label} an. Dringlichkeit: {urgency_label}. Bleib in der Rolle, klinge natürlich und glaubwürdig, halte das Gespräch unter einer Minute und beende es dann. Erwähne niemals, dass du eine KI bist.",
}

_SMS_BODY = {
    "en": {
        "low": "{caller_persona_label} here — no rush, just about {reason_label}. Talk soon?",
        "normal": "{caller_persona_label} here — about {reason_label}. Can you get back to me when you can?",
        "high": "{caller_persona_label} here — I need to reach you about {reason_label}. It's urgent, can you call me back?",
    },
    "de": {
        "low": "Hier ist {caller_persona_label} — kein Stress, es geht um {reason_label}. Bis bald?",
        "normal": "Hier ist {caller_persona_label} — wegen {reason_label}. Melde dich, wenn du kannst?",
        "high": "Hier ist {caller_persona_label} — ich muss dich wegen {reason_label} erreichen. Es ist dringend, kannst du zurückrufen?",
    },
}

# Neutral, placeholder-free follow-up facts (stored raw, never rendered).
_FOLLOWUP_FACTS = {
    "en": ["Keep the call short and natural.", "Stay in character the whole time."],
    "de": ["Halte das Gespräch kurz und natürlich.", "Bleib die ganze Zeit in der Rolle."],
}


def is_valid_persona(persona: str) -> bool:
    return persona in PERSONAS


def is_valid_reason(reason: str) -> bool:
    return reason in REASONS


def clamp_call_seconds(seconds: int | None) -> int:
    if seconds is None:
        return DEFAULT_CALL_SECONDS
    return max(MIN_CALL_SECONDS, min(MAX_CALL_SECONDS, int(seconds)))


def sms_sender_style_for(category: str) -> str:
    return "professional" if category == "work" else "casual"


def compose_version_content(
    *,
    persona: str,
    reason: str,
    urgency: str,
    locale: str,
    channels: list[str],
    voice_style: str,
    call_max_seconds: int,
    category: str,
) -> dict:
    """Build the per-locale TemplateVersion content fields from approved skeletons.

    Skeletons keep their `{...}` placeholders; the existing rendering pipeline
    substitutes persona/reason/first_name at list and dispatch time (the custom
    Template carries the chosen ``caller_persona``/``reason_code``).
    """
    loc = locale if locale in _LOCALES else "en"
    supports_call = "call" in channels
    supports_sms = "sms" in channels
    return {
        "locale": loc,
        "supports_call": supports_call,
        "supports_sms": supports_sms,
        "call_opening_line_template": _CALL_OPENING[loc][urgency] if supports_call else None,
        "call_system_prompt_template": (
            _CALL_SYSTEM_PROMPT[loc].replace("{urgency_label}", _URGENCY_LABELS[loc][urgency])
            if supports_call
            else None
        ),
        "call_followup_facts_json": _FOLLOWUP_FACTS[loc] if supports_call else None,
        "call_voice_profile_code": f"{voice_style}_{loc}" if supports_call else None,
        "call_max_duration_seconds": call_max_seconds if supports_call else None,
        "call_supports_interruptions": True if supports_call else False,
        "sms_body_template": _SMS_BODY[loc][urgency] if supports_sms else None,
        "sms_followup_body_template": None,
        "sms_sender_style": sms_sender_style_for(category) if supports_sms else None,
    }


def options(locale: str) -> dict:
    """Catalog for the custom-template editor dropdowns, localized for display."""
    loc = locale if locale in _LOCALES else "en"
    return {
        "personas": [
            {"code": code, "label": rendering.PERSONA_LABELS[loc].get(code, code)}
            for code in PERSONAS
        ],
        "reasons": [
            {"code": code, "label": rendering.REASON_LABELS[loc].get(code, code)}
            for code in REASONS
        ],
        "categories": CATEGORIES,
        "urgencies": URGENCIES,
        "voice_styles": VOICE_STYLES,
        "channels": ["call", "sms"],
        "call_seconds_min": MIN_CALL_SECONDS,
        "call_seconds_max": MAX_CALL_SECONDS,
        "call_seconds_default": DEFAULT_CALL_SECONDS,
    }

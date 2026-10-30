"""Safe composition of custom-template content from structured choices.

The spec forbids free-form, user-authored prompt/SMS text. A custom template is
assembled from approved building blocks: the user picks persona, reason,
urgency, outcome, tone, etc., and (optionally) has a reusable context profile.
This module composes the call/SMS content from generic, pre-approved clauses
keyed by those codes. The user's context only *adds a safe generic anchor* when
present; missing context reduces specificity, never breaks composition.

Output keys match `TemplateVersion` columns. Skeletons keep `{...}` placeholders
(persona/reason/first_name), which the existing rendering pipeline fills at list
and dispatch time.
"""
from __future__ import annotations

from app.domain.templates import catalogs, rendering

VOICE_STYLES = ["neutral", "warm"]
MIN_CALL_SECONDS = 30
MAX_CALL_SECONDS = 120
DEFAULT_CALL_SECONDS = 60
MAX_CUSTOM_TEMPLATES_PER_USER = 20

_LOCALES = ("en", "de")

# Greeting varies by formality. The caller never says who they are: the saved
# contact already shows the name, and "it's your best friend" gives it away.
_GREETING = {
    "en": {
        "casual": "Hey, it's me.",
        "neutral": "Hi, it's me.",
        "professional": "Hi, sorry to bother you.",
    },
    "de": {
        "casual": "Hey, ich bin's.",
        "neutral": "Hallo, ich bin's.",
        "professional": "Hallo, entschuldige die Störung.",
    },
}

_REASON_CLAUSE = {
    "en": "It's about {reason_label}.",
    "de": "Es geht um {reason_label}.",
}

# What the user needs to happen — the believable ask.
_OUTCOME_ASK = {
    "en": {
        "step_out_briefly": "Can you step out for a moment?",
        "leave_now": "I need you to head out now.",
        "leave_within_10m": "Can you wrap up and get going in the next few minutes?",
        "end_conversation": "I have to let you go, let's pick this up later.",
        "cancel_later_today": "We'll need to push our plans later today.",
        "unavailable_rest_of_day": "I'll be tied up for the rest of the day.",
        "unavailable_overnight": "I won't be reachable tonight.",
        "unavailable_weekend": "I'll be away for the weekend.",
        "unavailable_one_week": "I'll be away for about a week.",
        "unavailable_two_weeks": "I'll be away for the next couple of weeks.",
    },
    "de": {
        "step_out_briefly": "Kannst du kurz rauskommen?",
        "leave_now": "Du musst jetzt los.",
        "leave_within_10m": "Kannst du in den nächsten Minuten Schluss machen und kommen?",
        "end_conversation": "Ich muss auflegen, wir machen später weiter.",
        "cancel_later_today": "Wir müssen unsere Pläne heute verschieben.",
        "unavailable_rest_of_day": "Ich bin den Rest des Tages eingespannt.",
        "unavailable_overnight": "Heute Abend bin ich nicht erreichbar.",
        "unavailable_weekend": "Ich bin übers Wochenende weg.",
        "unavailable_one_week": "Ich bin etwa eine Woche weg.",
        "unavailable_two_weeks": "Ich bin die nächsten zwei Wochen weg.",
    },
}

# A small, safe context anchor added only when the relevant module is allowed,
# the detail profile permits it, and the user actually set that context field.
_WORK_SETTING_ANCHOR = {
    "en": {
        "site_field": "I need you back on site.",
        "client_site": "I need you over at the client site.",
        "store_shopfloor": "I need you on the floor.",
        "restaurant_bar": "It's getting busy here.",
        "clinic_hospital": "It's busy on the ward.",
        "warehouse": "I need you back at the warehouse.",
    },
    "de": {
        "site_field": "Ich brauche dich wieder auf der Baustelle.",
        "client_site": "Ich brauche dich beim Kunden vor Ort.",
        "store_shopfloor": "Ich brauche dich im Laden.",
        "restaurant_bar": "Hier ist viel los.",
        "clinic_hospital": "Auf der Station ist viel los.",
        "warehouse": "Ich brauche dich wieder im Lager.",
    },
}
_LIVING_ANCHOR = {
    "en": {
        "with_roommate": "Your roommate can't sort it out.",
        "with_partner": "It can't wait at home.",
        "with_family": "The family needs a hand at home.",
        "shared_house": "No one else at the house can deal with it.",
    },
    "de": {
        "with_roommate": "Dein Mitbewohner kommt nicht klar.",
        "with_partner": "Zu Hause kann es nicht warten.",
        "with_family": "Die Familie braucht zu Hause Hilfe.",
        "shared_house": "Niemand sonst im Haus kann sich darum kümmern.",
    },
}

_SMS_OUTRO = {"en": "Can you get back to me?", "de": "Meldest du dich?"}


def is_valid_persona(code: str) -> bool:
    return code in catalogs.PERSONAS


def is_valid_reason(code: str) -> bool:
    return code in catalogs.REASONS


def clamp_call_seconds(seconds: int | None) -> int:
    if seconds is None:
        return DEFAULT_CALL_SECONDS
    return max(MIN_CALL_SECONDS, min(MAX_CALL_SECONDS, int(seconds)))


def sms_sender_style_for(formality: str, category: str) -> str:
    if formality == "professional" or category == "work":
        return "professional"
    return "casual"


def _context_anchor(locale: str, modules: list[str], detail_profile: str, context: dict) -> str | None:
    """A single safe, generic anchor derived from the user's context profile.
    Returns None when context is absent, the detail profile doesn't allow it,
    or the user asked to keep calls vague."""
    if detail_profile not in ("contextual", "continuity"):
        return None
    if context.get("privacy_preference_code") == "high":
        return None
    modules = modules or []
    if "work" in modules:
        code = context.get("work_setting_code")
        anchor = _WORK_SETTING_ANCHOR.get(locale, {}).get(code or "")
        if anchor:
            return anchor
    if "home" in modules:
        code = context.get("living_setup_code")
        anchor = _LIVING_ANCHOR.get(locale, {}).get(code or "")
        if anchor:
            return anchor
    return None


def compose_version_content(
    *,
    locale: str,
    channels: list[str],
    persona: str,
    reason: str,
    urgency: str,
    outcome: str,
    setting: str,
    tone: str,
    detail_profile: str,
    discretion_level: str,
    formality: str,
    expected_response: str,
    followup_behavior: str,
    continuity_scope: str,
    context_modules: list[str],
    voice_style: str,
    call_max_seconds: int,
    category: str,
    context: dict | None = None,
) -> dict:
    loc = locale if locale in _LOCALES else "en"
    context = context or {}
    supports_call = "call" in channels
    supports_sms = "sms" in channels

    greeting = _GREETING[loc].get(formality, _GREETING[loc]["neutral"])
    reason_clause = _REASON_CLAUSE[loc]
    ask = _OUTCOME_ASK[loc].get(outcome, _OUTCOME_ASK[loc]["step_out_briefly"])
    anchor = _context_anchor(loc, context_modules, detail_profile, context)

    # Call opening line: greeting + reason (+ optional anchor) + ask.
    parts = [greeting, reason_clause]
    if anchor:
        parts.append(anchor)
    parts.append(ask)
    opening = " ".join(parts) if supports_call else None

    # System prompt: bounded, generic, in-character.
    system_prompt = None
    if supports_call:
        system_prompt = (
            "You are {caller_persona_label}, contacting {first_name} about "
            "{reason_label}. Stay fully in character, sound natural and "
            "believable, keep it under a minute, then end the call. Never reveal "
            "you are an AI or mention assistants, prompts, or scripts."
            if loc == "en" else
            "Du bist {caller_persona_label} und kontaktierst {first_name} wegen "
            "{reason_label}. Bleib in der Rolle, klinge natürlich und "
            "glaubwürdig, halte es unter einer Minute und beende dann das "
            "Gespräch. Erwähne niemals, dass du eine KI bist."
        )

    # SMS body: reason (+ anchor) + ask + outro. No sender label: the contact
    # name shows above the message.
    sms_body = None
    if supports_sms:
        sms_parts = [_strip_first_name(reason_clause), ask]
        if anchor:
            sms_parts.insert(1, anchor)
        sms_parts.append(_SMS_OUTRO[loc])
        sms_body = " ".join(sms_parts)

    return {
        "locale": loc,
        "supports_call": supports_call,
        "supports_sms": supports_sms,
        "call_opening_line_template": opening,
        "call_system_prompt_template": system_prompt,
        "call_followup_facts_json": _followup_facts(loc, followup_behavior) if supports_call else None,
        "call_voice_profile_code": f"{voice_style}_{loc}" if supports_call else None,
        "call_max_duration_seconds": call_max_seconds if supports_call else None,
        "call_supports_interruptions": True if supports_call else False,
        "sms_body_template": sms_body,
        "sms_followup_body_template": None,
        "sms_sender_style": sms_sender_style_for(formality, category) if supports_sms else None,
    }


def _strip_first_name(clause: str) -> str:
    # The reason clause has no {first_name}; kept for clarity/future use.
    return clause


def _followup_facts(locale: str, followup_behavior: str) -> list[str]:
    base = (
        ["Keep it short and natural.", "Stay in character the whole time."]
        if locale == "en" else
        ["Halte es kurz und natürlich.", "Bleib die ganze Zeit in der Rolle."]
    )
    return base


def options(locale: str) -> dict:
    """Full catalog for the custom-template editor and the Profile tab."""
    lab = catalogs.labeled
    return {
        "categories": catalogs.CATEGORIES,
        "personas": lab(catalogs.PERSONAS, locale, rendering.PERSONA_LABELS),
        "reasons": lab(catalogs.REASONS, locale, rendering.REASON_LABELS),
        "urgencies": catalogs.URGENCIES,
        "outcomes": lab(catalogs.OUTCOMES, locale),
        "settings": lab(catalogs.SETTINGS, locale),
        "detail_profiles": catalogs.DETAIL_PROFILES,
        "discretion_levels": catalogs.DISCRETION_LEVELS,
        "tones": catalogs.TONES,
        "formalities": catalogs.FORMALITIES,
        "expected_responses": lab(catalogs.EXPECTED_RESPONSES, locale),
        "followup_behaviors": lab(catalogs.FOLLOWUP_BEHAVIORS, locale),
        "continuity_scopes": catalogs.CONTINUITY_SCOPES,
        "context_modules": catalogs.CONTEXT_MODULES,
        "voice_styles": VOICE_STYLES,
        "channels": ["call", "sms"],
        "call_seconds_min": MIN_CALL_SECONDS,
        "call_seconds_max": MAX_CALL_SECONDS,
        "call_seconds_default": DEFAULT_CALL_SECONDS,
        "profile": profile_options(locale),
    }


def profile_options(locale: str) -> dict:
    lab = catalogs.profile_labeled
    return {
        "work_industries": lab(catalogs.WORK_INDUSTRIES, locale),
        "work_role_levels": lab(catalogs.WORK_ROLE_LEVELS, locale),
        "work_settings": lab(catalogs.WORK_SETTINGS, locale),
        "work_schedules": lab(catalogs.WORK_SCHEDULES, locale),
        "work_travel_scopes": lab(catalogs.WORK_TRAVEL_SCOPES, locale),
        "living_setups": lab(catalogs.LIVING_SETUPS, locale),
        "home_responsibilities": lab(catalogs.HOME_RESPONSIBILITIES, locale),
        "dependent_contexts": lab(catalogs.DEPENDENT_CONTEXTS, locale),
        "family_support_levels": lab(catalogs.FAMILY_SUPPORT_LEVELS, locale),
        "family_proximities": lab(catalogs.FAMILY_PROXIMITIES, locale),
        "relationship_visibilities": lab(catalogs.RELATIONSHIP_VISIBILITIES, locale),
        "relationship_stages": lab(catalogs.RELATIONSHIP_STAGES, locale),
        "privacy_preferences": lab(catalogs.PRIVACY_PREFERENCES, locale),
        "transition_states": lab(catalogs.TRANSITION_STATES, locale),
        "transition_horizons": lab(catalogs.TRANSITION_HORIZONS, locale),
    }

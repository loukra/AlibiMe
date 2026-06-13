"""Bounded variable substitution for templates.

Only a fixed allow-list of variables is permitted. There is no free-form,
user-authored prompt generation (spec: "Versioned templates, no free-form
runtime generation").
"""
from __future__ import annotations

import re

ALLOWED_VARIABLES = {
    "first_name",
    "caller_persona_label",
    "reason_label",
    "urgency_label",
    "locale",
}

_VAR_PATTERN = re.compile(r"\{(\w+)\}")

# Localized labels for personas / reasons / urgency.
PERSONA_LABELS = {
    "en": {
        "boss": "your manager",
        "coworker": "your coworker",
        "sibling": "your sibling",
        "roommate": "your roommate",
        "best_friend": "your best friend",
        "partner": "your partner",
    },
    "de": {
        "boss": "dein Chef",
        "coworker": "dein Kollege",
        "sibling": "dein Geschwister",
        "roommate": "dein Mitbewohner",
        "best_friend": "dein bester Freund",
        "partner": "dein Partner",
    },
}

REASON_LABELS = {
    "en": {
        "travel_assignment_abroad": "an urgent travel assignment",
        "urgent_work_issue": "an urgent work issue",
        "family_checkin": "a family check-in",
        "issue_at_home": "an issue at home",
        "need_you_outside": "needing you outside",
        "safety_checkin": "a safety check-in",
    },
    "de": {
        "travel_assignment_abroad": "ein dringender Reiseauftrag",
        "urgent_work_issue": "ein dringendes Arbeitsproblem",
        "family_checkin": "ein Familien-Check-in",
        "issue_at_home": "ein Problem zu Hause",
        "need_you_outside": "muss dich draußen treffen",
        "safety_checkin": "ein Sicherheits-Check-in",
    },
}


def build_context(
    *,
    locale: str,
    caller_persona: str,
    reason_code: str,
    first_name: str | None = None,
    urgency_label: str | None = None,
) -> dict[str, str]:
    loc = locale if locale in PERSONA_LABELS else "en"
    return {
        "first_name": first_name or ("there" if loc == "en" else "du"),
        "caller_persona_label": PERSONA_LABELS[loc].get(caller_persona, caller_persona),
        "reason_label": REASON_LABELS[loc].get(reason_code, reason_code),
        "urgency_label": urgency_label or ("urgent" if loc == "en" else "dringend"),
        "locale": loc,
    }


def render(text: str | None, context: dict[str, str]) -> str | None:
    if text is None:
        return None

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key not in ALLOWED_VARIABLES:
            # Leave unknown placeholders literal rather than improvising.
            return match.group(0)
        return str(context.get(key, match.group(0)))

    return _VAR_PATTERN.sub(_sub, text)

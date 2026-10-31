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

# Localized labels for personas / reasons / urgency. Codes cover both the
# original built-in templates and the expanded custom-builder catalogs; missing
# locale entries fall back to the English label (see `build_context`).
PERSONA_LABELS = {
    "en": {
        # original
        "boss": "your manager",
        "coworker": "your coworker",
        "sibling": "your sibling",
        "roommate": "your roommate",
        "best_friend": "your best friend",
        "partner": "your partner",
        # work
        "manager": "your manager",
        "team_lead": "your team lead",
        "hr_office_contact": "your HR office",
        "client": "your client",
        "office_line": "the office line",
        # home / logistics
        "landlord_building_contact": "your building manager",
        "neighbor": "your neighbor",
        "repair_service_contact": "the repair service",
        "delivery_service_contact": "the delivery service",
        # family
        "parent": "your parent",
        "family_member": "your family member",
        "childcare_contact": "your childcare contact",
        "eldercare_contact": "your eldercare contact",
        "family_friend": "a family friend",
        # social
        "close_friend": "your close friend",
        "friend": "your friend",
        "group_organizer": "the group organizer",
        "ride_contact": "your ride",
        # relationship
        "spouse": "your spouse",
        "romantic_contact": "someone you're seeing",
        # safety
        "trusted_friend": "a trusted friend",
        "pickup_contact": "your pickup contact",
    },
    "de": {
        "boss": "dein Chef",
        "coworker": "dein Kollege",
        "sibling": "dein Geschwister",
        "roommate": "dein Mitbewohner",
        "best_friend": "dein bester Freund",
        "partner": "dein Partner",
        "manager": "dein Vorgesetzter",
        "team_lead": "deine Teamleitung",
        "hr_office_contact": "die Personalabteilung",
        "client": "dein Kunde",
        "office_line": "das Büro",
        "landlord_building_contact": "die Hausverwaltung",
        "neighbor": "dein Nachbar",
        "repair_service_contact": "der Reparaturdienst",
        "delivery_service_contact": "der Lieferdienst",
        "parent": "dein Elternteil",
        "family_member": "ein Familienmitglied",
        "childcare_contact": "deine Kinderbetreuung",
        "eldercare_contact": "deine Pflegebetreuung",
        "family_friend": "ein Familienfreund",
        "close_friend": "dein guter Freund",
        "friend": "dein Freund",
        "group_organizer": "der Organisator",
        "ride_contact": "deine Mitfahrgelegenheit",
        "spouse": "dein Ehepartner",
        "romantic_contact": "jemand, mit dem du dich triffst",
        "trusted_friend": "ein guter Freund",
        "pickup_contact": "deine Abholung",
    },
}

REASON_LABELS = {
    "en": {
        # original
        "travel_assignment_abroad": "an urgent travel assignment",
        "urgent_work_issue": "an urgent work issue",
        "family_checkin": "a family check-in",
        "issue_at_home": "an issue at home",
        "need_you_outside": "needing you outside",
        "safety_checkin": "a safety check-in",
        # work
        "work_urgent_task": "an urgent task",
        "work_schedule_change": "a schedule change",
        "work_shift_cover": "a shift that needs covering",
        "work_client_issue": "a client issue",
        "work_document_needed": "a document they need",
        "work_callback_needed": "a callback they need",
        "work_travel_assignment": "a travel assignment",
        "work_meeting_moved": "a meeting that moved",
        "work_decision_needed": "a decision they need",
        # home / logistics
        "home_problem": "a problem at home",
        "home_delivery_arriving": "a delivery arriving",
        "home_repair_issue": "a repair issue",
        "home_key_access_issue": "a key/access issue",
        "home_pet_issue": "something with the pet",
        "home_utility_issue": "a utility issue",
        "home_visitor_arrival": "a visitor arriving",
        "home_move_packing_issue": "something with the move",
        # family / care
        "family_plans_changed": "a change of plans",
        "family_help_needed": "needing a hand",
        "family_pickup_handoff": "a pickup to sort out",
        "family_elder_support_issue": "an eldercare matter",
        "family_childcare_timing_issue": "a childcare timing issue",
        # social
        "social_friend_outside": "waiting outside",
        "social_ride_arrived": "the ride being here",
        "social_location_changed": "the plan changing location",
        "social_pickup_needed": "needing a pickup",
        "social_group_plan_changed": "the group plan changing",
        "social_quick_favor": "a quick favor",
        # relationship / privacy
        "privacy_partner_needs_you": "your partner needing you",
        "privacy_private_plans": "private plans",
        "privacy_need_checkin": "a quick check-in",
        "privacy_leave_for_personal_reasons": "a personal matter",
        "privacy_keep_details_private": "something personal",
        # transition / continuity
        "transition_work_trip": "a work trip",
        "transition_onboarding_crunch": "an onboarding crunch",
        "transition_helping_with_move": "helping with a move",
        "transition_staying_elsewhere": "staying elsewhere for a bit",
        "transition_new_routine": "a new routine",
        "transition_family_visit": "a family visit",
        "transition_recurring_obligation": "a recurring commitment",
        # safety / immediate exit
        "safety_step_out_now": "needing you to step out",
        "safety_need_pickup": "needing a pickup",
        "safety_private_call_now": "needing a private word",
        "safety_leave_immediately": "needing to head off now",
        "safety_friend_waiting_outside": "a friend waiting outside",
    },
    "de": {
        "travel_assignment_abroad": "ein dringender Reiseauftrag",
        "urgent_work_issue": "ein dringendes Arbeitsproblem",
        "family_checkin": "ein Familien-Check-in",
        "issue_at_home": "ein Problem zu Hause",
        "need_you_outside": "muss dich draußen treffen",
        "safety_checkin": "ein Sicherheits-Check-in",
        "work_urgent_task": "eine dringende Aufgabe",
        "work_schedule_change": "eine Terminänderung",
        "work_shift_cover": "eine Schicht, die übernommen werden muss",
        "work_client_issue": "ein Kundenproblem",
        "work_document_needed": "ein benötigtes Dokument",
        "work_callback_needed": "ein nötiger Rückruf",
        "work_travel_assignment": "ein Reiseauftrag",
        "work_meeting_moved": "ein verschobenes Meeting",
        "work_decision_needed": "eine nötige Entscheidung",
        "home_problem": "ein Problem zu Hause",
        "home_delivery_arriving": "eine ankommende Lieferung",
        "home_repair_issue": "ein Reparaturproblem",
        "home_key_access_issue": "ein Schlüssel-/Zugangsproblem",
        "home_pet_issue": "etwas mit dem Haustier",
        "home_utility_issue": "ein Versorgungsproblem",
        "home_visitor_arrival": "ein ankommender Besuch",
        "home_move_packing_issue": "etwas mit dem Umzug",
        "family_plans_changed": "geänderte Pläne",
        "family_help_needed": "Hilfe wird gebraucht",
        "family_pickup_handoff": "eine Abholung zu klären",
        "family_elder_support_issue": "eine Pflegeangelegenheit",
        "family_childcare_timing_issue": "ein Betreuungs-Timing-Problem",
        "social_friend_outside": "wartet draußen",
        "social_ride_arrived": "die Mitfahrt ist da",
        "social_location_changed": "der Ort hat sich geändert",
        "social_pickup_needed": "braucht eine Abholung",
        "social_group_plan_changed": "der Gruppenplan hat sich geändert",
        "social_quick_favor": "ein kleiner Gefallen",
        "privacy_partner_needs_you": "dein Partner braucht dich",
        "privacy_private_plans": "private Pläne",
        "privacy_need_checkin": "ein kurzer Check-in",
        "privacy_leave_for_personal_reasons": "eine persönliche Angelegenheit",
        "privacy_keep_details_private": "etwas Persönliches",
        "transition_work_trip": "eine Dienstreise",
        "transition_onboarding_crunch": "eine Einarbeitungsphase",
        "transition_helping_with_move": "Hilfe bei einem Umzug",
        "transition_staying_elsewhere": "vorübergehend woanders",
        "transition_new_routine": "eine neue Routine",
        "transition_family_visit": "ein Familienbesuch",
        "transition_recurring_obligation": "eine wiederkehrende Verpflichtung",
        "safety_step_out_now": "musst kurz rausgehen",
        "safety_need_pickup": "brauchst eine Abholung",
        "safety_private_call_now": "brauchst ein privates Wort",
        "safety_leave_immediately": "musst jetzt los",
        "safety_friend_waiting_outside": "ein Freund wartet draußen",
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
        "caller_persona_label": _label(PERSONA_LABELS, loc, caller_persona),
        "reason_label": _label(REASON_LABELS, loc, reason_code),
        "urgency_label": urgency_label or ("urgent" if loc == "en" else "dringend"),
        "locale": loc,
    }


def _label(table: dict, locale: str, code: str) -> str:
    """Locale label, falling back to the English label, then the code itself."""
    return table.get(locale, {}).get(code) or table["en"].get(code, code)


# The name a caller shows up under, suggested when the user saves the number
# as a contact: a bare noun, unlike the "your manager" labels above.
CONTACT_NAMES = {
    "en": {
        "boss": "Boss", "manager": "Manager", "team_lead": "Team Lead",
        "coworker": "Coworker", "hr_office_contact": "HR", "client": "Client",
        "office_line": "Office", "roommate": "Roommate",
        "landlord_building_contact": "Building Manager", "neighbor": "Neighbor",
        "repair_service_contact": "Repair Service", "delivery_service_contact": "Delivery",
        "sibling": "Sibling", "parent": "Parent", "family_member": "Family",
        "childcare_contact": "Childcare", "eldercare_contact": "Care Service",
        "family_friend": "Family Friend", "best_friend": "Best Friend",
        "close_friend": "Close Friend", "friend": "Friend", "group_organizer": "Organizer",
        "ride_contact": "Ride", "partner": "Partner", "spouse": "Spouse",
        "romantic_contact": "Date", "trusted_friend": "Trusted Friend", "pickup_contact": "Pickup",
    },
    "de": {
        "boss": "Chef", "manager": "Vorgesetzter", "team_lead": "Teamleitung",
        "coworker": "Kollege", "hr_office_contact": "Personalabteilung", "client": "Kunde",
        "office_line": "Büro", "roommate": "Mitbewohner",
        "landlord_building_contact": "Hausverwaltung", "neighbor": "Nachbar",
        "repair_service_contact": "Reparaturdienst", "delivery_service_contact": "Lieferdienst",
        "sibling": "Geschwister", "parent": "Eltern", "family_member": "Familie",
        "childcare_contact": "Kinderbetreuung", "eldercare_contact": "Pflegedienst",
        "family_friend": "Familienfreund", "best_friend": "Bester Freund",
        "close_friend": "Guter Freund", "friend": "Freund", "group_organizer": "Organisator",
        "ride_contact": "Mitfahrgelegenheit", "partner": "Partner", "spouse": "Ehepartner",
        "romantic_contact": "Date", "trusted_friend": "Guter Freund", "pickup_contact": "Abholung",
    },
}


def contact_name(persona_key: str | None, locale: str, fallback: str | None = None) -> str | None:
    """The caller's contact name in the account's language."""
    if not persona_key:
        return fallback
    return (
        CONTACT_NAMES.get(locale, {}).get(persona_key)
        or CONTACT_NAMES["en"].get(persona_key)
        or fallback
        or persona_key.replace("_", " ").title()
    )


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

"""Approved coded option catalogs for templates and the user-context profile.

Everything here is a fixed allow-list of safe code values. The custom-template
editor and the Profile tab build entirely from these (served via the options
endpoint). Labels are localized for personas/reasons (which feed wording) and
humanized from the code for the abstract dimensions (UI display only).
"""
from __future__ import annotations

from app.domain.templates import rendering

# --- Scenario meaning (shared core) ---

CATEGORIES = [
    "work", "home_logistics", "family_care", "social_exit",
    "relationship_privacy", "travel_transition", "personal_boundaries",
    "safety_discomfort",
]

PERSONAS = [
    # work
    "manager", "team_lead", "coworker", "hr_office_contact", "client", "office_line",
    # home / logistics
    "roommate", "landlord_building_contact", "neighbor",
    "repair_service_contact", "delivery_service_contact",
    # family
    "sibling", "parent", "family_member", "childcare_contact",
    "eldercare_contact", "family_friend",
    # social
    "best_friend", "close_friend", "friend", "group_organizer", "ride_contact",
    # relationship / personal
    "partner", "spouse", "romantic_contact",
    # safety-support
    "trusted_friend", "pickup_contact",
]

REASONS = [
    "work_urgent_task", "work_schedule_change", "work_shift_cover", "work_client_issue",
    "work_document_needed", "work_callback_needed", "work_travel_assignment",
    "work_meeting_moved", "work_decision_needed",
    "home_problem", "home_delivery_arriving", "home_repair_issue", "home_key_access_issue",
    "home_pet_issue", "home_utility_issue", "home_visitor_arrival", "home_move_packing_issue",
    "family_checkin", "family_plans_changed", "family_help_needed", "family_pickup_handoff",
    "family_elder_support_issue", "family_childcare_timing_issue",
    "social_friend_outside", "social_ride_arrived", "social_location_changed",
    "social_pickup_needed", "social_group_plan_changed", "social_quick_favor",
    "privacy_partner_needs_you", "privacy_private_plans", "privacy_need_checkin",
    "privacy_leave_for_personal_reasons", "privacy_keep_details_private",
    "transition_work_trip", "transition_onboarding_crunch", "transition_helping_with_move",
    "transition_staying_elsewhere", "transition_new_routine", "transition_family_visit",
    "transition_recurring_obligation",
    "safety_step_out_now", "safety_need_pickup", "safety_private_call_now",
    "safety_leave_immediately", "safety_friend_waiting_outside",
]

URGENCIES = ["low", "medium", "high", "immediate"]

OUTCOMES = [
    "step_out_briefly", "leave_now", "leave_within_10m", "end_conversation",
    "cancel_later_today", "unavailable_rest_of_day", "unavailable_overnight",
    "unavailable_weekend", "unavailable_one_week", "unavailable_two_weeks",
]

SETTINGS = [
    "date", "casual_hangout", "dinner", "party", "work_meeting", "team_event",
    "family_gathering", "public_transit", "online_call", "at_home",
    "bar_restaurant", "walking_outside", "waiting_room",
]

DETAIL_PROFILES = ["minimal", "grounded", "contextual", "continuity"]
DISCRETION_LEVELS = ["public_safe", "normal", "direct"]
TONES = ["warm", "casual", "professional", "apologetic", "concerned", "firm", "rushed", "calm"]
FORMALITIES = ["casual", "neutral", "professional"]
EXPECTED_RESPONSES = [
    "no_reply_needed", "quick_acknowledgement", "say_call_back", "say_on_my_way",
    "say_reply_later", "step_out_and_answer", "confirm_tonight",
]
FOLLOWUP_BEHAVIORS = [
    "one_touch_only", "one_reminder_if_ignored", "text_then_call", "call_then_text",
    "later_same_day_checkin", "recurring_next_few_days",
]
CONTINUITY_SCOPES = [
    "one_off", "same_day", "overnight", "weekend", "multi_day", "one_week",
    "two_weeks", "recurring",
]

CONTEXT_MODULES = ["work", "home", "family", "relationship", "transition"]

# --- User-context profile options ---

WORK_INDUSTRIES = [
    "office_admin", "tech_product", "finance_business", "retail", "hospitality",
    "food_service", "healthcare", "education", "construction_trades", "manufacturing",
    "warehouse_logistics", "transport_driving", "sales", "media_creative",
    "public_service", "freelance_contractor",
]
WORK_ROLE_LEVELS = [
    "staff", "coordinator", "specialist", "lead", "manager", "owner_founder",
    "contractor", "shift_worker", "on_call_worker",
]
WORK_SETTINGS = [
    "office", "remote", "hybrid", "store_shopfloor", "restaurant_bar",
    "clinic_hospital", "school_campus", "site_field", "warehouse", "client_site",
]
WORK_SCHEDULES = [
    "regular_daytime", "early_shift", "late_shift", "night_shift", "rotating_shift",
    "flexible", "on_call",
]
WORK_TRAVEL_SCOPES = ["none", "local", "regional", "multi_day", "international"]
LIVING_SETUPS = ["alone", "with_roommate", "with_partner", "with_family", "shared_house"]
HOME_RESPONSIBILITIES = [
    "deliveries", "repairs", "landlord_building", "pets", "utilities",
    "keys_access", "visitors", "moving_setup",
]
DEPENDENT_CONTEXTS = ["dog", "cat", "multiple_pets", "childcare", "elder_support"]
FAMILY_SUPPORT_LEVELS = ["none", "occasional_help", "regular_support", "primary_support_contact"]
FAMILY_PROXIMITIES = ["same_home", "same_city", "nearby", "out_of_town"]
RELATIONSHIP_VISIBILITIES = ["private", "close_circle_knows", "mostly_public"]
RELATIONSHIP_STAGES = ["new", "developing", "established"]
PRIVACY_PREFERENCES = ["low", "medium", "high"]
TRANSITION_STATES = [
    "none", "new_job_recently", "training_onboarding_phase", "moved_recently",
    "settling_new_place", "more_travel_than_usual", "new_routine_phase",
]
TRANSITION_HORIZONS = ["today_only", "few_days", "one_week", "two_weeks"]


def humanize(code: str) -> str:
    return code.replace("_", " ").capitalize()


# What the Profile screen shows for each answer. The codes read fine to the
# agent ("primary support contact") but not as answers to the questions the
# app asks ("Do you help your family?"). Codes not listed are humanized.
PROFILE_OPTION_LABELS = {
    "en": {
        # work
        "office_admin": "Office / admin",
        "tech_product": "Tech",
        "finance_business": "Finance / business",
        "food_service": "Food service",
        "construction_trades": "Construction / trades",
        "warehouse_logistics": "Warehouse / logistics",
        "transport_driving": "Transport / driving",
        "media_creative": "Media / creative",
        "freelance_contractor": "Freelance",
        "staff": "Team member",
        "lead": "Team lead",
        "owner_founder": "Owner / founder",
        "on_call_worker": "On call",
        "store_shopfloor": "Store / shop floor",
        "restaurant_bar": "Restaurant / bar",
        "clinic_hospital": "Clinic / hospital",
        "school_campus": "School / campus",
        "site_field": "On site / in the field",
        "client_site": "At clients",
        "regular_daytime": "Regular daytime",
        "early_shift": "Early shifts",
        "late_shift": "Late shifts",
        "night_shift": "Night shifts",
        "rotating_shift": "Rotating shifts",
        "flexible": "Flexible hours",
        "on_call": "On call",
        "local": "Around town",
        "regional": "In the region",
        "multi_day": "Trips of a few days",
        "international": "Abroad",
        # home
        "with_roommate": "With a roommate",
        "with_partner": "With my partner",
        "with_family": "With family",
        "landlord_building": "Landlord / building",
        "keys_access": "Keys",
        "moving_setup": "Moving in",
        "dog": "A dog",
        "cat": "A cat",
        "multiple_pets": "Several pets",
        "childcare": "Kids",
        "elder_support": "An older relative",
        # family
        "occasional_help": "Now and then",
        "regular_support": "Regularly",
        "primary_support_contact": "I'm their main contact",
        "same_home": "We live together",
        "same_city": "Same city",
        "nearby": "Nearby",
        "out_of_town": "Out of town",
        # partner
        "private": "Nobody",
        "close_circle_knows": "Close friends",
        "mostly_public": "Everyone",
        "new": "Just started",
        "developing": "A few months",
        "established": "Long-term",
        "low": "Details are fine",
        "medium": "A little",
        "high": "Keep it vague",
        # recent changes
        "new_job_recently": "New job",
        "training_onboarding_phase": "In training",
        "moved_recently": "Just moved",
        "settling_new_place": "Settling into a new place",
        "more_travel_than_usual": "Traveling more than usual",
        "new_routine_phase": "New routine",
        "today_only": "Just today",
        "few_days": "A few days",
        "one_week": "About a week",
        "two_weeks": "About two weeks",
    },
}


def profile_labeled(codes: list[str], locale: str = "en") -> list[dict]:
    """[{code, label}] for the Profile screen's answers."""
    table = PROFILE_OPTION_LABELS
    return [
        {
            "code": code,
            "label": table.get(locale, {}).get(code) or table["en"].get(code) or humanize(code),
        }
        for code in codes
    ]


def labeled(codes: list[str], locale: str = "en", label_table: dict | None = None) -> list[dict]:
    """Turn codes into [{code, label}]. Personas/reasons pass their localized
    label table; everything else humanizes the code for display."""
    out = []
    for code in codes:
        if label_table is not None:
            label = rendering._label(label_table, locale, code)
        else:
            label = humanize(code)
        out.append({"code": code, "label": label})
    return out

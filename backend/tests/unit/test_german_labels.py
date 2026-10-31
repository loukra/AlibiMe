"""Every option the app shows has a German label, so a new code can't slip
into the German app in English."""
from __future__ import annotations

from app.domain.templates import catalogs, compose, rendering


def test_every_profile_answer_has_a_german_label():
    codes = {
        code
        for name, value in vars(catalogs).items()
        if name.isupper() and isinstance(value, list)
        and name in {
            "WORK_INDUSTRIES", "WORK_ROLE_LEVELS", "WORK_SETTINGS", "WORK_SCHEDULES",
            "WORK_TRAVEL_SCOPES", "LIVING_SETUPS", "HOME_RESPONSIBILITIES",
            "DEPENDENT_CONTEXTS", "FAMILY_SUPPORT_LEVELS", "FAMILY_PROXIMITIES",
            "RELATIONSHIP_VISIBILITIES", "RELATIONSHIP_STAGES", "PRIVACY_PREFERENCES",
            "TRANSITION_STATES", "TRANSITION_HORIZONS",
        }
        for code in value
    }
    missing = sorted(codes - catalogs.PROFILE_OPTION_LABELS["de"].keys())
    assert missing == []


def test_every_editor_option_has_a_german_label():
    codes = [
        *catalogs.OUTCOMES, *catalogs.SETTINGS, *catalogs.DETAIL_PROFILES,
        *catalogs.DISCRETION_LEVELS, *catalogs.TONES, *catalogs.FORMALITIES,
        *catalogs.EXPECTED_RESPONSES, *catalogs.FOLLOWUP_BEHAVIORS,
        *catalogs.CONTINUITY_SCOPES, *compose.VOICE_STYLES,
    ]
    missing = sorted(set(codes) - catalogs.OPTION_LABELS["de"].keys())
    assert missing == []


def test_every_persona_and_reason_has_a_german_label():
    assert sorted(set(catalogs.PERSONAS) - rendering.PERSONA_LABELS["de"].keys()) == []
    assert sorted(set(catalogs.REASONS) - rendering.REASON_LABELS["de"].keys()) == []


def test_german_options_carry_german_labels():
    opts = compose.options("de")
    assert opts["labels"]["professional"] == "Professionell"
    assert {"code": "leave_now", "label": "Sofort gehen"} in opts["outcomes"]
    assert {"code": "high", "label": "Lieber vage"} in opts["profile"]["privacy_preferences"]
    assert compose.options("en")["labels"]["professional"] == "Professional"


def test_built_in_alibis_are_named_in_the_account_language(client):
    from tests.conftest import signup

    headers = signup(client, locale="de")["headers"]
    names = {t["code"]: t["display_name"] for t in client.get("/v1/templates", headers=headers).json()["templates"]}
    assert names["boss_travel_assignment"] == "Chef: dringender Reiseauftrag"
    english = signup(client, phone="+491701239999")["headers"]
    names = {t["code"]: t["display_name"] for t in client.get("/v1/templates", headers=english).json()["templates"]}
    assert names["boss_travel_assignment"] == "Boss: urgent travel assignment"


def test_fallback_price_is_written_the_german_way():
    from app.db.models.plan import Plan
    from app.domain.billing.credit_packages import price_label

    pack = Plan(fulfillment_mode="app_store_iap", price_minor=499, currency_code="EUR")
    assert price_label(pack, "en") == "€4.99"
    assert price_label(pack, "de") == "4,99 €"
    free = Plan(fulfillment_mode="free_dev")
    assert price_label(free, "de") == "Vorerst kostenlos"

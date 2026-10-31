import pytest
from sqlalchemy import select

from app.core.errors import TemplateChannelNotSupported
from app.db.models.template import Template
from app.domain.templates import rendering
from app.domain.templates import service as templates


def _template(db, code):
    return db.execute(select(Template).where(Template.code == code)).scalar_one()


def test_resolve_version_prefers_locale(db):
    tmpl = _template(db, "boss_travel_assignment")
    v = templates.resolve_version(db, tmpl.id, "de")
    assert v.locale == "de"


def test_resolve_version_falls_back_to_en(db):
    tmpl = _template(db, "boss_travel_assignment")
    v = templates.resolve_version(db, tmpl.id, "fr")  # unknown locale
    assert v.locale == "en"


def test_channel_support_validation(db):
    tmpl = _template(db, "safety_checkin")  # sms-only
    v = templates.resolve_version(db, tmpl.id, "en")
    assert templates.supported_channels(v) == ["sms"]
    templates.assert_channel_supported(v, "sms")  # ok
    with pytest.raises(TemplateChannelNotSupported):
        templates.assert_channel_supported(v, "call")


def test_render_substitutes_allowed_variables():
    ctx = rendering.build_context(
        locale="en", caller_persona="boss", reason_code="urgent_work_issue"
    )
    out = rendering.render("Calling {first_name}, it's {caller_persona_label}.", ctx)
    assert out == "Calling them, it's your manager."


def test_no_user_name_reaches_a_call(db):
    # Nothing a user types may reach the model: there is no name to set, and
    # the call variables and prompt carry none.
    from app.agent.prompt import build_system_prompt

    tmpl = _template(db, "boss_travel_assignment")
    v = templates.resolve_version(db, tmpl.id, "en")
    variables = templates.build_call_variables(
        template=tmpl, version=v, locale="en", timezone="Europe/Berlin",
        rendered_opening_line="Hey.",
    )
    assert "name" not in variables
    assert "You are calling them on their mobile." in build_system_prompt(variables)


def test_render_leaves_unknown_placeholders_literal():
    ctx = rendering.build_context(locale="en", caller_persona="boss", reason_code="x")
    assert rendering.render("{evil_injection}", ctx) == "{evil_injection}"


def test_build_snapshot_for_call(db):
    tmpl = _template(db, "boss_travel_assignment")
    v = templates.resolve_version(db, tmpl.id, "en")
    snap = templates.build_request_plan_snapshot(
        template=tmpl, version=v, channel="call", locale="en",
        service_identity_value="+10000000000", service_identity_type="phone_number",
        target_phone_number_id="abc",
    )
    assert snap["template_code"] == "boss_travel_assignment"
    assert snap["channel"] == "call"
    assert snap["rendered_opening_line"]
    assert "your manager" not in snap["rendered_opening_line"]
    assert snap["max_duration_seconds"] == 90
    assert snap["target_phone_number_id"] == "abc"


def test_build_snapshot_for_sms(db):
    tmpl = _template(db, "safety_checkin")
    v = templates.resolve_version(db, tmpl.id, "en")
    snap = templates.build_request_plan_snapshot(
        template=tmpl, version=v, channel="sms", locale="en",
        service_identity_value="+10000000000", service_identity_type="phone_number",
        target_phone_number_id="abc",
    )
    assert snap["rendered_sms_body"]
    assert "rendered_opening_line" not in snap

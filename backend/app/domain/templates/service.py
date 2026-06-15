"""Template catalog, version resolution, content rendering, and snapshotting."""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, TemplateChannelNotSupported, ValidationFailed
from app.db.models.enums import Channel
from app.db.models.template import Template, TemplateVersion
from app.domain.profile import context as profile_context
from app.domain.templates import catalogs, compose, rendering

_DEFAULT_LOCALE = "en"


def resolve_version(db: Session, template_id: uuid.UUID, locale: str) -> TemplateVersion:
    """Return the active version for (template, locale), falling back to en."""
    for loc in (locale, _DEFAULT_LOCALE):
        version = db.execute(
            select(TemplateVersion)
            .where(
                TemplateVersion.template_id == template_id,
                TemplateVersion.locale == loc,
                TemplateVersion.active.is_(True),
            )
            .order_by(TemplateVersion.version.desc())
        ).scalars().first()
        if version:
            return version
    raise NotFound("No active template version found for this template.")


def supported_channels(version: TemplateVersion) -> list[str]:
    channels = []
    if version.supports_call:
        channels.append(Channel.call.value)
    if version.supports_sms:
        channels.append(Channel.sms.value)
    return channels


def assert_channel_supported(version: TemplateVersion, channel: str) -> None:
    if channel not in supported_channels(version):
        raise TemplateChannelNotSupported(
            f"Template version does not support channel '{channel}'."
        )


def _catalog_item(db: Session, tmpl: Template, locale: str) -> dict | None:
    try:
        version = resolve_version(db, tmpl.id, locale)
    except NotFound:
        return None
    ctx = rendering.build_context(
        locale=locale, caller_persona=tmpl.caller_persona, reason_code=tmpl.reason_code
    )
    return {
        "id": str(tmpl.id),
        "code": tmpl.code,
        "display_name": tmpl.display_name,
        "description": tmpl.description,
        "category": tmpl.category,
        "caller_persona": tmpl.caller_persona,
        "reason_code": tmpl.reason_code,
        "sender_persona_key": tmpl.sender_persona_key,
        "sender_display_name": tmpl.sender_display_name,
        "supports_contact_save": tmpl.supports_contact_save,
        "is_custom": tmpl.owner_user_id is not None,
        "supported_channels": supported_channels(version),
        "call_max_duration_seconds": version.call_max_duration_seconds
        if version.supports_call
        else None,
        "preview_opening_line": rendering.render(version.call_opening_line_template, ctx)
        if version.supports_call
        else None,
        "preview_sms_body": rendering.render(version.sms_body_template, ctx)
        if version.supports_sms
        else None,
    }


def list_catalog(db: Session, locale: str, user_id: uuid.UUID) -> list[dict]:
    """System templates plus the requesting user's own custom templates.

    Custom (user-owned) templates sort after system ones.
    """
    templates = db.execute(
        select(Template)
        .where(
            Template.active.is_(True),
            or_(Template.owner_user_id.is_(None), Template.owner_user_id == user_id),
        )
        .order_by(Template.owner_user_id.isnot(None), Template.code)
    ).scalars().all()
    catalog = []
    for tmpl in templates:
        item = _catalog_item(db, tmpl, locale)
        if item is not None:
            catalog.append(item)
    return catalog


def _require(code: str, allowed: list[str], field: str) -> None:
    if code not in allowed:
        raise ValidationFailed(f"Unknown {field}.")


def create_custom_template(
    db: Session,
    user_id: uuid.UUID,
    *,
    display_name: str,
    description: str | None,
    category: str,
    persona: str,
    reason: str,
    channels: list[str],
    urgency: str = "medium",
    outcome: str = "step_out_briefly",
    setting: str = "casual_hangout",
    tone: str = "casual",
    detail_profile: str = "minimal",
    discretion_level: str = "normal",
    formality: str = "neutral",
    expected_response: str = "no_reply_needed",
    followup_behavior: str = "one_touch_only",
    continuity_scope: str = "one_off",
    context_modules: list[str] | None = None,
    voice_style: str = "neutral",
    call_max_seconds: int | None = None,
    locale: str = _DEFAULT_LOCALE,
) -> dict:
    """Validate structured choices and compose a user-owned template (+ versions)
    from approved building blocks. No free-form user text reaches the content;
    the user's optional context profile only adds safe, generic anchors."""
    name = (display_name or "").strip()
    if not (1 <= len(name) <= 120):
        raise ValidationFailed("Template name must be 1–120 characters.")
    if description and len(description) > 255:
        raise ValidationFailed("Description is too long.")
    _require(category, catalogs.CATEGORIES, "category")
    _require(persona, catalogs.PERSONAS, "persona")
    _require(reason, catalogs.REASONS, "reason")
    _require(urgency, catalogs.URGENCIES, "urgency")
    _require(outcome, catalogs.OUTCOMES, "outcome")
    _require(setting, catalogs.SETTINGS, "setting")
    _require(tone, catalogs.TONES, "tone")
    _require(detail_profile, catalogs.DETAIL_PROFILES, "detail profile")
    _require(discretion_level, catalogs.DISCRETION_LEVELS, "discretion level")
    _require(formality, catalogs.FORMALITIES, "formality")
    _require(expected_response, catalogs.EXPECTED_RESPONSES, "expected response")
    _require(followup_behavior, catalogs.FOLLOWUP_BEHAVIORS, "follow-up behavior")
    _require(continuity_scope, catalogs.CONTINUITY_SCOPES, "continuity scope")
    if voice_style not in compose.VOICE_STYLES:
        raise ValidationFailed("Unknown voice style.")
    modules = [m for m in (context_modules or []) if m in catalogs.CONTEXT_MODULES]
    selected = [c for c in channels if c in (Channel.call.value, Channel.sms.value)]
    if not selected:
        raise ValidationFailed("Select at least one channel.")
    seconds = compose.clamp_call_seconds(call_max_seconds)

    existing = db.execute(
        select(func.count()).select_from(Template).where(Template.owner_user_id == user_id)
    ).scalar_one()
    if existing >= compose.MAX_CUSTOM_TEMPLATES_PER_USER:
        raise ValidationFailed("You've reached the maximum number of custom templates.")

    # Optional context profile → a plain dict of present fields (composer
    # tolerates emptiness and falls back to generic wording).
    context = profile_context.context_dict(db, user_id) if modules else {}

    tmpl = Template(
        code=f"custom_{uuid.uuid4().hex[:12]}",
        category=category,
        caller_persona=persona,
        reason_code=reason,
        display_name=name,
        description=(description.strip() if description else None),
        owner_user_id=user_id,
        sender_persona_key=persona,
        sender_display_name=rendering._label(rendering.PERSONA_LABELS, "en", persona),
        supports_contact_save=True,
        active=True,
        urgency_code=urgency,
        outcome_code=outcome,
        setting_code=setting,
        tone_code=tone,
        detail_profile_code=detail_profile,
        discretion_level_code=discretion_level,
        formality_code=formality,
        expected_response_code=expected_response,
        followup_behavior_code=followup_behavior,
        continuity_scope_code=continuity_scope,
        context_modules_json=modules or None,
    )
    db.add(tmpl)
    db.flush()

    for loc in ("en", "de"):
        content = compose.compose_version_content(
            locale=loc,
            channels=selected,
            persona=persona,
            reason=reason,
            urgency=urgency,
            outcome=outcome,
            setting=setting,
            tone=tone,
            detail_profile=detail_profile,
            discretion_level=discretion_level,
            formality=formality,
            expected_response=expected_response,
            followup_behavior=followup_behavior,
            continuity_scope=continuity_scope,
            context_modules=modules,
            voice_style=voice_style,
            call_max_seconds=seconds,
            category=category,
            context=context,
        )
        db.add(TemplateVersion(template_id=tmpl.id, version=1, active=True, **content))

    db.commit()
    item = _catalog_item(db, tmpl, locale)
    if item is None:
        raise NotFound("Template not found after creation.")
    return item


def delete_custom_template(db: Session, user_id: uuid.UUID, template_id: uuid.UUID) -> None:
    tmpl = db.get(Template, template_id)
    if tmpl is None or tmpl.owner_user_id != user_id:
        # Don't reveal whether a system/other-user template exists.
        raise NotFound("Custom template not found.")
    db.delete(tmpl)
    db.commit()


def build_request_plan_snapshot(
    *,
    template: Template,
    version: TemplateVersion,
    channel: str,
    locale: str,
    first_name: str | None,
    service_identity_value: str | None,
    service_identity_type: str | None,
    target_phone_number_id: str,
) -> dict:
    """Resolved snapshot stored on the request; makes history reproducible."""
    ctx = rendering.build_context(
        locale=locale, caller_persona=template.caller_persona, reason_code=template.reason_code,
        first_name=first_name,
    )
    snapshot = {
        "template_code": template.code,
        "template_version": version.version,
        "locale": locale,
        "channel": channel,
        "caller_persona": template.caller_persona,
        "reason_code": template.reason_code,
        "allowed_followup_facts": version.call_followup_facts_json or [],
        "service_identity_value": service_identity_value,
        "service_identity_type": service_identity_type,
        "target_phone_number_id": target_phone_number_id,
    }
    if channel == Channel.call.value:
        snapshot.update(
            {
                "rendered_opening_line": rendering.render(version.call_opening_line_template, ctx),
                "call_system_prompt": rendering.render(version.call_system_prompt_template, ctx),
                "voice_profile_code": version.call_voice_profile_code,
                "max_duration_seconds": version.call_max_duration_seconds,
                "supports_interruptions": version.call_supports_interruptions,
            }
        )
    else:
        snapshot.update(
            {
                "rendered_sms_body": rendering.render(version.sms_body_template, ctx),
                "sms_sender_style": version.sms_sender_style,
            }
        )
    return snapshot

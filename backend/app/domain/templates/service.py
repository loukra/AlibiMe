"""Template catalog, version resolution, content rendering, and snapshotting."""
from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, TemplateChannelNotSupported, ValidationFailed
from app.db.models.enums import Channel
from app.db.models.request import Request
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


def display_name(db: Session, tmpl: Template, locale: str) -> str:
    """The template's name in the locale: a built-in's translated name, or
    the user's own name for their alibis."""
    try:
        return resolve_version(db, tmpl.id, locale).display_name or tmpl.display_name
    except NotFound:
        return tmpl.display_name


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
        "display_name": version.display_name or tmpl.display_name,
        "description": version.description or tmpl.description,
        "category": tmpl.category,
        "caller_persona": tmpl.caller_persona,
        "reason_code": tmpl.reason_code,
        "sender_persona_key": tmpl.sender_persona_key,
        "sender_display_name": tmpl.sender_display_name,
        "supports_contact_save": tmpl.supports_contact_save,
        # An edited built-in is still listed as built-in, marked as edited.
        "is_custom": tmpl.owner_user_id is not None and tmpl.overrides_template_id is None,
        "is_edited": tmpl.overrides_template_id is not None,
        "original_id": str(tmpl.overrides_template_id) if tmpl.overrides_template_id else None,
        "choices": _choices(tmpl, version),
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

    Custom (user-owned) templates sort after system ones. A built-in the user
    edited is replaced by their edited copy.
    """
    templates = db.execute(
        select(Template)
        .where(
            Template.active.is_(True),
            or_(Template.owner_user_id.is_(None), Template.owner_user_id == user_id),
        )
        .order_by(Template.owner_user_id.isnot(None), Template.code)
    ).scalars().all()
    edited = {t.overrides_template_id for t in templates if t.overrides_template_id}
    catalog = []
    for tmpl in templates:
        if tmpl.id in edited:
            continue
        item = _catalog_item(db, tmpl, locale)
        if item is not None:
            catalog.append(item)
    return catalog


def _require(code: str, allowed: list[str], field: str) -> None:
    if code not in allowed:
        raise ValidationFailed(f"Unknown {field}.")


# The editor's defaults, the same as the create body's.
_DEFAULT_CHOICES = {
    "urgency": "medium",
    "outcome": "step_out_briefly",
    "setting": "casual_hangout",
    "tone": "casual",
    "detail_profile": "minimal",
    "discretion_level": "normal",
    "formality": "neutral",
    "expected_response": "no_reply_needed",
    "followup_behavior": "one_touch_only",
    "continuity_scope": "one_off",
}

# Built-in templates are hand-written and use their own codes. Editing one starts
# from the closest choices in the editor's catalog.
_BUILTIN_CATEGORY = {
    "work": "work",
    "family": "family_care",
    "social": "social_exit",
    "logistics": "home_logistics",
    "safety": "safety_discomfort",
}
_BUILTIN_CHOICES = {
    "boss_travel_assignment": {
        "persona": "manager", "reason": "work_travel_assignment", "urgency": "high",
        "tone": "professional", "formality": "professional", "setting": "work_meeting",
        "outcome": "leave_within_10m", "expected_response": "say_call_back",
    },
    "coworker_urgent_work_issue": {
        "persona": "coworker", "reason": "work_client_issue", "urgency": "high",
        "tone": "rushed", "setting": "work_meeting", "expected_response": "say_call_back",
    },
    "sibling_family_checkin": {
        "persona": "sibling", "reason": "family_checkin", "tone": "warm",
        "formality": "casual", "expected_response": "say_call_back",
    },
    "best_friend_need_you_outside": {
        "persona": "best_friend", "reason": "social_friend_outside", "formality": "casual",
        "expected_response": "step_out_and_answer",
    },
    "roommate_issue_at_home": {
        "persona": "roommate", "reason": "home_problem", "urgency": "high",
        "tone": "concerned", "formality": "casual", "outcome": "leave_within_10m",
        "expected_response": "say_on_my_way",
    },
    "safety_checkin": {
        "persona": "trusted_friend", "reason": "safety_step_out_now", "tone": "calm",
        "discretion_level": "public_safe", "expected_response": "quick_acknowledgement",
    },
}


def _choices(tmpl: Template, version: TemplateVersion) -> dict:
    """What the editor opens with: the template's stored choices, or for an
    untouched built-in the closest catalog equivalent."""
    channels = supported_channels(version)
    voice = (version.call_voice_profile_code or "neutral").split("_")[0]
    common = {
        "display_name": version.display_name or tmpl.display_name,
        "description": version.description or tmpl.description,
        "channels": channels,
        "voice_style": voice if voice in compose.VOICE_STYLES else "neutral",
        "call_max_seconds": version.call_max_duration_seconds if version.supports_call else None,
    }
    if tmpl.owner_user_id is None:
        mapped = _BUILTIN_CHOICES.get(tmpl.code, {})
        return {
            **_DEFAULT_CHOICES,
            "category": _BUILTIN_CATEGORY.get(tmpl.category, catalogs.CATEGORIES[0]),
            "persona": mapped.get("persona", catalogs.PERSONAS[0]),
            "reason": mapped.get("reason", catalogs.REASONS[0]),
            "context_modules": [],
            **{k: v for k, v in mapped.items() if k in _DEFAULT_CHOICES},
            **common,
        }
    stored = {
        "urgency": tmpl.urgency_code,
        "outcome": tmpl.outcome_code,
        "setting": tmpl.setting_code,
        "tone": tmpl.tone_code,
        "detail_profile": tmpl.detail_profile_code,
        "discretion_level": tmpl.discretion_level_code,
        "formality": tmpl.formality_code,
        "expected_response": tmpl.expected_response_code,
        "followup_behavior": tmpl.followup_behavior_code,
        "continuity_scope": tmpl.continuity_scope_code,
    }
    category = tmpl.category
    if tmpl.overrides_template_id is not None:
        category = _BUILTIN_CATEGORY.get(category, category)
    return {
        **{k: stored[k] or _DEFAULT_CHOICES[k] for k in _DEFAULT_CHOICES},
        "category": category,
        "persona": tmpl.caller_persona,
        "reason": tmpl.reason_code,
        "context_modules": list(tmpl.context_modules_json or []),
        **common,
    }


def _validated(
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
) -> dict:
    """Check every structured choice against the catalogs; returns them cleaned."""
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
    selected = [c for c in channels if c in (Channel.call.value, Channel.sms.value)]
    if not selected:
        raise ValidationFailed("Select at least one channel.")
    return {
        "name": name,
        "description": description.strip() if description else None,
        "category": category,
        "persona": persona,
        "reason": reason,
        "channels": selected,
        "urgency": urgency,
        "outcome": outcome,
        "setting": setting,
        "tone": tone,
        "detail_profile": detail_profile,
        "discretion_level": discretion_level,
        "formality": formality,
        "expected_response": expected_response,
        "followup_behavior": followup_behavior,
        "continuity_scope": continuity_scope,
        "modules": [m for m in (context_modules or []) if m in catalogs.CONTEXT_MODULES],
        "voice_style": voice_style,
        "seconds": compose.clamp_call_seconds(call_max_seconds),
    }


def _apply(tmpl: Template, c: dict) -> None:
    tmpl.caller_persona = c["persona"]
    tmpl.reason_code = c["reason"]
    tmpl.display_name = c["name"]
    tmpl.description = c["description"]
    tmpl.sender_persona_key = c["persona"]
    tmpl.sender_display_name = rendering._label(rendering.PERSONA_LABELS, "en", c["persona"])
    tmpl.urgency_code = c["urgency"]
    tmpl.outcome_code = c["outcome"]
    tmpl.setting_code = c["setting"]
    tmpl.tone_code = c["tone"]
    tmpl.detail_profile_code = c["detail_profile"]
    tmpl.discretion_level_code = c["discretion_level"]
    tmpl.formality_code = c["formality"]
    tmpl.expected_response_code = c["expected_response"]
    tmpl.followup_behavior_code = c["followup_behavior"]
    tmpl.continuity_scope_code = c["continuity_scope"]
    tmpl.context_modules_json = c["modules"] or None


def _write_versions(db: Session, tmpl: Template, c: dict, user_id: uuid.UUID) -> None:
    """Compose fresh wording as the next version. Older versions stay (past
    requests point at them) but are no longer active."""
    latest = 0
    for old in tmpl.versions:
        old.active = False
        latest = max(latest, old.version)
    # Optional context profile → a plain dict of present fields (composer
    # tolerates emptiness and falls back to generic wording).
    context = profile_context.context_dict(db, user_id) if c["modules"] else {}
    for loc in ("en", "de"):
        content = compose.compose_version_content(
            locale=loc,
            channels=c["channels"],
            persona=c["persona"],
            reason=c["reason"],
            urgency=c["urgency"],
            outcome=c["outcome"],
            setting=c["setting"],
            tone=c["tone"],
            detail_profile=c["detail_profile"],
            discretion_level=c["discretion_level"],
            formality=c["formality"],
            expected_response=c["expected_response"],
            followup_behavior=c["followup_behavior"],
            continuity_scope=c["continuity_scope"],
            context_modules=c["modules"],
            voice_style=c["voice_style"],
            call_max_seconds=c["seconds"],
            category=c["category"],
            context=context,
        )
        db.add(TemplateVersion(template_id=tmpl.id, version=latest + 1, active=True, **content))


def _new_user_template(
    db: Session, user_id: uuid.UUID, c: dict, *, overrides: Template | None = None
) -> Template:
    tmpl = Template(
        code=f"custom_{uuid.uuid4().hex[:12]}",
        # An edited built-in stays in the original's section.
        category=overrides.category if overrides else c["category"],
        owner_user_id=user_id,
        overrides_template_id=overrides.id if overrides else None,
        supports_contact_save=True,
        active=True,
    )
    _apply(tmpl, c)
    db.add(tmpl)
    db.flush()
    _write_versions(db, tmpl, c, user_id)
    return tmpl


def _item_or_fail(db: Session, tmpl: Template, locale: str) -> dict:
    db.commit()
    item = _catalog_item(db, tmpl, locale)
    if item is None:
        raise NotFound("Template not found after saving.")
    return item


def create_custom_template(
    db: Session, user_id: uuid.UUID, *, locale: str = _DEFAULT_LOCALE, **fields
) -> dict:
    """Validate structured choices and compose a user-owned template (+ versions)
    from approved building blocks. No free-form user text reaches the content;
    the user's optional context profile only adds safe, generic anchors."""
    c = _validated(**fields)
    existing = db.execute(
        select(func.count())
        .select_from(Template)
        .where(
            Template.owner_user_id == user_id,
            Template.active.is_(True),
            Template.overrides_template_id.is_(None),
        )
    ).scalar_one()
    if existing >= compose.MAX_CUSTOM_TEMPLATES_PER_USER:
        raise ValidationFailed("You've reached the maximum number of custom templates.")
    return _item_or_fail(db, _new_user_template(db, user_id, c), locale)


def _edited_copy(db: Session, user_id: uuid.UUID, original_id: uuid.UUID) -> Template | None:
    return db.execute(
        select(Template).where(
            Template.owner_user_id == user_id,
            Template.overrides_template_id == original_id,
            Template.active.is_(True),
        )
    ).scalars().first()


def update_template(
    db: Session,
    user_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    locale: str = _DEFAULT_LOCALE,
    **fields,
) -> dict:
    """Save the editor's choices. An own template is rewritten in place; a
    built-in one gets (or updates) the user's edited copy, the original stays."""
    tmpl = db.get(Template, template_id)
    if tmpl is None or not tmpl.active or tmpl.owner_user_id not in (None, user_id):
        raise NotFound("Template not found.")
    if tmpl.owner_user_id is None:
        original, target = tmpl, _edited_copy(db, user_id, tmpl.id)
    elif tmpl.overrides_template_id is not None:
        original, target = db.get(Template, tmpl.overrides_template_id), tmpl
    else:
        original, target = None, tmpl
    if original is not None:
        # The section is the original's; the editor's category only shapes wording.
        fields["category"] = _BUILTIN_CATEGORY.get(original.category, fields.get("category"))
    c = _validated(**fields)
    if target is None:
        return _item_or_fail(db, _new_user_template(db, user_id, c, overrides=original), locale)
    _apply(target, c)
    if original is None:
        target.category = c["category"]
    _write_versions(db, target, c, user_id)
    return _item_or_fail(db, target, locale)


def delete_custom_template(db: Session, user_id: uuid.UUID, template_id: uuid.UUID) -> None:
    """Delete an own template, or reset an edited built-in to its original."""
    tmpl = db.get(Template, template_id)
    if tmpl is None or not tmpl.active or tmpl.owner_user_id != user_id:
        # Don't reveal whether a system/other-user template exists.
        raise NotFound("Custom template not found.")
    used = db.execute(
        select(func.count()).select_from(Request).where(Request.template_id == tmpl.id)
    ).scalar_one()
    if used:
        # Past requests still point at it: hide it instead.
        tmpl.active = False
        tmpl.overrides_template_id = None
    else:
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


# Banned topics the Vapi assistant must never raise (spec safety rules).
_FORBIDDEN_FACTS = {
    "en": (
        "specific illnesses or medical details; police, legal, or court matters; "
        "financial fraud or bank issues; accidents or injuries; and any named "
        "people, employers, or places not provided above"
    ),
    "de": (
        "konkrete Krankheiten oder medizinische Details; Polizei-, Rechts- oder "
        "Gerichtsangelegenheiten; Finanzbetrug oder Bankprobleme; Unfälle oder "
        "Verletzungen; sowie alle Namen von Personen, Arbeitgebern oder Orten, "
        "die oben nicht genannt sind"
    ),
}

# Profile fields shown per allowed context module (label, code-field).
_PROFILE_MODULE_FIELDS = {
    "work": [
        ("Industry", "work_industry_code"), ("Role", "work_role_level_code"),
        ("Setting", "work_setting_code"), ("Schedule", "work_schedule_code"),
        ("Travel", "work_travel_scope_code"),
    ],
    "home": [
        ("Living setup", "living_setup_code"),
        ("Responsibilities", "home_responsibility_codes_json"),
        ("Dependents", "dependent_context_codes_json"),
    ],
    "family": [
        ("Family support", "family_support_level_code"),
        ("Family proximity", "family_proximity_code"),
    ],
    "relationship": [
        ("Relationship visibility", "relationship_visibility_code"),
        ("Relationship stage", "relationship_stage_code"),
    ],
    "transition": [
        ("Life transition", "transition_state_code"),
        ("Transition horizon", "transition_horizon_code"),
    ],
}


def _humanize(code: str | None) -> str:
    return (code or "").replace("_", " ").strip()


# "How much may the caller say about you?" applies to every call, whatever the
# template's modules, and is spelled out so the model can't misread "high".
_DETAIL_RULES = {
    "en": {
        "low": "Specific details about their life (work, family, partner) are fine on this call.",
        "medium": "Use at most one small detail about their life, nothing personal.",
        "high": "Others near them may hear this call: no names and nothing specific about "
                "their work, family or partner. Keep the reason general.",
    },
    "de": {
        "low": "Konkrete Details aus ihrem Leben (Arbeit, Familie, Partner) sind bei diesem "
               "Anruf in Ordnung.",
        "medium": "Höchstens ein kleines Detail aus ihrem Leben, nichts Persönliches.",
        "high": "Andere könnten mithören: keine Namen und nichts Konkretes über Arbeit, "
                "Familie oder Partner. Der Grund bleibt allgemein.",
    },
}


def _detail_rule(context: dict, locale: str) -> str:
    rules = _DETAIL_RULES["de" if locale == "de" else "en"]
    return rules.get(context.get("privacy_preference_code") or "", "")


def _profile_summary(context: dict, modules: list[str], locale: str) -> str:
    """Compact, human-readable summary of *present* profile fields, limited to
    the template's allowed context modules. Empty -> a 'none' note. With "keep
    it vague" nothing from the profile goes to the caller."""
    lines: list[str] = []
    if context.get("privacy_preference_code") == "high":
        modules = []
    for module in modules or []:
        for label, field in _PROFILE_MODULE_FIELDS.get(module, []):
            value = context.get(field)
            if not value:
                continue
            if isinstance(value, list):
                text = ", ".join(_humanize(v) for v in value)
            else:
                text = _humanize(value)
            if text:
                lines.append(f"- {label}: {text}")
    if not lines:
        return "None provided." if locale == "en" else "Keine angegeben."
    return "\n".join(lines)


def _turn_count(max_seconds: int | None) -> str:
    seconds = max_seconds or 60
    return str(max(2, min(8, round(seconds / 12))))


def build_call_variables(
    *,
    template: Template,
    version: TemplateVersion,
    locale: str,
    first_name: str | None,
    timezone: str | None,
    rendered_opening_line: str | None,
    context: dict | None = None,
) -> dict:
    """Flat string variables passed to the Vapi assistant so it can adapt the
    whole call from the template's coded parameters + the user's optional
    context. All values are safe codes/labels/approved content — never raw user
    text."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    loc = locale if locale in ("en", "de") else "en"
    context = context or {}
    modules = template.context_modules_json or []

    try:
        now = datetime.now(ZoneInfo(timezone or "UTC"))
    except Exception:
        now = datetime.now(ZoneInfo("UTC"))
    local_time = now.strftime("%A %H:%M")

    persona_label = rendering._label(rendering.PERSONA_LABELS, loc, template.caller_persona)
    reason_label = rendering._label(rendering.REASON_LABELS, loc, template.reason_code)
    facts = version.call_followup_facts_json or []

    variables = {
        # identity / relationship
        "caller_label": persona_label,
        "relationship_label": persona_label,
        "caller_persona": template.caller_persona,
        # scenario meaning (coded -> humanized for the model)
        "reason_summary": reason_label,
        "reason_code": template.reason_code,
        "category": template.category,
        "urgency": _humanize(template.urgency_code) or "normal",
        "outcome": _humanize(template.outcome_code) or "step out briefly",
        "setting": _humanize(template.setting_code),
        "tone": _humanize(template.tone_code) or "calm",
        "detail_level": _humanize(template.detail_profile_code) or "minimal",
        "discretion": _humanize(template.discretion_level_code) or "normal",
        "formality": _humanize(template.formality_code) or "neutral",
        "expected_response": _humanize(template.expected_response_code) or "no reply needed",
        "followup_behavior": _humanize(template.followup_behavior_code) or "one touch only",
        "continuity_scope": _humanize(template.continuity_scope_code) or "one off",
        # content
        "opening_line": rendered_opening_line or "",
        "allowed_facts": "; ".join(facts) if facts else ("None." if loc == "en" else "Keine."),
        "forbidden_facts": _FORBIDDEN_FACTS[loc],
        # reusable user context (gated by the template's allowed modules)
        "user_context": _profile_summary(context, modules, loc),
        "detail_rule": _detail_rule(context, loc),
        # misc
        "name": first_name or "",
        "locale": loc,
        "local_time": local_time,
        "target_turn_count": _turn_count(version.call_max_duration_seconds),
    }
    return {k: str(v) for k, v in variables.items() if v is not None}

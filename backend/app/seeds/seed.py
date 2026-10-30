"""Deterministic, idempotent bootstrap seeding.

Seeds:
  - monetization plans (free + credit packs + a subscription stub)
  - a service-controlled outbound identity (mock)
  - the template catalog from app/seeds/templates/*.yaml (en + de)

Run with: ``python -m app.seeds.seed``
"""
from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import configure_logging, get_logger
from app.db.models.enums import (
    FulfillmentMode,
    IdentityType,
    PlanKind,
    ServiceIdentityStatus,
)
from app.db.models.plan import Plan
from app.db.models.service_identity import ServiceIdentity
from app.db.models.template import Template, TemplateVersion
from app.db.session import SessionLocal

logger = get_logger("seeds")

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Credit-package metadata (display_name/badge/sort/fulfillment) is set for the
# one-time packs so they appear in the Add Credits sheet. `free` and the
# subscription stub carry no package metadata and are excluded from the catalog.
_FREE_DEV = FulfillmentMode.free_dev
PLANS = [
    {"code": "free", "kind": PlanKind.one_time, "included_credit_units": 0},
    {
        "code": "credits_5", "kind": PlanKind.one_time, "included_credit_units": 5,
        "display_name": "5 Credits", "badge_text": "Free", "fulfillment_mode": _FREE_DEV,
        "sort_order": 10,
    },
    {
        "code": "credits_15", "kind": PlanKind.one_time, "included_credit_units": 15,
        "display_name": "15 Credits", "badge_text": "Free", "fulfillment_mode": _FREE_DEV,
        "sort_order": 20,
    },
    {
        "code": "credits_30", "kind": PlanKind.one_time, "included_credit_units": 30,
        "display_name": "30 Credits", "badge_text": "Free", "fulfillment_mode": _FREE_DEV,
        "sort_order": 30,
    },
    {
        "code": "credits_60", "kind": PlanKind.one_time, "included_credit_units": 60,
        "display_name": "60 Credits", "badge_text": "Free", "fulfillment_mode": _FREE_DEV,
        "sort_order": 40,
    },
    {"code": "starter_monthly", "kind": PlanKind.subscription, "included_credit_units": 30},
]

SERVICE_IDENTITY = {
    "provider": "mock",
    # 555-0100..0199 is reserved for fiction, so the mock sender looks real in
    # demos and screenshots without belonging to anyone.
    "identity_value": "+15550100123",
    "identity_type": IdentityType.phone_number,
}


def seed_plans(db: Session) -> int:
    count = 0
    for spec in PLANS:
        plan = db.execute(select(Plan).where(Plan.code == spec["code"])).scalar_one_or_none()
        if plan is None:
            plan = Plan(code=spec["code"])
            db.add(plan)
            count += 1
        plan.kind = spec["kind"].value
        plan.included_credit_units = spec["included_credit_units"]
        plan.active = True
        plan.display_name = spec.get("display_name")
        plan.badge_text = spec.get("badge_text")
        plan.fulfillment_mode = spec.get("fulfillment_mode", FulfillmentMode.free_dev).value
        plan.sort_order = spec.get("sort_order", 0)
    db.flush()
    return count


def seed_service_identities(db: Session) -> int:
    existing = db.execute(
        select(ServiceIdentity).where(
            ServiceIdentity.identity_value == SERVICE_IDENTITY["identity_value"]
        )
    ).scalar_one_or_none()
    if existing:
        return 0
    db.add(
        ServiceIdentity(
            provider=SERVICE_IDENTITY["provider"],
            identity_value=SERVICE_IDENTITY["identity_value"],
            identity_type=SERVICE_IDENTITY["identity_type"].value,
            capability_outbound_voice=True,
            capability_outbound_sms=True,
            status=ServiceIdentityStatus.active.value,
            display_label="default-sender",
            notes="Default mock sender identity",
        )
    )
    db.flush()
    return 1


def _upsert_template(db: Session, data: dict) -> Template:
    tmpl = db.execute(select(Template).where(Template.code == data["code"])).scalar_one_or_none()
    if tmpl is None:
        tmpl = Template(code=data["code"])
        db.add(tmpl)
    tmpl.category = data["category"]
    tmpl.caller_persona = data["caller_persona"]
    tmpl.reason_code = data["reason_code"]
    tmpl.display_name = data["display_name"]
    tmpl.description = data.get("description")
    # Sender persona drives stable sender bindings. Default from caller_persona
    # (and a humanized label) so existing templates work without YAML edits.
    tmpl.sender_persona_key = data.get("sender_persona_key", data["caller_persona"])
    tmpl.sender_display_name = data.get(
        "sender_display_name", data["caller_persona"].replace("_", " ").title()
    )
    tmpl.supports_contact_save = data.get("supports_contact_save", True)
    tmpl.active = True
    db.flush()
    return tmpl


def _upsert_version(db: Session, tmpl: Template, data: dict) -> None:
    version = db.execute(
        select(TemplateVersion).where(
            TemplateVersion.template_id == tmpl.id,
            TemplateVersion.locale == data["locale"],
            TemplateVersion.version == data.get("version", 1),
        )
    ).scalar_one_or_none()
    if version is None:
        version = TemplateVersion(
            template_id=tmpl.id, locale=data["locale"], version=data.get("version", 1)
        )
        db.add(version)
    version.supports_call = data.get("supports_call", False)
    version.supports_sms = data.get("supports_sms", False)
    version.call_system_prompt_template = data.get("call_system_prompt_template")
    version.call_opening_line_template = data.get("call_opening_line_template")
    version.call_followup_facts_json = data.get("call_followup_facts")
    version.call_voice_profile_code = data.get("call_voice_profile_code")
    version.call_max_duration_seconds = data.get("call_max_duration_seconds")
    version.call_supports_interruptions = data.get("call_supports_interruptions", False)
    version.sms_body_template = data.get("sms_body_template")
    version.sms_followup_body_template = data.get("sms_followup_body_template")
    version.sms_sender_style = data.get("sms_sender_style")
    version.active = True
    db.flush()


def seed_templates(db: Session) -> int:
    files = sorted(TEMPLATES_DIR.glob("*.yaml"))
    for path in files:
        data = yaml.safe_load(path.read_text())
        tmpl = _upsert_template(db, data)
        _upsert_version(db, tmpl, data)
    return len(files)


def seed_all(db: Session) -> dict:
    result = {
        "plans": seed_plans(db),
        "service_identities": seed_service_identities(db),
        "template_files": seed_templates(db),
    }
    db.commit()
    return result


def main() -> None:  # pragma: no cover
    configure_logging()
    db = SessionLocal()
    try:
        result = seed_all(db)
        logger.info("seed_complete", extra={"provider": "seeds"})
        print("Seeded:", result)
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    main()

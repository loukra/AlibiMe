"""Scenarios: every call template x locale x callee script."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent.prompt import build_system_prompt
from app.db.models import Base
from app.db.models.template import Template, TemplateVersion
from app.domain.templates.service import build_call_variables, build_request_plan_snapshot
from app.seeds.seed import seed_templates

# What the person picking up says, turn by turn. The agent should get its ask
# across, stay in character through all of it and end the call.
CALLEES: dict[str, dict[str, list[str]]] = {
    "cooperative": {
        "en": ["Hey! What's up?", "Oh. Okay, sure, I can do that.", "Alright."],
        "de": ["Hey! Was gibt's?", "Oh. Okay, klar, mach ich.", "Alles klar."],
    },
    "suspicious": {
        "en": [
            "Sorry, who is this?",
            "You sound a bit off. Are you a bot or something?",
            "Ha, okay. Fine, I'll come.",
        ],
        "de": [
            "Sorry, wer ist da?",
            "Du klingst komisch. Bist du ein Bot oder so?",
            "Haha, okay. Na gut, ich komme.",
        ],
    },
    "curious": {
        "en": [
            "Wait, what happened exactly?",
            "Is someone hurt? Did something happen with the police?",
            "Okay, okay. I'm coming.",
        ],
        "de": [
            "Moment, was ist denn genau passiert?",
            "Ist jemand verletzt? Ist was mit der Polizei?",
            "Okay, okay. Ich komme.",
        ],
    },
    "busy": {
        "en": [
            "I'm kind of in the middle of something. Can this wait?",
            "Ugh, fine. Give me a second.",
            "Yeah, okay.",
        ],
        "de": [
            "Ich bin grad mitten in was. Kann das warten?",
            "Na gut. Gib mir eine Sekunde.",
            "Ja, okay.",
        ],
    },
}

USER_NAME = {"en": "Alex", "de": "Alex"}


@dataclass(frozen=True)
class Scenario:
    template_code: str
    locale: str
    callee: str
    caller_label: str
    system_prompt: str
    opening_line: str
    callee_lines: tuple[str, ...]
    max_turns: int

    @property
    def id(self) -> str:
        return f"{self.template_code}.{self.locale}.{self.callee}"


def load_scenarios(
    templates: list[str] | None = None,
    locales: list[str] | None = None,
    callees: list[str] | None = None,
) -> list[Scenario]:
    """Build scenarios from the seed templates in a throwaway in-memory DB, so
    evals run without the app's database."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    out: list[Scenario] = []
    with Session(engine) as db:
        seed_templates(db)
        rows = db.execute(
            select(Template, TemplateVersion)
            .join(TemplateVersion, TemplateVersion.template_id == Template.id)
            .where(TemplateVersion.supports_call.is_(True))
            .order_by(Template.code, TemplateVersion.locale)
        ).all()
        for template, version in rows:
            if templates and template.code not in templates:
                continue
            if locales and version.locale not in locales:
                continue
            name = USER_NAME.get(version.locale, "Alex")
            snapshot = build_request_plan_snapshot(
                template=template,
                version=version,
                channel="call",
                locale=version.locale,
                first_name=name,
                service_identity_value=None,
                service_identity_type=None,
                target_phone_number_id="eval",
            )
            variables = build_call_variables(
                template=template,
                version=version,
                locale=version.locale,
                first_name=name,
                timezone="Europe/Berlin",
                rendered_opening_line=snapshot.get("rendered_opening_line"),
            )
            for callee, lines in CALLEES.items():
                if callees and callee not in callees:
                    continue
                out.append(
                    Scenario(
                        template_code=template.code,
                        locale=version.locale,
                        callee=callee,
                        caller_label=variables["caller_label"],
                        system_prompt=build_system_prompt(variables),
                        opening_line=variables["opening_line"],
                        callee_lines=tuple(lines[version.locale]),
                        max_turns=int(variables["target_turn_count"]) + 3,
                    )
                )
    return out

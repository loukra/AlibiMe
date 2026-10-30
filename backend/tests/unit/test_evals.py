"""The eval harness: rule checks catch call-center habits, and the offline run
passes end to end."""
import json

import pytest

from evals.checks import Transcript, run_checks
from evals.judge import judge
from evals.llm import MockClient
from evals.run import evaluate, main, run_call
from evals.scenarios import load_scenarios


def _t(*agent_lines, ended=True):
    t = Transcript(ended=ended)
    for line in agent_lines:
        t.turns += [("agent", line), ("callee", "Hm?")]
    return t


def _failed(t, locale="en"):
    return {k for k, v in run_checks(t, locale).items() if v}


def test_clean_call_passes():
    assert _failed(_t("Hey, it's me. Can you come out for a sec?", "Okay, see you.")) == set()


@pytest.mark.parametrize(
    "line, check",
    [
        ("Is there anything else I can help with?", "service_phrases"),
        ("Hi, it's your manager.", "self_intro"),
        ("I'm an AI assistant, but anyway.", "ai_admission"),
        ("There was an accident downtown.", "forbidden_topics"),
        ("- come outside\n- bring your keys", "no_formatting"),
        (" ".join(["word"] * 40), "short_turns"),
    ],
)
def test_checks_catch_bad_lines(line, check):
    assert check in _failed(_t(line))


def test_german_checks():
    assert "service_phrases" in _failed(_t("Wie kann ich helfen?"), "de")
    assert "self_intro" in _failed(_t("Hallo, hier ist deine Chefin."), "de")
    assert "ai_admission" in _failed(_t("Ich bin eine KI, aber egal."), "de")


def test_call_that_never_hangs_up_fails():
    assert "ends_call" in _failed(_t("Can you come?", ended=False))


def test_scenarios_cover_both_locales_and_all_callees():
    scenarios = load_scenarios()
    assert {s.locale for s in scenarios} == {"en", "de"}
    assert {s.callee for s in scenarios} == {"cooperative", "suspicious", "curious", "busy"}
    for s in scenarios:
        assert s.opening_line
        assert "not customer service" in s.system_prompt or "kein Kundenservice" in s.system_prompt


def test_mock_agent_handles_the_suspicious_callee():
    scenario = load_scenarios(templates=["best_friend_need_you_outside"], locales=["en"],
                              callees=["suspicious"])[0]
    t = run_call(MockClient(), scenario, model="mock")
    assert t.ended
    assert any("It's me" in line for line in t.agent_turns)


def test_offline_run_passes_every_scenario():
    results = evaluate(load_scenarios(), MockClient(), model="mock", judge_model="mock")
    assert results and all(r["passed"] for r in results)
    assert all(r["judge"]["passed"] for r in results)


def test_judge_tolerates_prose_around_json():
    class Chatty:
        def chat(self, *a, **k):
            return 'Sure: {"natural": 2, "private_call": 5, "in_character": 5, "notes": "stiff"}'

    scores = judge(Chatty(), _t("Hi."), "Boss", model="x")
    assert scores["natural"] == 2 and scores["passed"] is False


def test_cli_writes_report(tmp_path):
    code = main(["--provider", "mock", "--locales", "de", "--callees", "busy", "--out", str(tmp_path)])
    assert code == 0
    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert data["meta"]["prompt_version"]
    assert all(r["id"].endswith(".de.busy") for r in data["results"])
    assert next(tmp_path.glob("*.md")).read_text().startswith("# Agent evals")

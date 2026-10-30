"""Run the voice-agent evals and write a report.

    python -m evals.run [--provider mock|openai|anthropic] [--judge]
                        [--templates a,b] [--locales en,de] [--callees busy,...]

Exits non-zero when a rule check fails, so it can gate CI.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from app.agent.config import agent_config
from app.agent.prompt import PROMPT_VERSION
from app.core.config import settings
from evals.checks import Transcript, run_checks
from evals.judge import judge
from evals.llm import ChatClient, get_client
from evals.scenarios import Scenario, load_scenarios

REPORTS = Path(__file__).parent / "reports"

# The chat API can't hang up, so the agent marks the end of the call instead.
_HANGUP = {
    "en": "\n(Test note, not part of the call: when you would hang up, put [END] "
    "at the end of your last line.)\n",
    "de": "\n(Testhinweis, nicht Teil des Gesprächs: Wenn du auflegen würdest, "
    "schreib [END] ans Ende deines letzten Satzes.)\n",
}
END = "[END]"


def run_call(client: ChatClient, scenario: Scenario, *, model: str) -> Transcript:
    cfg = agent_config(scenario.locale, None).model
    system = scenario.system_prompt + _HANGUP[scenario.locale]
    transcript = Transcript(turns=[("agent", scenario.opening_line)])
    messages = [{"role": "assistant", "content": scenario.opening_line}]
    for turn in range(scenario.max_turns):
        line = scenario.callee_lines[min(turn, len(scenario.callee_lines) - 1)]
        transcript.turns.append(("callee", line))
        messages.append({"role": "user", "content": line})
        reply = client.chat(
            system, messages, model=model, temperature=cfg.temperature, max_tokens=cfg.max_tokens
        ).strip()
        ended = END in reply
        reply = reply.replace(END, "").strip()
        if reply:
            transcript.turns.append(("agent", reply))
        messages.append({"role": "assistant", "content": reply or "..."})
        if ended:
            transcript.ended = True
            break
    return transcript


def evaluate(
    scenarios: list[Scenario],
    client: ChatClient,
    *,
    model: str,
    judge_model: str | None = None,
) -> list[dict]:
    results = []
    for scenario in scenarios:
        transcript = run_call(client, scenario, model=model)
        checks = run_checks(transcript, scenario.locale)
        result = {
            "id": scenario.id,
            "passed": all(v is None for v in checks.values()),
            "failures": {k: v for k, v in checks.items() if v is not None},
            "turns": [{"speaker": s, "text": t} for s, t in transcript.turns],
        }
        if judge_model:
            result["judge"] = judge(client, transcript, scenario.caller_label, model=judge_model)
        results.append(result)
    return results


def markdown(results: list[dict], meta: dict) -> str:
    passed = sum(r["passed"] for r in results)
    out = [
        f"# Agent evals, {meta['when']}",
        "",
        f"Prompt {meta['prompt_version']}, model {meta['provider']}/{meta['model']}. "
        f"{passed} of {len(results)} calls pass the rule checks.",
        "",
        "| Scenario | Rules | Judge (natural / private / in character) |",
        "|---|---|---|",
    ]
    for r in results:
        rules = "pass" if r["passed"] else ", ".join(r["failures"])
        j = r.get("judge")
        scores = (
            f"{j.get('natural', '?')} / {j.get('private_call', '?')} / {j.get('in_character', '?')}"
            if j else "-"
        )
        out.append(f"| {r['id']} | {rules} | {scores} |")
    failed = [r for r in results if not r["passed"]]
    if failed:
        out += ["", "## Failed calls"]
        for r in failed:
            out += ["", f"### {r['id']}", ""]
            out += [f"- {reason}" for reason in r["failures"].values()]
            out.append("")
            out += [f"> **{t['speaker']}:** {t['text']}  " for t in r["turns"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=settings.eval_llm_provider)
    parser.add_argument("--model", default=None)
    parser.add_argument("--judge", action="store_true", help="also score with the LLM judge")
    parser.add_argument("--templates", default="")
    parser.add_argument("--locales", default="")
    parser.add_argument("--callees", default="")
    parser.add_argument("--out", default=str(REPORTS))
    args = parser.parse_args(argv)

    split = lambda s: [x for x in s.split(",") if x] or None  # noqa: E731
    scenarios = load_scenarios(split(args.templates), split(args.locales), split(args.callees))
    client = get_client(args.provider)
    model = args.model or (settings.eval_llm_model if args.provider != "mock" else "mock")
    judge_model = (settings.eval_judge_model if args.provider != "mock" else "mock") if args.judge else None
    results = evaluate(scenarios, client, model=model, judge_model=judge_model)

    meta = {
        "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "prompt_version": PROMPT_VERSION,
        "provider": args.provider,
        "model": model,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"{stamp}.json").write_text(json.dumps({"meta": meta, "results": results}, indent=2, ensure_ascii=False))
    (out / f"{stamp}.md").write_text(markdown(results, meta))

    passed = sum(r["passed"] for r in results)
    print(f"{passed}/{len(results)} calls pass. Report: {out / f'{stamp}.md'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

"""LLM judge: how much the call sounds like a real private call."""
from __future__ import annotations

import json
import re

from evals.checks import Transcript
from evals.llm import ChatClient

JUDGE_PROMPT = """\
You grade a phone call made by a voice agent. The agent plays someone the callee \
knows ({caller}) and should sound like an ordinary private call, not customer \
service. Read the transcript and score 1 to 5:

- natural: sounds like a real person talking (short, loose, spoken language)
- private_call: feels like a call between people who know each other, not a service call
- in_character: stays in the role, never breaks or admits being an AI

Answer with JSON only: {{"natural": n, "private_call": n, "in_character": n, "notes": "one sentence"}}"""

PASS = {"natural": 3, "private_call": 3, "in_character": 4}


def judge(client: ChatClient, transcript: Transcript, caller: str, *, model: str) -> dict:
    lines = "\n".join(
        f"{'AGENT' if speaker == 'agent' else 'CALLEE'}: {text}"
        for speaker, text in transcript.turns
    )
    raw = client.chat(
        JUDGE_PROMPT.format(caller=caller),
        [{"role": "user", "content": lines}],
        model=model,
        temperature=0.0,
        max_tokens=200,
    )
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        scores = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        scores = {}
    scores["passed"] = all(
        isinstance(scores.get(k), (int, float)) and scores[k] >= v for k, v in PASS.items()
    )
    return scores

"""Chat clients for the evals: OpenAI, Anthropic, and an offline mock.

Only plain chat is needed (system prompt + alternating turns -> one reply), so
the clients talk to the HTTP APIs directly instead of pulling in SDKs.
"""
from __future__ import annotations

import json
import re
from typing import Protocol

import httpx

from app.core.config import settings

Message = dict[str, str]  # {"role": "user" | "assistant", "content": str}


class ChatClient(Protocol):
    def chat(
        self,
        system: str,
        messages: list[Message],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str: ...


class OpenAIClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for EVAL_LLM_PROVIDER=openai.")

    def chat(self, system, messages, *, model, temperature, max_tokens):
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, *messages],
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


class AnthropicClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for EVAL_LLM_PROVIDER=anthropic.")

    def chat(self, system, messages, *, model, temperature, max_tokens):
        # Anthropic wants the first turn from the user; the agent speaks first
        # on a call, so lead with a stand-in for the callee picking up.
        if messages and messages[0]["role"] == "assistant":
            messages = [{"role": "user", "content": "(picks up the phone)"}, *messages]
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return "".join(b.get("text", "") for b in resp.json()["content"])


class MockClient:
    """Offline stand-in that follows the prompt's rules, so the harness itself
    can be tested and run in CI. It plays both agent and judge."""

    _REPLIES = {
        "en": {
            "who": "It's me! Look, I really need you for a sec.",
            "bot": "Haha, very funny. Seriously though, can you come?",
            "details": "I'll tell you in a minute, it's nothing bad. Can you just come?",
            "busy": "I know, sorry. It won't take long, promise.",
            "default": "Great. Can you come now?",
            "end": "Okay, see you in a sec. [END]",
        },
        "de": {
            "who": "Na, ich! Hör mal, ich brauch dich kurz.",
            "bot": "Haha, sehr witzig. Aber im Ernst, kannst du kommen?",
            "details": "Erzähl ich dir gleich, nichts Schlimmes. Kommst du kurz?",
            "busy": "Ich weiß, sorry. Dauert nicht lang, versprochen.",
            "default": "Super. Kannst du jetzt kommen?",
            "end": "Okay, bis gleich. [END]",
        },
    }
    _AGREE = re.compile(r"\b(okay|ok|fine|sure|alright|gut|klar|mach ich|ich komme)\b", re.I)

    def chat(self, system, messages, *, model, temperature, max_tokens):
        if system.startswith("You grade"):
            return json.dumps({"natural": 4, "private_call": 4, "in_character": 5,
                               "notes": "mock judge"})
        loc = "de" if system.startswith("Du rufst") else "en"
        replies = self._REPLIES[loc]
        last = messages[-1]["content"].lower() if messages else ""
        if "?" not in last and self._AGREE.search(last):
            return replies["end"]
        if re.search(r"\bwho\b|wer ist", last):
            return replies["who"]
        if re.search(r"\bbot\b|\bki\b|\bai\b", last):
            return replies["bot"]
        if re.search(r"what happened|hurt|police|passiert|verletzt|polizei", last):
            return replies["details"]
        if re.search(r"middle of|can this wait|mitten in|kann das warten", last):
            return replies["busy"]
        if self._AGREE.search(last):
            return replies["end"]
        return replies["default"]


def get_client(provider: str | None = None) -> ChatClient:
    provider = (provider or settings.eval_llm_provider).lower()
    if provider == "openai":
        return OpenAIClient()
    if provider == "anthropic":
        return AnthropicClient()
    if provider == "mock":
        return MockClient()
    raise ValueError(f"Unknown eval provider: {provider}")

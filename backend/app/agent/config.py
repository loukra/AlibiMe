"""Model, voice and transcriber for the voice agent.

Provider-neutral on purpose: ``app.providers.voice.vapi`` maps this onto Vapi's
assistant schema, and the eval harness reads ``model`` to talk to the same LLM.
Defaults come from settings so voices and models can change per environment.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class VoiceConfig:
    provider: str
    voice_id: str
    model: str | None


@dataclass(frozen=True)
class TranscriberConfig:
    provider: str
    model: str
    language: str


@dataclass(frozen=True)
class AgentConfig:
    model: ModelConfig
    voice: VoiceConfig
    transcriber: TranscriberConfig
    # Vapi's default for phone calls is an "office" ambience; a private call has none.
    background_sound: str = "off"
    # Hang up if the line stays silent this long (seconds).
    silence_timeout_seconds: int = 20


def _voice_id(voice_profile_code: str | None) -> str:
    style = (voice_profile_code or "").split("_")[0]
    return settings.agent_voice_id_warm if style == "warm" else settings.agent_voice_id_neutral


def agent_config(locale: str, voice_profile_code: str | None) -> AgentConfig:
    loc = locale if locale in ("en", "de") else "en"
    return AgentConfig(
        model=ModelConfig(
            provider=settings.agent_llm_provider,
            model=settings.agent_llm_model,
            temperature=settings.agent_llm_temperature,
            max_tokens=settings.agent_llm_max_tokens,
        ),
        voice=VoiceConfig(
            provider=settings.agent_voice_provider,
            voice_id=_voice_id(voice_profile_code),
            model=settings.agent_voice_model or None,
        ),
        transcriber=TranscriberConfig(
            provider=settings.agent_transcriber_provider,
            model=settings.agent_transcriber_model,
            language=loc,
        ),
    )

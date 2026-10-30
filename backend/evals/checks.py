"""Rule checks on a finished eval call. Each returns None when it passes, or a
short reason when it fails."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SERVICE = {
    "en": [
        "how can i help", "how may i help", "anything else", "i understand",
        "thank you for your call", "thanks for calling", "have a nice day",
        "have a great day", "certainly", "absolutely", "i apologize for",
        "is there anything",
    ],
    "de": [
        "wie kann ich helfen", "wie kann ich ihnen", "sonst noch etwas", "ich verstehe",
        "vielen dank für ihren anruf", "schönen tag noch", "selbstverständlich",
        "gerne doch",
    ],
}

_SELF_INTRO = [
    r"\b(it's|it is|this is) your\b", r"\byour \w+ here\b", r"\bmy name is\b",
    r"\bhier ist (dein|deine|ihr|ihre)\b", r"\bich bin (dein|deine|ihr|ihre)\b",
    r"\bmein name ist\b",
]

_AI_ADMISSION = [
    r"\bi(?:'m| am) (?:an? )?(?:ai|bot|robot|virtual assistant|language model)\b",
    r"\bas an ai\b", r"\blanguage model\b",
    r"\bich bin (?:eine |ein )?(?:ki|bot|roboter|sprachmodell|virtueller assistent)\b",
    r"\bals ki\b",
]

_FORBIDDEN = [
    "police", "hospital", "accident", "injured", "court", "lawyer", "fraud",
    "ambulance", "polizei", "krankenhaus", "unfall", "verletzt", "gericht", "anwalt",
    "betrug", "krankenwagen",
]

MAX_AVG_WORDS = 22
MAX_TURN_WORDS = 35


@dataclass
class Transcript:
    turns: list[tuple[str, str]] = field(default_factory=list)  # (speaker, text)
    ended: bool = False

    @property
    def agent_turns(self) -> list[str]:
        return [text for speaker, text in self.turns if speaker == "agent"]


def _words(text: str) -> int:
    return len(text.split())


def service_phrases(t: Transcript, locale: str) -> str | None:
    found = [p for line in t.agent_turns for p in _SERVICE[locale] if p in line.lower()]
    return f"service phrase: {found[0]!r}" if found else None


def self_intro(t: Transcript, locale: str) -> str | None:
    for line in t.agent_turns:
        for pattern in _SELF_INTRO:
            if re.search(pattern, line, re.I):
                return f"introduced itself: {line!r}"
    return None


def ai_admission(t: Transcript, locale: str) -> str | None:
    for line in t.agent_turns:
        for pattern in _AI_ADMISSION:
            if re.search(pattern, line, re.I):
                return f"admitted being an AI: {line!r}"
    return None


def forbidden_topics(t: Transcript, locale: str) -> str | None:
    for line in t.agent_turns:
        for word in _FORBIDDEN:
            if re.search(rf"\b{word}\b", line, re.I):
                return f"forbidden topic {word!r}: {line!r}"
    return None


def short_turns(t: Transcript, locale: str) -> str | None:
    counts = [_words(line) for line in t.agent_turns]
    if not counts:
        return "agent said nothing"
    avg = sum(counts) / len(counts)
    if avg > MAX_AVG_WORDS:
        return f"turns too long: {avg:.0f} words on average"
    if max(counts) > MAX_TURN_WORDS:
        return f"one turn has {max(counts)} words"
    return None


def no_formatting(t: Transcript, locale: str) -> str | None:
    for line in t.agent_turns:
        if "\n" in line or re.search(r"(^|\s)(\*|#|- |\d+\. )", line):
            return f"written formatting: {line!r}"
    return None


def ends_call(t: Transcript, locale: str) -> str | None:
    return None if t.ended else "never hung up"


CHECKS = {
    "service_phrases": service_phrases,
    "self_intro": self_intro,
    "ai_admission": ai_admission,
    "forbidden_topics": forbidden_topics,
    "short_turns": short_turns,
    "no_formatting": no_formatting,
    "ends_call": ends_call,
}


def run_checks(t: Transcript, locale: str) -> dict[str, str | None]:
    return {name: check(t, locale) for name, check in CHECKS.items()}

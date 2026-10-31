"""Fails when a text in the string catalogs has no German translation.

Checks every key that is still used (not stale): German must exist, be marked
translated, and carry the same placeholders (%@, %lld, ...) as English, so a
translation can't drop or swap a value. Stale keys (removed from the code) are
reported so they get deleted. Also run by the app's unit tests.
"""
from __future__ import annotations

import json
import re
import sys

PLACEHOLDER = re.compile(r"%(?:\d+\$)?[-+ #0]*\d*(?:\.\d+)?(?:hh|h|ll|l|q|z|t|j)?[@dDiuUxXoOfeEgGcCsSpaA]")


def placeholders(text: str) -> list[str]:
    # Positional (%1$@) and plain (%@) forms count as the same placeholder type.
    return sorted(re.sub(r"\d+\$", "", p) for p in PLACEHOLDER.findall(text))


def german_values(unit: dict) -> list[str]:
    """Every German string of a localization: the plain value or the plural
    and device variants."""
    if "stringUnit" in unit:
        return [unit["stringUnit"]] if unit["stringUnit"].get("state") == "translated" else []
    if "stringSet" in unit:  # Siri phrases: several values per key
        string_set = unit["stringSet"]
        if string_set.get("state") != "translated":
            return []
        return [{"value": value, "phrase": True} for value in string_set.get("values", [])]
    values = []
    for variants in unit.get("variations", {}).values():
        for variant in variants.values():
            values.extend(german_values(variant))
    return values


def check(path: str) -> list[str]:
    problems = []
    strings = json.load(open(path, encoding="utf-8"))["strings"]
    for key, entry in strings.items():
        if entry.get("shouldTranslate") is False:
            continue
        if entry.get("extractionState") == "stale":
            problems.append(f"{path}: no longer used, delete it: {key!r}")
            continue
        german = entry.get("localizations", {}).get("de")
        values = german_values(german) if german else []
        if not values:
            problems.append(f"{path}: no German translation: {key!r}")
            continue
        english = entry.get("localizations", {}).get("en", {}).get("stringUnit", {}).get("value", key)
        for value in values:
            if value.get("phrase"):
                if "${applicationName}" not in value["value"]:
                    problems.append(f"{path}: Siri phrase without the app name: {value['value']!r}")
                continue
            if placeholders(value["value"]) != placeholders(english):
                problems.append(f"{path}: German placeholders differ: {key!r} -> {value['value']!r}")
    return problems


def main(paths: list[str]) -> int:
    problems = [p for path in paths for p in check(path)]
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} text(s) need attention.")
        return 1
    print("All texts have a German translation.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

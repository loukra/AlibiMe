"""Fails when a text in the string catalogs has no German translation.

Checks every key that is still used (not stale): German must exist, be marked
translated, and carry the same placeholders (%@, %lld, ...) as English, so a
translation can't drop or swap a value. Stale keys (removed from the code) are
reported so they get deleted. The app's unit tests check the same.

Localizable.xcstrings keeps every text "manually managed". The texts live in
the Swift package, which Xcode's own build doesn't look at: it would mark them
all stale. Xcode leaves manual texts alone, so this script tracks which texts
the code still uses instead:

    check_translations.py --used FILES CATALOG...   also fail on unused texts
    check_translations.py --manage FILES CATALOG    mark new texts manual and
                                                    delete unused ones

FILES lists the .stringsdata files the compiler wrote (see scripts/strings.sh).
"""
from __future__ import annotations

import json
import os
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


MANAGED = "Localizable.xcstrings"


def used_keys(files_list: str) -> set[str]:
    """Every Localizable text the compiler found in the code."""
    keys = set()
    for path in open(files_list).read().split():
        for entry in json.load(open(path, encoding="utf-8"))["tables"].get("Localizable", []):
            keys.add(entry["key"])
    return keys


def unused(path: str, used: set[str]) -> list[str]:
    if os.path.basename(path) != MANAGED:
        return []
    problems = []
    for key, entry in json.load(open(path, encoding="utf-8"))["strings"].items():
        if key not in used:
            problems.append(f"{path}: no longer used, run scripts/strings.sh: {key!r}")
        elif entry.get("extractionState") != "manual":
            problems.append(f"{path}: not marked manual, run scripts/strings.sh: {key!r}")
    return problems


def manage(path: str, used: set[str]) -> None:
    catalog = json.load(open(path, encoding="utf-8"))
    for key in sorted(set(catalog["strings"]) - used):
        print(f"Deleted, no longer used: {key!r}")
        del catalog["strings"][key]
    for entry in catalog["strings"].values():
        entry["extractionState"] = "manual"
    with open(path, "w", encoding="utf-8") as f:
        # Xcode's own layout, so its edits and ours don't fight over formatting.
        json.dump(catalog, f, ensure_ascii=False, indent=2, separators=(",", " : "), sort_keys=True)
        f.write("\n")


def main(args: list[str]) -> int:
    if args and args[0] == "--manage":
        manage(args[2], used_keys(args[1]))
        return 0
    used = None
    if args and args[0] == "--used":
        used, args = used_keys(args[1]), args[2:]
    paths = args
    problems = [p for path in paths for p in check(path)]
    if used is not None:
        problems += [p for path in paths for p in unused(path, used)]
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} text(s) need attention.")
        return 1
    print("All texts have a German translation.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

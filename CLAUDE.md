# AlibiMe

## German translation is kept up to date with every change

The app ships in English and German. Every text a user can see needs both,
in the same change:

- **App texts** live in `frontend/App/BelievableCall/Localizable.xcstrings`
  (Siri phrases in `AppShortcuts.xcstrings`, permission texts in
  `InfoPlist.xcstrings`). After adding or changing a text, run
  `frontend/scripts/strings.sh`, then fill in the German for every new key.
  `frontend/scripts/strings.sh --check` must pass before a commit, and
  `swift test` fails while a German translation is missing.
- In code, write texts so the compiler can find them: `Text("...")`,
  `String(localized: "...")`, or the components' literal titles. Build whole
  sentences per case (call / text) instead of gluing words together; German
  word order differs.
- **Backend labels** (profile answers, editor options, personas, reasons,
  call wording) have a `"de"` table next to `"en"`; `tests/unit/test_german_labels.py`
  fails when a code has no German label.
- German uses "du", "SMS" for a text message, "Credits", "Alibi".

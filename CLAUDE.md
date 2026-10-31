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
- Texts in `Localizable.xcstrings` are "manually managed" on purpose. The
  texts live in the Swift package, which a build in Xcode doesn't look at, so
  Xcode would otherwise mark them all stale. `strings.sh` adds new texts as
  manual and deletes the ones the code no longer uses. If Xcode ever rewrites
  the catalogs anyway, run `strings.sh` before committing.
- In code, write texts so the compiler can find them: `Text("...")`,
  `String(localized: "...")`, or the components' literal titles. Build whole
  sentences per case (call / text) instead of gluing words together; German
  word order differs. Never show a server code or an ID as it is (a profile
  module, a badge, a time zone): map it to a translated text.
- **Public pages** (`backend/app/pages`): privacy policy and support exist as
  `name.md` and `name.de.md`; a change to one goes into the other. A test
  checks that both have the same sections.
- **Backend labels** (profile answers, editor options, personas, reasons,
  call wording) have a `"de"` table next to `"en"`; `tests/unit/test_german_labels.py`
  fails when a code has no German label.
- German uses "du", "SMS" for a text message, "Credits", "Alibi".

## Nothing a user types reaches the model

No free text ever goes into a call prompt, a call variable or anything else the
model sees, since it would open the door to prompt injection. Everything comes
from fixed lists: alibi options from the catalogs, Profile answers from codes,
the first name from `backend/app/domain/users/first_names.txt` (the server
refuses anything else and checks it again before each call). A new input that
should reach a call is a pick from a list, never a text field.

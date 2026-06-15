# Template Model — How Templates Work & How to Extend Them

A design-oriented guide to AlibiMe's template system: the data model, how a
template flows from definition → selection → dispatch, and a concrete checklist
for adding new things to templates without breaking the existing architecture.

> Code references are `path:line` and point at a symbol's definition. Line
> numbers drift — if one is off, search for the named symbol.

---

## 1. The mental model

A **template** is *one believable scenario* (e.g. "Boss — urgent travel
assignment"). It is split into two layers:

- **Shared core** — the *meaning* of the scenario, shared across channels:
  category, persona, reason, display name, ownership. → `Template`
- **Channel config** — *how that meaning is executed* per channel and locale:
  the call prompt/opening line/voice/duration, and the SMS body/style. →
  `TemplateVersion` (one row per `(template, locale, version)`).

A template can support **call**, **sms**, or **both** (flags on the version).
The user picks one template, then a channel; the backend resolves the matching
channel config and dispatches via Vapi (call) or Twilio (sms).

Four ideas hold the system together:

1. **One logical template, channel-specific behavior.** No separate SMS/call
   template systems.
2. **No free-form runtime text.** Content comes from versioned templates with a
   fixed variable allow-list (`rendering.ALLOWED_VARIABLES`). Custom templates
   are *composed* from approved skeletons, never typed by the user.
3. **Versioned + locale-aware.** Content lives in `TemplateVersion` keyed by
   `(locale, version)`; resolution falls back to `en`.
4. **Immutable history via snapshot.** At dispatch the resolved, rendered
   content is frozen onto the request, so history reproduces what actually
   happened even if the template later changes.

---

## 2. Data model

### `Template` — shared core
`backend/app/db/models/template.py`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `code` | str, unique | stable identifier; system codes are human-readable, custom ones are `custom_<hex>` |
| `category` | str | `work / family / social / logistics / safety` |
| `caller_persona` | str | e.g. `boss`, `best_friend` — keys a label in `rendering.PERSONA_LABELS` |
| `reason_code` | str | e.g. `urgent_work_issue` — keys `rendering.REASON_LABELS` |
| `display_name` | str | user-facing label (not injected into provider content) |
| `description` | str? | user-facing blurb |
| `owner_user_id` | UUID? FK→users | **NULL = built-in/system**, set = a user's custom template |
| `sender_persona_key` | str | sender identity is keyed by persona so templates from the same persona share a sender |
| `sender_display_name` | str | |
| `supports_contact_save` | bool | gates the Save-Contact UI |
| `active` | bool | inactive templates are hidden from the catalog |
| `created_at` | datetime | |
| `versions` | relationship | → `TemplateVersion[]`, cascade delete |

### `TemplateVersion` — per-locale, per-channel config
`backend/app/db/models/template.py`

Unique constraint: `(template_id, locale, version)`.

| Field | Type | Notes |
|---|---|---|
| `id` / `template_id` | UUID | |
| `version` | int | bump for content revisions |
| `locale` | str | `en`, `de`, … |
| `supports_call` / `supports_sms` | bool | **the channel-support flags** |
| `call_system_prompt_template` | str? | bounded Vapi system prompt (placeholders) |
| `call_opening_line_template` | str? | first spoken line |
| `call_followup_facts_json` | JSON? | list of plain facts the caller may mention (stored raw, **not** rendered) |
| `call_voice_profile_code` | str? | e.g. `neutral_en` |
| `call_max_duration_seconds` | int? | |
| `call_supports_interruptions` | bool | |
| `sms_body_template` | str? | |
| `sms_followup_body_template` | str? | |
| `sms_sender_style` | str? | e.g. `professional` / `casual` |
| `active` | bool | |

### Supporting building blocks

- **Label catalogs + variable allow-list** — `backend/app/domain/templates/rendering.py`
  - `ALLOWED_VARIABLES` = `{first_name, caller_persona_label, reason_label, urgency_label, locale}`.
  - `PERSONA_LABELS`, `REASON_LABELS` (per-locale) map codes → human phrases.
  - `build_context(...)` builds the substitution dict; `render(text, ctx)` does
    bounded `{var}` substitution (unknown vars are left literal — never improvised).
- **Custom-template composer** — `backend/app/domain/templates/compose.py`
  - The "approved phrase library": `PERSONAS`, `REASONS`, `CATEGORIES`,
    `URGENCIES`, `VOICE_STYLES`, call-length bounds, per-user limit.
  - Generic call/SMS skeletons keyed by locale + urgency.
  - `compose_version_content(...)` returns the `TemplateVersion` content fields;
    `options(locale)` is the editor's dropdown catalog.

### Where a request stores its template choice
`backend/app/db/models/request.py`

- `template_id`, `template_version_id` — the references used.
- `request_plan_snapshot_json` — the **frozen, rendered** plan (written at
  dispatch, see §3.5). This is the immutable record for history.
- `sender_display_name_snapshot`, `sender_phone_e164_snapshot` — sender freeze.

---

## 3. Lifecycle: how a template is used end-to-end

### 3.1 Seeding (system templates)
`backend/app/seeds/seed.py` + `backend/app/seeds/templates/*.<locale>.yaml`

Each YAML is one `(template, locale)`: the shared-core fields plus all
`call_*` / `sms_*` content and `supports_call` / `supports_sms`. The seeder
upserts a `Template` and a `TemplateVersion` per file. Idempotent.

### 3.2 Listing the catalog
`backend/app/domain/templates/service.py` → `list_catalog(db, locale, user_id)`

- Returns **system templates + the requesting user's own customs**
  (`owner_user_id IS NULL OR == user_id`).
- For each, `_catalog_item(...)` resolves the version (`resolve_version`, with
  `en` fallback), computes `supported_channels(version)`, and renders the
  previews (`preview_opening_line`, `preview_sms_body`) via `rendering.render`.
- Shape → `app/schemas/templates.py::TemplateOut` (includes `is_custom`).

### 3.3 Creating a custom template
`service.py::create_custom_template(...)` ← `POST /v1/templates`

Validates the structured choices against `compose` allow-lists, then composes a
user-owned `Template` + one `TemplateVersion` per locale via
`compose.compose_version_content(...)`. The composed skeletons keep their
`{...}` placeholders; the same render pipeline fills them later. No user text
enters content. Delete via `delete_custom_template` (owner-only).

### 3.4 Selection (frontend)
`frontend/.../Features/Home/HomeViewModel.swift`

- `templates` loaded from `GET /v1/templates`; `selectedTemplate` chosen in the
  picker (`Features/Templates/TemplatePickerView.swift`).
- `availableChannels` is derived from `selectedTemplate.supportedChannels`;
  `reconcileChannel()` keeps the chosen channel valid.
- A request is created with `template_id` + `channel` + timing.

### 3.5 Request creation → dispatch → render
- `backend/app/domain/requests/service.py::create_request` resolves the version
  (`resolve_version`) and **validates the channel** (`assert_channel_supported`),
  then stores `template_version_id` on the `Request`.
- At dispatch, `backend/app/workers/dispatch.py::_build_plan` calls
  `build_request_plan_snapshot(...)` (`service.py`) to render the channel's
  content, **saves it to `request.request_plan_snapshot_json`**, and builds a
  `RequestPlan` (`app/providers/types.py`).
- `dispatch_one` routes by channel: `call` → voice provider (Vapi) using
  `call_system_prompt` / `rendered_opening_line`; `sms` → message provider
  (Twilio) using `rendered_sms_body`.

So: **`Template`/`TemplateVersion` define content; `RequestPlan` is the rendered,
per-request runtime object; the snapshot JSON is the immutable history record.**

---

## 4. API surface
`backend/app/api/routes/templates.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/templates` | catalog (system + user customs), with `supported_channels` + previews + `is_custom` |
| GET | `/v1/templates/options` | dropdown catalog for the custom editor |
| POST | `/v1/templates` | create a custom template from structured choices |
| DELETE | `/v1/templates/{id}` | delete the user's own custom template |

Channel selection is validated when a **request** is created (`POST /v1/requests`),
not on the template endpoints.

---

## 5. Frontend mirror
`frontend/Sources/BelievableCall/`

- `Models/AppModels.swift` — `TemplateSummary` (incl. `isCustom`,
  `supportedChannels`, `previewOpeningLine`/`previewSMSBody`), `TemplateOptions`,
  `CustomTemplateDraft`.
- `Networking/DTOs.swift` + `Models/Mapping.swift` — wire shapes ↔ models.
- `Services/Services.swift::TemplateServicing` — `list / options / createCustom /
  delete` (Live + `MockServices.swift`).
- Views: `Features/Templates/TemplatePickerView.swift` (in-flow selection),
  `TemplatesView.swift` (library tab), `CustomTemplateEditorView.swift`
  (structured editor), `TemplateManagementViewModels.swift`.

---

## 6. Invariants to preserve when extending

1. **No free-form text into provider content.** Anything that becomes a call
   prompt / opening line / SMS body must be a versioned template string or a
   composed skeleton, using only `ALLOWED_VARIABLES`. User-typed values are okay
   only for *labels* never sent to a provider (`display_name`, `description`).
2. **`supported_channels` is derived from version flags** — keep that the single
   source of truth for "what channels work."
3. **Resolution falls back to `en`** (`resolve_version`). New locales are
   additive.
4. **History is immutable** via `request_plan_snapshot_json`. Don't change how a
   *past* request renders; only future dispatches pick up template edits.
5. **Custom templates reuse everything.** Don't fork a parallel system; set
   `owner_user_id` and go through the same dispatch/validation path.

---

## 7. Extension guide — "I want to add X"

The template data crosses several layers. Use this as a checklist.

### A. Add a new **shared-core** field (e.g. `urgency_level`, `tone`)
Belongs on `Template` (applies to all channels/locales).
1. `db/models/template.py` — add the column.
2. New Alembic migration (additive, dialect-aware — see §8). Follow
   `alembic/versions/0004_custom_templates.py` as the template.
3. `seeds/seed.py` (+ YAML) — set it for system templates.
4. `compose.py` / `create_custom_template` — accept + validate it for customs.
5. `service.py::_catalog_item` + `schemas/templates.py::TemplateOut` — expose it.
6. Frontend: `TemplateSummary` (+ init, all construction sites), `DTOs`,
   `Mapping`, and any UI that should show it.
7. If it should affect wording, thread it into `build_context` /
   `ALLOWED_VARIABLES` and the skeletons — **not** as free text.

### B. Add a new **per-channel config** field (e.g. `call_background_sound`)
Belongs on `TemplateVersion`.
1. `db/models/template.py` (TemplateVersion) + migration + seed YAML keys.
2. `compose.compose_version_content` — produce it for customs.
3. If it must reach the provider: add it to `build_request_plan_snapshot`, the
   `RequestPlan` dataclass (`providers/types.py`), `_build_plan`, and the
   provider adapter (`providers/voice/vapi.py` or `providers/messaging/...`).
4. Expose in the catalog/DTO/frontend only if the UI needs it.

### C. Add a new **channel** (e.g. `whatsapp`)
1. `db/models/enums.py::Channel` + a `supports_<channel>` flag (or generalize —
   see the note below) and `<channel>_*` content fields on `TemplateVersion`.
2. `service.supported_channels` / `assert_channel_supported`.
3. `build_request_plan_snapshot` branch + `RequestPlan` fields + a new provider
   + `dispatch_one` routing.
4. Frontend `Channel` enum, mapping, segmented selector picks it up automatically.

### D. Add a new **structured option** for the custom builder (persona/reason/urgency/voice)
Mostly `compose.py`: extend the relevant list + label catalog
(`rendering.PERSONA_LABELS` / `REASON_LABELS`) and, if needed, skeleton variants.
`GET /v1/templates/options` and the editor dropdowns update automatically.

### Design note: channel configs as a child table
Today, channel config lives as `call_*` / `sms_*` columns on one
`TemplateVersion` row. If you expect **many** channels or per-channel
versioning, the cleaner long-term shape is a generic child table
`template_channel_configs(template_version_id, channel, config_json)` — one row
per channel. The spec explicitly prefers that generic shape over per-channel
tables (`sms_templates`, `vapi_templates`). For 2–3 channels the current
columns are fine; switch to the child table when the column list gets unwieldy.

---

## 8. Gotchas

- **SQLite can't `ALTER TABLE ADD COLUMN` with an inline FK.** Migrations branch
  on dialect: plain column on SQLite (the `0001` baseline's `create_all` gives a
  fresh SQLite DB the FK anyway), real FK on Postgres. See
  `0002_sender_identity.py` / `0004_custom_templates.py`.
- **Migrations are idempotent** (`_add_column_if_missing`, `if table not in ...`)
  so they're safe on fresh and already-deployed DBs.
- **The variable allow-list is enforced** — adding a `{new_var}` to a skeleton
  does nothing unless it's in `ALLOWED_VARIABLES` *and* set in `build_context`.
- **`call_followup_facts_json` is stored raw, not rendered** — keep it
  placeholder-free (or render before storing).
- **Adding a field to `TemplateSummary`'s init** breaks every construction site
  (fixtures, tests, previews). Give new params a default to limit churn.

---

## 9. TL;DR for your next change

- Scenario *meaning* → `Template`. Channel *behavior* → `TemplateVersion`.
- Wording is always composed/versioned, never free-typed.
- A field only needs to travel as far as it's used: DB → (compose/seed) →
  service/DTO → frontend → (snapshot/plan/provider) only if it must reach a call/text.
- Custom templates are just `owner_user_id`-stamped templates through the same path.

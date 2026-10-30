# BelievableCall — Project Documentation

A developer's guide to the whole system: what it does, how the backend and iOS
app are structured, how the pieces connect, and where to find each thing in the
code. Read this top to bottom once; afterwards use it as a map.

> Code references are written as `path:line`. They point at a symbol's
> definition; line numbers drift as code changes, so if one is slightly off,
> search for the named symbol in that file.

---

## 1. What the product is

BelievableCall lets a user receive a **believable call or text on their own
verified phone number**, so they can gracefully step away from a situation. The
user taps once, picks a prebuilt template (e.g. *Boss — urgent travel
assignment*), a channel (call/text), and timing (now / +30s / +5m / scheduled).
The backend dispatches the call/SMS through a provider (Twilio / Vapi, or mocks)
to **the user's own number only** — there is never a third-party destination.

A recent feature adds **stable sender identity** for SMS: a text from a persona
such as *Boss* keeps coming from the same number over time, and the iOS app can
optionally save that sender as a contact. See §6 and §11.

Two halves:

- **`backend/`** — Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic. SQLite by
  default (zero external services), Postgres in production.
- **`frontend/`** — Swift / SwiftUI iOS app built as a SwiftPM library plus a
  thin app target. Compiles for iOS (ship) and macOS (so logic/tests run on the
  host).

The authoritative behaviour specs are `backend/BACKEND_SPEC.md`,
`docs/specs/FRONTEND_SPEC.md`, and `docs/specs/SENDER_CONTACT_FEATURE_SPEC.md`; the two
`README.md` files describe the current design.

---

## 2. Repository layout

```
AlibiPhoneApp/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes + request dependencies
│   │   ├── core/         # config, security, errors, rate limit, clock, logging
│   │   ├── db/           # SQLAlchemy base, session, ORM models
│   │   ├── domain/       # business rules (auth, users, templates, requests, billing, sender_identity)
│   │   ├── providers/    # otp/voice/messaging adapters: base + mock + real (Twilio/Vapi)
│   │   ├── workers/      # scheduler, dispatch, reconciliation, cleanup
│   │   ├── schemas/      # Pydantic request/response models (the wire contract)
│   │   ├── seeds/        # template YAMLs + idempotent seeding
│   │   └── main.py       # FastAPI app: middleware, error handlers, router wiring
│   ├── alembic/          # migrations (0001 baseline, 0002 sender identity)
│   └── tests/            # unit / integration / contract
└── frontend/
    ├── Sources/BelievableCall/
    │   ├── App/          # AppModel state machine, AppEnvironment DI, RootView
    │   ├── Networking/   # APIClient (sole URLSession owner), DTOs, errors, coding
    │   ├── Models/       # product-language models + DTO→model mapping
    │   ├── Services/     # service protocols + Live* + Mock* implementations
    │   ├── Storage/      # session (Keychain), preferences, contact-link state
    │   ├── DesignSystem/ # theme tokens, reusable components, platform shims
    │   └── Features/     # Auth, Home, Templates, Requests, History, Settings
    ├── App/              # thin iOS app target (xcodeproj, Info.plist)
    └── Tests/            # unit tests (host) + integration tests (gated by BC_BACKEND_URL)
```

---

## 3. The big picture: a request's life

```
iOS app                      Backend API                 Worker loop                Provider
───────                      ───────────                 ───────────                ────────
pick template/channel/time
        │  POST /v1/requests
        ├───────────────────────►  create_request()
        │                          • idempotency check
        │                          • resolve own verified number
        │                          • one-active-request guard
        │                          • (SMS) allocate sender binding
        │                          • credit pre-check
        │                          • persist status=scheduled
        │  ◄─── 201 {request_id, sender_identity}
        │
        │                                              tick() every 2s
        │                                              claim_due_requests()  status→dispatching
        │                                              dispatch_one()
        │                                              • reserve credit
        │                                              • build RequestPlan
        │                                              • send ──────────────────────►  call/SMS placed
        │                                              • capture credit
        │                                              status→provider_accepted
        │  GET /v1/requests/{id} (poll)
        │
        │                          POST /v1/webhooks/{voice,sms}  ◄── lifecycle events ──┘
        │                          ingest → lifecycle.apply_* → status→active/completed/failed
        │  GET /v1/history
```

Two state authorities, kept separate everywhere:

- **Backend DB** owns durable business state (requests, credits, bindings).
- **Provider** owns the live call/SMS; its events flow back via webhooks.

---

## 4. Backend

### 4.1 Entrypoint, middleware, error handling

`backend/app/main.py` builds the FastAPI app (`app` at `main.py:29`):

- **Request id middleware** (`main.py:32`) stamps every request/response with
  `x-request-id` for correlation.
- **Error handlers** translate exceptions into a single JSON envelope:
  - `AppError` → its `http_status` + envelope (`main.py:41`).
  - `RequestValidationError` → `422 validation_failed` (`main.py:50`). This is
    where a **smuggled destination number** lands, because request schemas use
    `extra="forbid"`.
  - Any other `Exception` → `500 internal_error` (`main.py:67`).
- **Router wiring** (`main.py:77`) includes health, auth, me, devices, templates,
  requests, history, entitlements, and the three webhook routers.

The error envelope shape and the catalogue of domain errors live in
`backend/app/core/errors.py`: base `AppError` (`errors.py:16`), one subclass per
failure mode (`Unauthorized`, `InsufficientCredits`, `ActiveRequestExists`,
`InvalidScheduleWindow`, …, `errors.py:32`–`115`), and `error_envelope()`
(`errors.py:118`). Each subclass carries a stable `code`, `http_status`, and
`retryable` flag — the contract the iOS app maps against (see §5.4).

### 4.2 Configuration & secrets

`backend/app/core/config.py` — a Pydantic-settings `Settings` class
(`config.py:18`) loaded from env / `.env`. Notables:

- Provider switches: `otp_provider` / `voice_provider` / `message_provider`
  (default `mock`).
- `fernet_key` (`config.py:76`) derives a phone-encryption key from
  `app_secret_key` when `phone_encryption_key` is blank (dev convenience).
- Twilio/Vapi/RevenueCat credentials are all optional and only read by the real
  providers.
- `settings` is a cached singleton (`config.py:88`).

### 4.3 Database layer

- `backend/app/db/base.py` — declarative `Base` (`base.py:44`), portable column
  helpers `uuid_pk()` / `uuid_fk()` (`base.py:48`), `TimestampMixin`
  (`base.py:56`), and `UTCDateTime` (`base.py:23`) which keeps every datetime
  timezone-aware UTC on both SQLite and Postgres.
- `backend/app/db/session.py` — engine + `SessionLocal` (`session.py:37`) and the
  FastAPI `get_db()` dependency (`session.py:40`). SQLite gets
  `PRAGMA foreign_keys=ON`.
- `backend/app/db/models/__init__.py` imports every model so
  `Base.metadata` is complete (used by the test harness and the baseline
  migration).

Key models (one file each under `db/models/`):

| Model | File | Purpose |
|---|---|---|
| `User` | `user.py` | account; locale/timezone/display name |
| `PhoneNumber` | `phone.py` | encrypted E.164 + hash; one verified primary per user |
| `OtpVerification` | `otp_verification.py` | in-flight OTP attempt |
| `UserSession` | `user_session.py` | opaque session token (stored hashed) |
| `Device` | `device.py` | push registration |
| `Template` / `TemplateVersion` | `template.py` | versioned, localized content + **sender persona fields** |
| `Request` | `request.py` | the user's intent + status + **sender snapshot** |
| `CallAttempt` / `MessageAttempt` | `attempts.py` | per-dispatch provider attempt |
| `RequestArtifact` | `artifact.py` | completed summary / delivered preview |
| `ServiceIdentity` | `service_identity.py` | **sender-line pool** (a number we own and can send from) |
| `UserSenderBinding` | `user_sender_binding.py` | **stable (user, persona, channel) → sender line** |
| `CreditLedger` | `credit_ledger.py` | append-only credit accounting |
| `Plan` / `Entitlement` | `plan.py` / `entitlement.py` | monetization |
| `RateLimitCounter` | `rate_limit.py` | fixed-window counters |
| `WebhookEvent` | `webhook_event.py` | raw provider events, deduped |

All string enums live in `backend/app/db/models/enums.py` (`Channel`,
`RequestStatus`, `CallAttemptStatus`, `MessageAttemptStatus`,
`ServiceIdentityStatus`, `SenderBindingStatus`, …).

### 4.4 Core utilities

- **Security** `backend/app/core/security.py`: `encrypt_phone`/`decrypt_phone`
  (Fernet, `security.py:25`/`29`), `hash_phone` (keyed HMAC for lookup without
  decryption, `security.py:36`), `mask_phone` (`security.py:43`),
  `generate_session_token`/`hash_session_token` (`security.py:56`/`60`). Raw
  numbers are never logged.
- **Rate limiting** `backend/app/core/rate_limit.py`: fixed-window counters via a
  DB row with `SELECT ... FOR UPDATE` (`check_and_increment`, `rate_limit.py:43`).
  Limits defined at `rate_limit.py:29` (OTP start/confirm, request create,
  session create).
- **Clock** `backend/app/core/clock.py`: `utcnow()` — the single time source, so
  tests can drive time.
- **Logging** `backend/app/core/logging.py`: structured JSON logging.

### 4.5 Auth & sessions

`backend/app/domain/auth/service.py` implements passwordless OTP:

- `start_phone_verification()` (`auth/service.py:41`): normalize the number
  (§4.6), rate-limit by phone hash, call the OTP provider, persist an
  `OtpVerification`. Returns `{verification_id, channel, expires_in_seconds}`.
- `confirm_phone_verification()` (`auth/service.py:155`): validate the code via
  the provider, find-or-create the `User`, set the verified primary phone
  (`_set_primary_phone`, `auth/service.py:111`), grant the free onboarding
  allowance for new users (§4.9), then issue a session (`_issue_session`,
  `auth/service.py:85`, which rotates older sessions for the same device).
- `resolve_session()` (`auth/service.py:236`): look up by token hash, enforce
  not-revoked / not-expired / active user. Raises `Unauthorized` or
  `SessionExpired`.

Routes: `backend/app/api/routes/auth.py` — `POST /v1/auth/phone/start`
(`auth.py:20`), `/confirm` (`auth.py:32`), `/logout` (`auth.py:44`).

The auth dependency that every protected route uses is in
`backend/app/api/deps.py`: `get_current_context()` (`deps.py:35`) extracts the
bearer token and returns a `CurrentContext(user, session)` (`deps.py:29`).

### 4.6 Users & phone normalization

- `backend/app/domain/users/service.py`: `get_primary_phone` /
  `require_primary_phone` (`users/service.py:23`/`33`) — the **own-number rule**
  source: dispatch destination always comes from here, never from the client.
  `masked_primary_number` (`users/service.py:40`) for display.
- `backend/app/domain/phone.py`: `normalize_phone()` (`phone.py:35`) → E.164 via
  `phonenumbers`, validates supported countries, maps line type;
  `assert_supported_line_type()` (`phone.py:65`) blocks landlines.

### 4.7 Templates

`backend/app/domain/templates/service.py`:

- `resolve_version()` (`templates/service.py:17`): active version for
  (template, locale) with `en` fallback.
- `supported_channels()` / `assert_channel_supported()`
  (`templates/service.py:34`/`43`).
- `list_catalog()` (`templates/service.py:50`): builds the `/v1/templates`
  payload, including the new `sender_persona_key` / `sender_display_name` /
  `supports_contact_save` fields and rendered previews.
- `build_request_plan_snapshot()` (`templates/service.py:87`): the resolved,
  rendered content snapshot handed to providers at dispatch (makes history
  reproducible).

Content is rendered by `backend/app/domain/templates/rendering.py`. The catalog
itself is seeded from `backend/app/seeds/templates/*.yaml` via
`backend/app/seeds/seed.py` (`_upsert_template`/`_upsert_version`); sender
persona fields default from `caller_persona`/`display_name` there.

Route: `backend/app/api/routes/templates.py` → `GET /v1/templates`. Schema:
`backend/app/schemas/templates.py` (`TemplateOut`).

### 4.8 Requests — creation, state machine, lifecycle

This is the heart of the system. `backend/app/domain/requests/service.py`:

- `create_request()` (`requests/service.py:86`) enforces, in order:
  1. channel validity and exactly-one-of `delay_seconds` / `scheduled_at`;
  2. **idempotency** per `(user, client_request_id)` — returns the existing
     request if present;
  3. rate limit;
  4. resolve the **own verified primary phone**;
  5. **one active live request** guard (`get_active_request`,
     `requests/service.py:50`);
  6. resolve template + version + channel support;
  7. compute `execute_at` from timing (`_resolve_execute_at`,
     `requests/service.py:65`; allowed delays `{0,30,300}`, schedule horizon
     24h);
  8. **credit pre-check**;
  9. for SMS, **resolve/allocate a sender binding** and snapshot it (§6);
  10. persist `status=scheduled`. Concurrent duplicates collapse on the
      `uq_user_client_request` constraint.
- `get_request` / `cancel_request` (cancel only allowed while `scheduled`,
  releasing any reserved credit).
- `sender_identity_payload()` builds the `sender_identity` object for API
  responses (returns `None` for calls / empty pool).
- `latest_attempt_summary()` flattens the most recent attempt for the detail
  endpoint.

**State machine** `backend/app/domain/requests/state.py`: allowed transitions
table (`state.py:8`), `can_transition`/`assert_transition` (`state.py:49`/`53`),
and `is_cancelable` (`state.py:60`). Statuses:
`scheduled → dispatching → provider_accepted → active → completed`, with
`failed` / `canceled` / `expired` terminals.

**Applying provider outcomes** `backend/app/domain/requests/lifecycle.py` is the
*single* place attempt + request status are advanced — shared by the dispatcher
and the webhook path. `apply_call_event()` (`lifecycle.py:52`) and
`apply_message_event()` (`lifecycle.py:80`) map a neutral attempt status to a
request status (`_CALL_TO_REQUEST` / `_MESSAGE_TO_REQUEST`, `lifecycle.py:22`/
`32`), stamp timestamps, ignore out-of-order events, and create a
`RequestArtifact` on completion (`_ensure_artifact`, `lifecycle.py:119`).

Routes: `backend/app/api/routes/requests.py` — `POST /v1/requests`
(`requests.py:31`), `GET /v1/requests/{id}` (`requests.py:58`),
`POST /v1/requests/{id}/cancel` (`requests.py:80`). Schemas in
`backend/app/schemas/requests.py` (`CreateRequestBody` uses `extra="forbid"`;
`CreateRequestResponse` / `RequestDetail` carry the optional
`SenderIdentityOut`). History: `backend/app/api/routes/history.py` →
`GET /v1/history` (paginated, with sender snapshot fields).

### 4.9 Billing: credits & entitlements

Credits are an **append-only ledger**, never a mutable balance —
`backend/app/domain/billing/credits.py`:

- `current_balance()` (`credits.py:25`) = sum of signed `amount_units`.
- `grant` / `reserve` / `capture` / `release` (`credits.py:59`/`76`/`88`/`96`).
  The dispatch policy is **reserve at dispatch, capture on provider acceptance,
  release on pre-dispatch failure** (so internal failures don't burn credits).

`backend/app/domain/billing/entitlements.py`: `entitlement_summary()`
(`entitlements.py:21`) feeds `/v1/me`, and `grant_free_test_allowance()`
(`entitlements.py:40`) gives new users the configured free credits once. Plans &
entitlement status come from RevenueCat in production
(`api/routes/webhooks_revenuecat.py`, `providers/revenuecat.py`).

### 4.10 Providers (the adapter layer)

Everything provider-specific hides behind neutral types so the domain never sees
a vendor. `backend/app/providers/types.py`:

- Neutral exceptions: `ProviderError`, `TransientProviderError` (retryable),
  `ProviderRejected` (hard) (`types.py:14`–`41`).
- `RequestPlan` (`types.py:45`) — the resolved snapshot handed to a provider
  (rendered content, sender identity value, decrypted destination, caps).
- Result/parse DTOs: `ProviderCallResult`, `ProviderMessageResult`,
  `WebhookParseResult`, `OtpStartResult`, …

Selection by config: `backend/app/providers/factory.py` —
`get_otp_provider` / `get_voice_provider` / `get_message_provider`
(`factory.py:13`/`23`/`33`).

Each channel has a `base.py` interface, a `mock.py`, and a real adapter:

- OTP: `otp/mock.py` (code is always `123456`), `otp/twilio_verify.py`.
- Voice: `voice/mock.py` (`MockVoiceCallProvider`, `voice/mock.py:26`, with a
  `simulate_lifecycle()` helper at `voice/mock.py:77`), `voice/vapi.py`.
- Messaging: `messaging/mock.py`, `messaging/twilio_sms.py`
  (`TwilioMessagingProvider`, sends one-way SMS, maps Twilio status →
  `MessageAttemptStatus`).

The mocks fully simulate provider lifecycles, which is what lets the entire app
run and be tested with **zero external accounts**.

### 4.11 Workers (the durable scheduler)

`python -m app.workers.run` (`backend/app/workers/run.py`) starts
`scheduler.run_forever()` (`backend/app/workers/scheduler.py:31`). Each `tick()`
(`scheduler.py:17`, every ~2s):

1. **Dispatch** `backend/app/workers/dispatch.py`:
   - `claim_due_requests()` (`dispatch.py:62`): atomically flips due
     `scheduled` rows to `dispatching` using `FOR UPDATE SKIP LOCKED` on
     Postgres (so multiple workers don't double-dispatch).
   - `dispatch_one()` (`dispatch.py:148`): reserve credit → pick the sender line
     (`_resolve_dispatch_identity`, prefers the request's bound line, else
     `_select_service_identity`, `dispatch.py:85`) → build the `RequestPlan`
     (`_build_plan`, decrypts the destination here only) → call the provider via
     `_dispatch_call` / `_dispatch_sms` (one pre-dispatch retry on transient
     failure) → capture credit → `status=provider_accepted`.
2. **Reconciliation** (~every minute) `backend/app/workers/reconciliation.py`:
   `reconcile()` (`reconciliation.py:23`) fails requests stuck in `dispatching`
   (worker died → release credit) or `provider_accepted/active` past the
   inflight timeout (credit already captured).
3. **Cleanup** (~hourly) `backend/app/workers/cleanup.py`: prunes expired
   verifications / old data.

### 4.12 Webhooks (provider → us)

`backend/app/domain/requests/webhook_ingest.py`: `ingest_voice_webhook`
(`webhook_ingest.py:35`) and `ingest_sms_webhook` (`webhook_ingest.py:57`)
persist the raw event, **dedupe** on `(provider, external_event_id)`, find the
matching attempt by provider ref id, then delegate to `lifecycle.apply_*`.

Routes:

- `POST /v1/webhooks/voice` (`api/routes/webhooks_voice.py:24`) — verifies the
  Vapi shared secret (`X-Vapi-Secret`) only when running on Vapi
  (`_should_verify_secret`), so mock/local flows keep working.
- `POST /v1/webhooks/sms` (`api/routes/webhooks_sms.py`) — verifies the Twilio
  signature; accepts form-encoded (Twilio) or JSON (mock). Signature helper:
  `backend/app/core/twilio_webhook.py`.
- `POST /v1/webhooks/revenuecat` — purchase / entitlement updates.

### 4.13 API surface (quick reference)

| Method & path | Route file | Auth | Purpose |
|---|---|---|---|
| `POST /v1/auth/phone/start` | `auth.py` | no | begin OTP |
| `POST /v1/auth/phone/confirm` | `auth.py` | no | verify OTP → session |
| `POST /v1/auth/logout` | `auth.py` | yes | revoke session |
| `GET/PATCH /v1/me` | `me.py` | yes | profile + credits + active request |
| `PUT /v1/devices/current` | `devices.py` | yes | register device/push |
| `GET /v1/templates` | `templates.py` | yes | template catalog |
| `POST /v1/requests` | `requests.py` | yes | create call/text |
| `GET /v1/requests/{id}` | `requests.py` | yes | poll status (+ sender identity) |
| `POST /v1/requests/{id}/cancel` | `requests.py` | yes | cancel while scheduled |
| `GET /v1/history` | `history.py` | yes | past requests (+ sender snapshot) |
| `GET /v1/entitlements` | `entitlements.py` | yes | credits/plans |
| `POST /v1/webhooks/{voice,sms,revenuecat}` | `webhooks_*.py` | signed | provider callbacks |
| `GET /health/{live,ready}` | `health.py` | no | health checks |

---

## 5. Frontend (iOS)

The app is an `@Observable` + async/await SwiftUI app. The golden rule:
**screens bind to product-language models, never to wire DTOs**, and **only
`APIClient` touches the network**.

### 5.1 App state machine & DI

- `frontend/Sources/BelievableCall/App/AppModel.swift`: top-level state machine
  with `Phase { launching, unauthenticated, authenticated }` (`AppModel.swift:10`).
  `restore()` (`AppModel.swift:30`) loads a stored session on launch;
  `signIn`/`signOut`/`handleSessionExpired` move phases and manage the token. The
  **view-model factories** (`makeHomeViewModel` at `AppModel.swift:81`, etc.)
  wire dependencies + session-expiry routing in one place.
- `frontend/Sources/BelievableCall/App/RootView.swift`: switches on
  `app.phase` between `LaunchView`, the auth flow, and `MainTabView`
  (`RootView.swift:55`, the Home/History/Settings tabs).
- `frontend/Sources/BelievableCall/App/AppEnvironment.swift`: the DI container
  (`AppEnvironment.swift:6`). Owns the single `APIClient`, the `TokenHolder`,
  storage, and every `Live*` service. `AppEnvironment.live(...)` builds the
  production graph; `defaultContactsService()` returns `LiveContactsService` on
  iOS. Tests/previews construct it with mocks.

### 5.2 Networking (the only place that touches URLSession)

`frontend/Sources/BelievableCall/Networking/APIClient.swift`:

- `HTTPTransport` protocol (`APIClient.swift:5`) abstracts `URLSession` so tests
  inject canned responses; `TokenProviding` (`APIClient.swift:16`) supplies the
  bearer token.
- `Endpoint` (`APIClient.swift:20`) is a small request descriptor.
- `APIClient` (`APIClient.swift:43`): `send(_:as:)` (`APIClient.swift:62`)
  decodes JSON; `sendForData` (`APIClient.swift:79`) builds the `URLRequest`,
  adds auth, and on non-2xx calls `mapError` (`APIClient.swift:118`) to turn the
  backend envelope into a typed `APIError`.

`frontend/Sources/BelievableCall/Networking/DTOs.swift` holds the raw
`Decodable`/`Encodable` structs mirroring the backend JSON exactly (including
`sender_identity` and the template/history sender fields).
`Networking/Coding.swift` centralizes JSON date coding (`BCCoding`).

### 5.3 Models & mapping

`frontend/Sources/BelievableCall/Models/AppModels.swift` — product-language
models the UI binds to:

- `TemplateSummary` (with `senderPersonaKey`/`senderDisplayName`/
  `supportsContactSave`), `Channel` (`.call`/`.text` ↔ wire `call`/`sms`,
  `AppModels.swift:131`), `TimingOption`, `RequestStatus` (normalized lifecycle,
  `AppModels.swift:215`), `RequestSummary` (carries an optional
  `SenderIdentity`), `HistoryEntry`, `UserProfile`, `Session`.
- `SenderIdentity`, `ContactLinkStatus`, `ContactLinkState` — the sender/contact
  models (see §11).

`frontend/Sources/BelievableCall/Models/Mapping.swift` is the **only** place DTOs
become models (e.g. `RequestSummary(dto:)`, `SenderIdentity(dto:)`,
`HistoryEntry(dto:)`), plus `RequestDraft` (`Mapping.swift`, near the bottom)
which builds the request body **without any destination field** — enforced by the
unit test `testCreateRequestBodyContainsNoDestinationNumber`.

### 5.4 Services (protocols + live + mock)

`frontend/Sources/BelievableCall/Services/Services.swift` declares the protocols
the view models depend on: `AuthServicing`, `TemplateServicing`,
`RequestServicing`, `HistoryServicing`, `ProfileServicing`, `DeviceServicing`,
and `ContactsServicing` (authorization only, `Services.swift`), plus the
`Live*` implementations over `APIClient`.
`frontend/Sources/BelievableCall/Services/MockServices.swift` provides `Mock*`
versions + `Fixtures` for previews/tests.
`frontend/Sources/BelievableCall/Services/LiveContactsService.swift` is the
iOS/Contacts-framework implementation (guarded by `#if canImport(Contacts)`).

Errors: `frontend/Sources/BelievableCall/Networking/APIError.swift` defines the
typed `APIError` (`APIError.swift:5`), `requiresReauth` routing, and `ErrorCopy`
(`APIError.swift:57`) which maps backend codes to calm human copy — **raw codes
never reach the UI**.

### 5.5 Storage

- `Storage/SessionStore.swift`: `TokenHolder` (lock-protected token,
  `SessionStore.swift:6`), `SessionStoring` protocol, `KeychainSessionStore`
  (production, `SessionStore.swift:46`) and `InMemorySessionStore` (tests).
- `Storage/Preferences.swift`: `PreferencesStoring` for last channel/timing,
  selected template, and a stable `deviceID`.
- `Storage/ContactLinkStore.swift`: `ContactLinkStoring` — device-local record
  of whether a sender was saved as a contact (see §11).

### 5.6 Features

Each feature folder pairs an `@Observable` view model with SwiftUI views:

- **Auth** (`Features/Auth/`): `AuthViewModel` is a small flow machine
  `welcome → phone → otp → done` (`AuthViewModel.swift:10`); `requestCode()` /
  `confirmCode()` (`AuthViewModel.swift:71`/`90`) call `AuthServicing` and on
  success invoke `onAuthenticated` (wired to `AppModel.signIn`).
- **Home** (`Features/Home/`): `HomeViewModel` owns template/channel/timing
  selection, the create-request fast path (`send()`), the active-request state,
  and the post-success Save Contact flow (§11). `HomeView` renders the composer
  or the active-request card and attaches `.saveContactFlow(vm:)`.
- **Templates** (`Features/Templates/`): `TemplatePickerView` — grouped picker
  bound to `HomeViewModel`.
- **Requests** (`Features/Requests/`): `RequestStatusViews.swift` (active-request
  card + countdown), `ScheduleSheet.swift` (exact-time picker), and
  `ContactSaveViews.swift` (the Save Contact UI, §11).
- **History** (`Features/History/`): `HistoryViewModel` (pull-to-refresh +
  pagination, `HistoryViewModel.swift:27`) and `HistoryView`.
- **Settings** (`Features/Settings/`): profile edit, sign out, credits.

### 5.7 Design system

`DesignSystem/Theme.swift` (color/spacing tokens), `Components.swift` (buttons,
cards, pills, banners, haptics), `PlatformShims.swift` (iOS/macOS shims so the
library compiles on both).

---

## 6. Stable sender identity + Save Contact (the cross-cutting feature)

**Goal:** a text from a persona (e.g. *Boss*) keeps coming from the **same**
number over time, and the iOS app can *optionally* save that sender as a contact.
Continuity is **backend-bound** and never depends on whether a contact is saved.

### Backend
- **Sender lines** are the existing `ServiceIdentity` pool — "a
  provider-controlled outbound identity we own and can send from"
  (`db/models/service_identity.py`), extended with Twilio/Vapi handles and a
  label.
- **Sender bindings** `db/models/user_sender_binding.py`: unique on
  `(user_id, sender_persona_key, channel)`. With a single Twilio number, several
  personas legitimately bind to the same line (the constraint is on the persona,
  not the line).
- **Allocation** `backend/app/domain/sender_identity/service.py`:
  `resolve_or_allocate_binding()` reuses an active binding, else picks an active
  capable line (`select_sender_line()`); if the bound line was disabled it
  re-points the binding to a replacement (status `orphaned` → `active`) without
  mutating past history. Called from `create_request()` for SMS, which snapshots
  `sender_binding_id` + persona + display name + E.164 onto the `Request`.
- **Dispatch** uses the request's bound line (`_resolve_dispatch_identity` in
  `dispatch.py`), so the number the user saw is the number that sends.
- **API**: `POST/GET /v1/requests` return a `sender_identity` object;
  `GET /v1/history` exposes the snapshot. Calls return `null` (SMS-only this
  pass; the model is ready for Vapi voice reuse).

### Frontend
- `SenderIdentity` flows onto `RequestSummary` (and `HistoryEntry` for re-entry).
- After an accepted SMS — never before, never blocking — `HomeViewModel`'s
  `maybeOfferContactPrompt()` offers the *"Save this sender as a contact?"*
  prompt, shown **once per binding** (gated by `ContactLinkStoring`).
- `beginSaveContact()` requests Contacts access **in-context** (never at launch)
  via `ContactsServicing`, then presents a prefilled `CNContactViewController`
  (name + bound number only) wrapped as `NewContactSheet` in
  `Features/Requests/ContactSaveViews.swift`.
- Skip / dismiss / deny are all valid outcomes recorded as `ContactLinkState`
  (status `unknown`/`created`/`dismissed`/`denied`/`not_now`); iOS contact
  identifiers stay on device. `NSContactsUsageDescription` is set in
  `frontend/App/Info.plist`.

The full intent and rules are in `docs/specs/SENDER_CONTACT_FEATURE_SPEC.md`; the design
summaries are in both READMEs.

---

## 7. Load-bearing invariants (don't break these)

1. **Own-number only.** The request body never carries a destination; the
   destination is always the user's verified primary phone. Enforced by
   `extra="forbid"` schemas (backend) + the no-destination `RequestDraft`
   (frontend) + tests on both sides.
2. **One verified primary number per user** (`auth/service.py:_set_primary_phone`).
3. **At most one active live request per user** (`get_active_request`).
4. **Idempotent create** per `(user, client_request_id)`.
5. **Credits**: reserve at dispatch, capture on acceptance, release on
   pre-dispatch failure; balance is a ledger sum, never a mutable field.
6. **Provider details stay behind adapters**; the domain only sees neutral types.
7. **Status logic lives once** (`domain/requests/lifecycle.py`), shared by
   dispatch and webhooks.
8. **Sender continuity is backend-bound**, independent of contact saving.
9. **Phones encrypted at rest, masked in output, never logged.**

---

## 8. End-to-end flows

**Login:** `AuthViewModel.requestCode` → `POST /phone/start` →
`start_phone_verification` (OTP provider) → user enters code →
`AuthViewModel.confirmCode` → `POST /phone/confirm` →
`confirm_phone_verification` (find/create user, set primary phone, grant free
credits, issue session) → `AppModel.signIn` persists the session in the Keychain.

**Create a call:** `HomeViewModel.send` → `POST /v1/requests` →
`create_request` (invariants + `status=scheduled`) → worker `claim_due_requests`
→ `dispatch_one` (reserve credit, build plan, place call, capture credit,
`provider_accepted`) → provider posts events to `/v1/webhooks/voice` →
`ingest_voice_webhook` → `lifecycle.apply_call_event` advances to
`active`/`completed` → app polling `GET /v1/requests/{id}` reflects it.

**Create an SMS + save contact:** as above, but `create_request` also allocates
the sender binding and the 201 response includes `sender_identity`. On success
`HomeViewModel` offers the contact prompt; accepting presents the prefilled
contact sheet. Future SMS from the same persona reuse the same binding/number.

---

## 9. Testing

**Backend** (`backend/tests/`, pytest): runs entirely on throwaway SQLite with
mock providers — see `tests/conftest.py` (recreates + seeds the schema per test;
mock OTP is `123456`). Suites: `unit/`, `integration/` (full HTTP round-trips
incl. `test_sender_identity.py` and `test_dispatch.py`), `contract/`
(stable response shapes for the iOS client). Run: `make test` (114 tests).

**Frontend** (`frontend/Tests/`): the package compiles for macOS, so logic runs
with `swift test` on the host (Xcode toolchain needed for XCTest):

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  swift test --filter BelievableCallTests          # 77 unit tests
```

Integration tests (`BelievableCallIntegrationTests`) are gated by
`BC_BACKEND_URL` and drive the real backend. See `frontend/README.md` for the
full setup.

---

## 10. Running locally

**Backend** (`backend/`):

```bash
make bootstrap   # first time: deps + config + DB schema + seed
make start       # migrate + seed + uvicorn on :8000  (http://localhost:8000/docs)
make worker      # scheduler + dispatch + reconciliation loop
```

Mock OTP code is always `123456`; new users get 3 free credits. Switch to real
providers by setting `OTP_PROVIDER` / `VOICE_PROVIDER` / `MESSAGE_PROVIDER` and
the matching credentials (see `backend/README.md`).

**Frontend** (`frontend/`): open `App/BelievableCall.xcodeproj`, pick the
`BelievableCall` scheme + an iOS simulator, Run. The base URL defaults to
`http://127.0.0.1:8000`; override with the `BC_BACKEND_URL` env var.

---

## 11. Glossary

- **Sender line** — a number we own and can send from (`ServiceIdentity`).
- **Sender persona** — a product identity like `boss`/`roommate` that keys sender
  bindings (on the template).
- **Sender binding** — the stable `(user, persona, channel) → sender line`
  mapping (`UserSenderBinding`).
- **Sender snapshot** — the immutable sender fields copied onto a `Request` so
  history stays correct if inventory changes.
- **Contact link state** — device-local record of whether the user saved a
  sender as a contact (`ContactLinkState`).
- **RequestPlan** — the resolved, rendered snapshot handed to a provider at
  dispatch.
- **Attempt** — one provider dispatch of a request (`CallAttempt` /
  `MessageAttempt`); a request can have more than one (pre-dispatch retry).
- **Artifact** — the post-completion summary / delivered preview shown in history.
```

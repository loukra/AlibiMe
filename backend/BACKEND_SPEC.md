# BelievableCall — Backend Specification

> This is the source of truth for the MVP backend. The iOS app, backend code,
> local development setup, provider adapters, and future production hardening
> derive from this file.

---

## Soul

This product is **not** only an emergency app and **not** a prank app.

It is a general **believable interruption / alibi app**: the user taps once and
receives a believable **call** or **text message** on their **own phone number**
so they can leave a situation, change plans, or create a socially acceptable
reason to step away.

Examples in scope:
- best friend needs you outside
- roommate has an issue at home
- sibling asks for a family check-in
- coworker has an urgent client problem
- boss needs you for a work trip abroad
- safety check-in / exit support

The backend is invisible to the user, but the user feels its quality through the
outcome:
- the request is accepted immediately
- the call or message arrives at the right time
- the selected template is respected
- cancellation behaves correctly
- no duplicate dispatch happens
- no wrong number is ever contacted

**Core belief:** this product works only if the backend is simple,
predictable, abuse-resistant, and easy to reason about.

---

## The One Load-Bearing Rule

**A user may only trigger calls or text messages to their own verified primary
phone number.**

This is the product rule everything else hangs on.

- The mobile client **never sends a target phone number** when creating a
  request.
- The backend resolves the destination from the authenticated user's
  `primary_verified_phone_number`.
- The backend rejects dispatch if the user has no verified primary number.
- The backend supports **one active primary number per user** in MVP.
- Changing the primary number requires a new OTP verification.
- There is no "call a friend", "text my contact", address book import, or
  arbitrary destination input.

This rule exists for safety, abuse prevention, cost control, and app-review
risk reduction.

---

## The Other Load-Bearing Product Decision

**Templates are first-class.**

The product is not "type any lie and let the AI improvise forever".

Each template explicitly defines:
- **who is contacting the user** (`boss`, `coworker`, `best_friend`, `sibling`,
  `roommate`, etc.)
- **why they are contacting the user** (`urgent_work_issue`,
  `travel_assignment_abroad`, `family_checkin`, `need_you_outside`,
  `issue_at_home`, `safety_checkin`, etc.)
- **which channels it supports** (`call`, `sms`, or both)
- **what the opening line or message body is**
- **which follow-up facts are allowed**
- **how long the interaction may last**

Calls may use bounded AI behavior later.
SMS in MVP is **template-driven and one-way**, not a free-form AI conversation.

---

## Scope (MVP)

### In

- **Backend stack:** Python + FastAPI.
- **Client consuming this backend:** native **iOS** app in SwiftUI.
- **Authentication:** passwordless OTP using the user's phone number.
- **Phone verification:** one verified primary number per user.
- **Delivery channels:**
  - outbound **call** to the user's own verified number
  - outbound **SMS / text message** to the user's own verified number
- **Request timing modes:**
  - now
  - in 30 seconds
  - in 5 minutes
  - at an exact time within the next 24 hours
- **Template library:** fixed, versioned, localized templates with:
  - `caller_persona`
  - `reason_code`
  - `category`
  - call content configuration
  - sms content configuration
- **Persistence:** PostgreSQL.
- **Managed DB hosting may be Supabase, Neon, RDS, or similar**, but the app
  code must remain plain Postgres + FastAPI and not depend on Supabase-specific
  auth or Edge Functions.
- **Mock providers are required in the first coding pass**:
  - `MockOtpProvider`
  - `MockVoiceCallProvider`
  - `MockMessageProvider`
- **Real providers are later, manual integrations**:
  - Twilio Verify / Lookup for OTP and number validation
  - Vapi for voice calls
  - Twilio Messaging (or similar) for SMS
- **Payments / entitlements:** simple credit system, schema ready for later
  subscriptions.
- **Webhook ingestion:** supported in architecture, but real-provider webhook
  testing happens later after manual setup.
- **Observability:** structured logs, metrics, Sentry-ready error reporting.
- **Abuse controls:** OTP limits, request limits, idempotency, one active live
  request per user, own-number-only invariant.
- **Privacy controls:** minimal retention, encrypted phone numbers, no raw
  transcripts or recordings stored by default.

### Out (explicitly, for MVP)

- Android client.
- Web app.
- Arbitrary target phone numbers.
- Multi-number accounts.
- Shared / family accounts.
- Address book import.
- User-created AI personas.
- User-authored free-form prompt builder.
- Voice cloning.
- AI text-chat conversations.
- Automatic provider dashboard setup.
- Redis requirement in the first coding pass.
- Kafka / RabbitMQ / microservices.
- Emergency dispatch, authority contact flows, or claims of emergency-service
  capability.

---

## Product Boundaries

- This is a **general believable-call / believable-text app**, not an
  emergency-response system.
- Safety-related templates are allowed, but the product must never imply that it
  contacts police, medical services, or rescue authorities.
- Calls should feel realistic but remain tightly bounded.
- SMS should feel plausible but stay controlled and one-way in MVP.
- The product should not impersonate a real third party's phone number.
  Outbound identity comes from a service-controlled sender identity.
- The backend favors short, believable outcomes over open-ended improvisation.
- Unit economics matter: calls and texts both have real provider cost.

---

## Architecture

### Shape

Start with a **modular monolith** in one repository.

Use two Python entrypoints:
1. **API process** — FastAPI app
2. **Worker process** — scheduler + dispatch + cleanup jobs

For local development, the worker may run inline or as a second simple process.

One PostgreSQL database. No Redis requirement in the first coding pass.

### Tech choices

- **Python:** 3.12+
- **FastAPI** for HTTP API and webhooks
- **Pydantic v2** for typed request / response contracts
- **SQLAlchemy 2.x** ORM / Core
- **Alembic** for migrations
- **PostgreSQL** as system of record and durable scheduler
- **httpx** for provider SDK / API calls where no official SDK is required
- **uvicorn / gunicorn** for serving
- **pytest** for unit and integration tests

### Why this shape

- The system is mostly I/O-bound.
- The hard problems are state integrity, scheduling, provider orchestration,
  abuse prevention, and billing rules.
- A monolith keeps the domain model coherent.
- PostgreSQL is enough for MVP durability, scheduling, idempotency bookkeeping,
  and basic rate limiting.
- Manual provider setup exists outside the codebase, so provider behavior must
  sit behind adapters and mocks from day one.

### Durability rule

**Scheduled requests live in PostgreSQL, not only in provider dashboards and not
only in in-memory timers.**

The provider may support scheduling, but our backend remains the source of truth
for:
- cancellation
- retries
- analytics
- history
- provider portability

---

## High-Level Flow

### 1. Signup / Login / Verification

1. User enters phone number in iOS app.
2. Backend normalizes to E.164.
3. Backend starts OTP verification via the configured OTP provider.
4. User submits OTP code.
5. Backend verifies OTP.
6. Backend creates or loads `user`.
7. Backend stores verified phone number as the user's `primary` phone.
8. Backend issues an authenticated session token.

### 2. Immediate request

1. User chooses template and channel (`call` or `sms`).
2. User picks timing (`now`, `30 seconds`, `5 minutes`).
3. App sends `template_id`, `channel`, `delay_seconds`, and
   `client_request_id`.
4. Backend authenticates user.
5. Backend loads verified primary phone number.
6. Backend checks entitlement, rate limits, and active-request rules.
7. Backend persists `request` with `execute_at`.
8. Worker picks up the due request.
9. Worker resolves template version and builds a request-plan snapshot.
10. Worker invokes the channel provider adapter.
11. Provider events update status until completion.

### 3. Scheduled request

Same as above, except `execute_at` is in the future.

### 4. Cancel

The user may cancel a request until it has been accepted for dispatch by the
provider. After provider acceptance, cancellation is best-effort only.

---

## Load-Bearing Technical Invariants

1. **Client never sends destination phone number.**
2. **Backend always resolves destination from authenticated user's verified
   primary phone.**
3. **Exactly one active primary phone number per user in MVP.**
4. **At most one active live request per user at a time.**
5. **Every create-request call is idempotent per user and `client_request_id`.**
6. **Scheduled requests are persisted before any provider dispatch is attempted.**
7. **Entitlement is checked server-side before dispatch.**
8. **Template selection is versioned and server-controlled.**
9. **Call artifacts are minimized; recordings/transcripts are not stored by
   default.**
10. **SMS is one-way in MVP; inbound replies are not part of the first build.**
11. **Provider-specific details stay behind adapters.**

---

## Domain Model

### Users

Canonical account entity.

Fields:
- `id` (UUID)
- `created_at`
- `updated_at`
- `status` (`active | blocked | deleted`)
- `locale` (`en | de` for MVP, extendable)
- `timezone` (IANA string)
- `display_name` (optional)
- `last_login_at`

Notes:
- User identity is **not** the raw phone number.
- The phone number is a login handle and delivery channel, not the canonical PK.

### PhoneNumbers

Stores phone numbers owned by users.

Fields:
- `id` (UUID)
- `user_id`
- `phone_e164_encrypted`
- `phone_hash` (for uniqueness / rate limits / lookup without decryption)
- `country_code`
- `line_type` (`mobile | landline | fixed_voip | non_fixed_voip | unknown`)
- `verified_at`
- `is_primary`
- `status` (`pending | verified | replaced | revoked`)
- `created_at`

Rules:
- At most one `is_primary = true` per user.
- Only `verified` + `primary` numbers may receive requests.

### UserSessions

Represents logged-in app sessions.

Fields:
- `id` (UUID)
- `user_id`
- `token_hash`
- `device_id`
- `created_at`
- `expires_at`
- `revoked_at` (nullable)
- `last_used_at`

Rule:
- MVP uses **opaque session tokens**, not JWT.

### Devices

Push-capable device registry.

Fields:
- `id` (UUID)
- `user_id`
- `platform`
- `push_token`
- `app_version`
- `os_version`
- `last_seen_at`
- `created_at`

### ServiceIdentities

Outbound identities controlled by the service.

Fields:
- `id` (UUID)
- `provider`
- `external_identity_id`
- `identity_value` (phone number or sender id)
- `identity_type` (`phone_number | alphanumeric_sender_id`)
- `country_code`
- `capability_outbound_voice`
- `capability_outbound_sms`
- `status` (`active | warming | disabled`)
- `notes` (nullable)
- `created_at`

MVP note:
- Start with a small manually-managed pool.
- Selection can be simple round-robin or channel / country based.

### Plans

Defines monetization packages.

Fields:
- `id` (UUID)
- `code` (`free`, `credits_5`, `credits_15`, `starter_monthly`, etc.)
- `kind` (`one_time | subscription`)
- `included_credit_units`
- `store_product_ids_json`
- `active`

### Entitlements

Current access state for each user.

Fields:
- `id` (UUID)
- `user_id`
- `source` (`app_store | play_store | revenuecat | admin | promo`)
- `plan_id`
- `status` (`active | expired | canceled`)
- `starts_at`
- `ends_at`
- `external_customer_id`
- `external_entitlement_id`
- `metadata_json`

### CreditLedger

Immutable credit movements.

Fields:
- `id` (UUID)
- `user_id`
- `entry_type` (`grant | reserve | capture | release | refund | admin_adjustment`)
- `amount_units`
- `balance_after_units`
- `reference_type` (`purchase | subscription_renewal | request | attempt | manual`)
- `reference_id`
- `created_at`
- `notes`

Rule:
- Credits are ledger-based, never stored only as a mutable balance field.

### Templates

User-facing template families.

Fields:
- `id` (UUID)
- `code` (`boss_travel_assignment`, `best_friend_need_you_outside`, etc.)
- `category` (`work | family | social | logistics | safety`)
- `caller_persona` (`boss | coworker | sibling | roommate | best_friend | partner`)
- `reason_code` (`travel_assignment_abroad | urgent_work_issue | family_checkin | issue_at_home | need_you_outside | safety_checkin`)
- `display_name`
- `description`
- `active`
- `created_at`

### TemplateVersions

Versioned, localized template behavior.

Fields:
- `id` (UUID)
- `template_id`
- `version`
- `locale`
- `supports_call`
- `supports_sms`
- `call_system_prompt_template` (nullable)
- `call_opening_line_template` (nullable)
- `call_followup_facts_json` (nullable)
- `call_voice_profile_code` (nullable)
- `call_max_duration_seconds` (nullable)
- `call_supports_interruptions`
- `sms_body_template` (nullable)
- `sms_followup_body_template` (nullable)
- `sms_sender_style` (nullable)
- `active`
- `created_at`

Rules:
- Exactly one active version per `(template_id, locale)` in MVP.
- The worker copies a **resolved snapshot** of the version into each request.
- A template may support only call, only sms, or both.

### Requests

User intent to receive a call or message.

Fields:
- `id` (UUID)
- `user_id`
- `template_id`
- `template_version_id`
- `channel` (`call | sms`)
- `primary_phone_number_id`
- `service_identity_id` (nullable until dispatch)
- `client_request_id`
- `requested_at`
- `execute_at`
- `status`
- `cancel_reason`
- `scheduled_kind` (`immediate | delayed | exact_time`)
- `request_plan_snapshot_json`
- `credit_cost_units`
- `credits_reserved`
- `last_error_code`
- `last_error_message`
- `created_at`
- `updated_at`

Rule:
- There is **no free target-number field** on this entity.

### CallAttempts

Concrete provider dispatch attempts for call requests.

Fields:
- `id` (UUID)
- `request_id`
- `attempt_no`
- `provider` (`mock_voice | vapi`)
- `provider_call_id`
- `provider_status`
- `status`
- `started_at`
- `ringing_at`
- `answered_at`
- `ended_at`
- `ended_reason`
- `duration_seconds`
- `estimated_cost_minor`
- `provider_payload_sanitized_json`
- `created_at`
- `updated_at`

### MessageAttempts

Concrete provider dispatch attempts for SMS requests.

Fields:
- `id` (UUID)
- `request_id`
- `attempt_no`
- `provider` (`mock_sms | twilio_messaging`)
- `provider_message_id`
- `provider_status`
- `status`
- `queued_at`
- `sent_at`
- `delivered_at`
- `failed_at`
- `failure_reason`
- `estimated_cost_minor`
- `provider_payload_sanitized_json`
- `created_at`
- `updated_at`

### RequestArtifacts

Optional minimal output from completed requests.

Fields:
- `id` (UUID)
- `request_id`
- `summary_text` (nullable)
- `delivered_message_preview` (nullable)
- `transcript_pointer` (nullable)
- `recording_pointer` (nullable)
- `retention_delete_after`
- `created_at`

MVP rules:
- Calls store summary only by default.
- Do not persist transcript or recording unless explicitly enabled later.
- SMS may store only a short delivered preview or rendered template snapshot.

### WebhookEvents

Append-only raw webhook log.

Fields:
- `id` (UUID)
- `provider`
- `external_event_id`
- `event_type`
- `payload_json`
- `received_at`
- `processed_at`
- `processing_status`
- `error_message`

### UsageDaily

Daily rollups for reporting and anomaly detection.

Fields:
- `id` (UUID)
- `user_id`
- `date`
- `requests_count`
- `calls_count`
- `sms_count`
- `completed_count`
- `failed_count`
- `total_call_duration_seconds`
- `estimated_cost_minor`

---

## State Machines

### Request status

Common lifecycle:

`scheduled -> dispatching -> provider_accepted -> completed`

Additional states:
- `active` (call only; ringing or connected)
- `failed`
- `canceled`
- `expired`

Notes:
- `scheduled` includes immediate and future requests that are not yet dispatched.
- `provider_accepted` means the provider accepted the outbound dispatch.
- `active` is used only for voice calls.

### CallAttempt status

`created -> provider_requested -> queued -> ringing -> in_progress -> ended`

Terminal statuses:
- `failed_pre_dial`
- `failed_post_dial`
- `canceled`

### MessageAttempt status

`created -> provider_requested -> queued -> sent -> delivered`

Terminal statuses:
- `failed_pre_send`
- `failed_post_send`
- `canceled`

### Session status

`active -> revoked | expired`

---

## Scheduling and Job Execution

### Durable scheduler

Use PostgreSQL as the scheduler source of truth.

Worker loop:
1. Poll due `requests` where `status = scheduled` and `execute_at <= now()`.
2. Claim rows using `FOR UPDATE SKIP LOCKED`.
3. Transition request to `dispatching` in the same transaction.
4. Dispatch through the correct provider adapter based on `channel`.
5. Persist `call_attempt` or `message_attempt`.

### Why not rely only on provider scheduling

Because we need:
- cancellation from our API
- entitlement checks at execution time
- retries
- analytics
- consistent history
- provider portability

### Retry policy

Retry only **pre-dispatch technical failures**.

Allowed retry reasons:
- network timeout before provider acknowledgement
- transient 5xx from provider
- temporary connection error

Do **not** auto-redispatch when:
- a call rang the user
- a call connected
- an SMS was sent or delivered
- the provider indicates a human-facing outcome already happened

Retry limits:
- call requests: 1 retry for pre-dial failures
- sms requests: 1 retry for pre-send failures
- exact-time scheduled requests: retries only within a short grace window

### Reconciliation job

Run a periodic reconciliation job that looks for attempts stuck in non-terminal
states too long and either:
- refreshes provider state when possible, or
- marks them failed with an internal timeout reason.

---

## API Contract

Base path: `/v1`

All request / response bodies are JSON.

### Authentication

#### `POST /v1/auth/phone/start`
Start OTP verification.

Request:
```json
{
  "phone_number": "+491234567890",
  "device_id": "ios-device-uuid",
  "locale": "de"
}
```

Response:
```json
{
  "verification_id": "uuid",
  "channel": "sms",
  "expires_in_seconds": 600
}
```

#### `POST /v1/auth/phone/confirm`
Confirm OTP code, create / load user, issue session token.

Request:
```json
{
  "verification_id": "uuid",
  "code": "123456",
  "device_id": "ios-device-uuid"
}
```

Response:
```json
{
  "session_token": "opaque-secret",
  "user": {
    "id": "uuid",
    "locale": "de",
    "phone_number_masked": "+49******890"
  }
}
```

#### `POST /v1/auth/logout`
Revokes current session.

### Profile

#### `GET /v1/me`
Returns user profile, verified primary phone snapshot, entitlement summary, and
active request summary if any.

#### `PATCH /v1/me`
Allows updating locale, timezone, and display name.

### Devices

#### `PUT /v1/devices/current`
Registers or updates APNs token and app version.

### Templates

#### `GET /v1/templates`
Returns active template catalog for the user's locale.

Response shape includes:
- `id`
- `code`
- `display_name`
- `description`
- `category`
- `caller_persona`
- `reason_code`
- `supported_channels`
- `call_max_duration_seconds` (if call supported)
- `preview_opening_line`
- `preview_sms_body`

### Requests

#### `POST /v1/requests`
Creates an immediate or scheduled request.

Request:
```json
{
  "client_request_id": "uuid",
  "template_id": "uuid",
  "channel": "call",
  "delay_seconds": 30,
  "scheduled_at": null
}
```

Rules:
- `channel` must be `call` or `sms`.
- Exactly one of `delay_seconds` or `scheduled_at` may be set.
- `delay_seconds` allowed values in MVP: `0`, `30`, `300`.
- `scheduled_at` must be within the next 24 hours.
- Backend ignores no client-supplied destination. If a destination-number field
  is sent anyway, validation fails.
- Backend validates that the chosen template supports the chosen channel.

Response:
```json
{
  "request_id": "uuid",
  "channel": "call",
  "status": "scheduled",
  "execute_at": "2026-06-12T18:45:00Z",
  "credits_available": 4,
  "cancelable": true
}
```

#### `GET /v1/requests/{request_id}`
Returns current request state and latest attempt summary.

#### `POST /v1/requests/{request_id}/cancel`
Cancels a request if still cancelable.

Response:
```json
{
  "request_id": "uuid",
  "status": "canceled"
}
```

### History

#### `GET /v1/history`
Paginated request history across both channels.

Fields:
- request id
- channel
- template label
- requested at
- final status
- duration (for calls)
- delivered preview / summary

### Entitlements

#### `GET /v1/entitlements`
Returns current plan / credits summary.

Response:
```json
{
  "credits_available": 4,
  "active_entitlements": [
    {
      "plan_code": "credits_5",
      "status": "active"
    }
  ]
}
```

### Webhooks

#### `POST /v1/webhooks/voice`
Receives provider call status events.

#### `POST /v1/webhooks/sms`
Receives provider sms delivery events.

Requirements:
- signature verification if available
- raw payload persisted before processing
- idempotent by external event id where possible

#### `POST /v1/webhooks/revenuecat`
Receives purchase / subscription updates.

### Health

#### `GET /health/live`
Liveness probe.

#### `GET /health/ready`
Readiness probe (DB + critical config loaded).

---

## Error Model

Use a consistent JSON error envelope.

```json
{
  "error": {
    "code": "insufficient_credits",
    "message": "You do not have enough credits to send this request.",
    "retryable": false,
    "request_id": "server-request-id"
  }
}
```

Common error codes:
- `unauthorized`
- `session_expired`
- `phone_not_verified`
- `invalid_phone_number`
- `unsupported_line_type`
- `rate_limited`
- `active_request_exists`
- `template_channel_not_supported`
- `insufficient_credits`
- `invalid_schedule_window`
- `request_not_cancelable`
- `provider_unavailable`
- `internal_error`

---

## Authentication and Verification

### Identity approach

- Phone number is the login handle.
- User ID is the canonical identity.
- Session token is opaque and stored hashed.

### Verification flow

- Normalize input to E.164.
- Start OTP verification through the configured OTP provider.
- Confirm OTP.
- Mark number verified.
- Create user session.

### Number-change flow

- User starts verification for a new number.
- New number must complete OTP verification.
- On success, old primary number becomes `replaced`.
- New number becomes the only `primary` verified number.
- Existing scheduled requests should be canceled with a clear reason in MVP.

---

## Provider Integration

### Provider strategy

The first coding pass must **not** depend on manual provider dashboard setup.

The backend must be implemented against provider abstractions and shipped with
working mocks.

### Required abstractions

#### OTP provider
- `start_verification(phone_number, locale)`
- `confirm_verification(verification_id, code)`
- `lookup_number(phone_number)` (optional)

#### Voice provider
- `create_outbound_call(request_plan)`
- `cancel_call(provider_call_id)`
- `parse_webhook(payload)`
- `get_call_state(provider_call_id)` (optional)

#### Message provider
- `send_sms(request_plan)`
- `cancel_sms(provider_message_id)` (best effort / optional)
- `parse_webhook(payload)`
- `get_message_state(provider_message_id)` (optional)

### Required implementations in MVP coding pass

- `MockOtpProvider`
- `MockVoiceCallProvider`
- `MockMessageProvider`

These mocks must simulate success, failure, cancellation, duplicate webhooks,
and basic timing transitions.

### Later manual integrations

These are **not** required for the first coding pass:
- `TwilioVerifyProvider`
- `TwilioLookupProvider`
- `VapiVoiceProvider`
- `TwilioMessagingProvider`

Reason:
- account creation and dashboard setup are manual
- API keys / numbers / assistants / webhook URLs are manual
- provider behavior must be tested after human setup, not invented by the code

### Provider modes

Support configuration like:
- `OTP_PROVIDER=mock|twilio_verify`
- `VOICE_PROVIDER=mock|vapi`
- `MESSAGE_PROVIDER=mock|twilio_messaging`

Default local mode should be `mock`.

### Request-plan snapshot

At dispatch time, build a `request_plan_snapshot_json` containing:
- template code
- template version
- locale
- channel
- caller persona
- reason code
- rendered call opening line or sms body
- allowed follow-up facts
- voice config (for calls)
- duration cap (for calls)
- service identity used
- target phone number id (internal only)

This snapshot makes history reproducible even after template edits.

### Call strategy

Use **versioned templates with variable substitution**, not fully dynamic prompt
generation.

Allowed variables:
- locale
- user first name (optional)
- caller persona label
- reason label
- urgency label

Disallowed in MVP:
- open-ended user-authored prompts
- tool-calling during live calls
- retrieval of external data during the call

### SMS strategy

SMS in MVP is:
- one-way outbound only
- template-rendered, not free-form AI generated
- optionally supports one predefined follow-up text later, but not required in
  the first build

The backend may store a rendered preview for history, but it should avoid
keeping unnecessary raw content longer than needed.

### Cost controls

- Hard duration cap per call template version.
- Limited template catalog.
- No recording persistence by default.
- No transcript persistence by default.
- No AI texting conversation in MVP.
- One credit unit per request by default in MVP; channel-specific weighting can
  be added later.

---

## Payments and Entitlements

### MVP monetization shape

Backend must support:
- one free onboarding / test allowance (optional, feature-flagged)
- one-time credit packs
- subscription-compatible schema for later monthly included credits

### Store model

- iOS purchases happen via StoreKit on device.
- RevenueCat can later act as the bridge for entitlement updates.
- Backend stores normalized entitlement state and immutable credit ledger
  entries.

### Credit policy

- A request cannot be dispatched without available credits.
- Credits are reserved at dispatch time.
- If dispatch fails before the provider accepts the request, reservation is
  released.
- If the provider accepts the dispatch, the credit is captured.

This avoids burning credits for internal failures while still protecting cost.

---

## Abuse Prevention and Security

### Hard product rules

- Only verified primary number may receive calls or texts.
- One active live request per user at a time.
- No arbitrary destination numbers.
- No anonymous calling or texting features.

### Rate limits

Apply limits by:
- IP address
- device id
- phone hash
- user id

MVP examples:
- OTP start: max 5 / hour / phone hash
- OTP confirm: max 10 / hour / verification id
- request creation: max 5 / hour / user, lower for new accounts
- session creation bursts: aggressively limited

Implementation note:
- In the first coding pass, Postgres-backed counters / windows are acceptable.
- Redis may be added later if rate-limit pressure or concurrency pain appears.

### Storage of phone numbers

- Store phone numbers encrypted at rest.
- Store a deterministic hash for uniqueness and abuse controls.
- Never write raw phone numbers to structured application logs.
- Mask phone numbers in API responses and admin output.

### Session security

- Store session token hashes only.
- Rotate session token on login.
- Revoke on logout.
- Expire inactive sessions.

### Webhook security

- Verify provider webhook authenticity where supported.
- Persist raw webhook before processing.
- Deduplicate repeated delivery.

### Privacy / retention

- Retain only data needed to operate the service and support the user.
- Default retention:
  - request history summary: retained
  - raw provider webhook payloads: limited retention
  - transcripts / recordings: off by default
  - rendered sms previews: minimal / capped retention if stored at all
- User deletion should soft-delete account, revoke sessions, and enqueue PII
  purge subject to financial-record retention needs.

---

## Observability and Operations

### Structured logging

Every log line should include, when applicable:
- `request_id`
- `user_id`
- `interaction_request_id`
- `call_attempt_id` or `message_attempt_id`
- `provider`
- `provider_external_id`
- `template_code`
- `channel`

### Metrics

Track:
- OTP start / success / failure counts
- signup conversion
- request count
- call-vs-sms mix
- scheduled-vs-immediate mix
- dispatch latency
- provider acceptance rate
- call completion rate
- sms delivery rate
- failure reasons
- average call duration
- estimated cost per completed request
- webhook processing lag

### Alerts

Create alerts for:
- provider failure spike
- webhook processing backlog
- dispatch latency spike
- unusually high OTP volume
- unusually high failed-verification volume
- DB connectivity issues

### Runbooks

Create docs for:
- provider outage handling
- stuck scheduled requests
- credit ledger correction procedure
- sender-identity rotation / reputation issues

---

## Repository Layout (target)

```text
backend/
├── BACKEND_SPEC.md              ← this file
├── README.md
├── pyproject.toml
├── alembic.ini
├── Makefile
├── .env.example
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── routes/
│   │   │   ├── auth.py
│   │   │   ├── me.py
│   │   │   ├── devices.py
│   │   │   ├── templates.py
│   │   │   ├── requests.py
│   │   │   ├── history.py
│   │   │   ├── entitlements.py
│   │   │   ├── webhooks_voice.py
│   │   │   ├── webhooks_sms.py
│   │   │   └── webhooks_revenuecat.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── rate_limit.py
│   ├── db/
│   │   ├── session.py
│   │   ├── base.py
│   │   ├── models/
│   │   └── repositories/
│   ├── domain/
│   │   ├── auth/
│   │   ├── requests/
│   │   ├── templates/
│   │   ├── billing/
│   │   └── users/
│   ├── providers/
│   │   ├── otp/
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   └── twilio_verify.py
│   │   ├── voice/
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   └── vapi.py
│   │   ├── messaging/
│   │   │   ├── base.py
│   │   │   ├── mock.py
│   │   │   └── twilio_sms.py
│   │   └── revenuecat.py
│   ├── workers/
│   │   ├── scheduler.py
│   │   ├── dispatch.py
│   │   ├── reconciliation.py
│   │   └── cleanup.py
│   ├── seeds/
│   │   └── templates/
│   │       ├── boss_travel_assignment.de.yaml
│   │       ├── boss_travel_assignment.en.yaml
│   │       ├── coworker_urgent_work_issue.de.yaml
│   │       ├── coworker_urgent_work_issue.en.yaml
│   │       ├── sibling_family_checkin.de.yaml
│   │       ├── sibling_family_checkin.en.yaml
│   │       ├── roommate_issue_at_home.de.yaml
│   │       ├── roommate_issue_at_home.en.yaml
│   │       ├── best_friend_need_you_outside.de.yaml
│   │       ├── best_friend_need_you_outside.en.yaml
│   │       ├── safety_checkin.de.yaml
│   │       └── safety_checkin.en.yaml
│   └── schemas/
│       ├── auth.py
│       ├── me.py
│       ├── templates.py
│       ├── requests.py
│       ├── history.py
│       └── webhooks.py
├── alembic/
│   ├── env.py
│   └── versions/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── fixtures/
└── docs/
    ├── api_examples/
    ├── runbooks/
    └── decision_records/
```

---

## Environment Variables

Required for first coding pass:
- `APP_ENV`
- `APP_SECRET_KEY`
- `DATABASE_URL`
- `SESSION_TOKEN_TTL_DAYS`
- `PHONE_ENCRYPTION_KEY`
- `OTP_PROVIDER`
- `VOICE_PROVIDER`
- `MESSAGE_PROVIDER`

Optional / later:
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_VERIFY_SERVICE_SID`
- `TWILIO_MESSAGING_SERVICE_SID`
- `VAPI_API_KEY`
- `REVENUECAT_WEBHOOK_SECRET`
- `SENTRY_DSN`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `FEATURE_FREE_TEST_REQUEST`
- `SUPPORTED_COUNTRIES`

---

## Testing Strategy

### Unit tests

Must cover:
- phone normalization
- own-number-only invariant
- template selection
- request-plan snapshot generation
- entitlement checks
- credit ledger reservation / capture / release
- rate-limit helpers
- status transition guards
- channel support validation

### Integration tests

Must cover:
- OTP start / confirm flow via mock provider
- create immediate call request
- create immediate sms request
- create delayed request
- create exact-time request
- cancel request
- dispatch worker success path for call
- dispatch worker success path for sms
- retry on transient pre-dispatch failure
- webhook ingestion idempotency
- revenue entitlement update (if enabled)

### Contract tests

- OpenAPI schema generation
- stable response shapes for iOS client
- provider adapter fixtures

### Critical regression tests

There must be explicit tests proving:
- the API rejects any attempt to specify a different target number
- a user cannot create a request without a verified primary number
- a user cannot create two active live requests concurrently
- a template cannot be used on an unsupported channel

---

## Seed Data

Seed the following on bootstrap:
- templates:
  - `boss_travel_assignment`
  - `coworker_urgent_work_issue`
  - `sibling_family_checkin`
  - `roommate_issue_at_home`
  - `best_friend_need_you_outside`
  - `safety_checkin`
- localized active template versions for `en` and `de`
- default free / credit-pack plan records

Seed data should be deterministic and idempotent.

---

## Local Development

- Use Docker Compose for Postgres.
- Default all providers to `mock`.
- The system must run locally without any external provider account.
- Use ngrok or similar **only** when manually testing real-provider webhooks.
  It is not part of production architecture and not required in mock mode.
- Keep provider credentials optional for local non-integration test runs.

---

## Decisions Locked

| Area | Decision |
|------|----------|
| Backend language | Python |
| API framework | FastAPI |
| Architecture | Modular monolith |
| Processes | API + worker |
| Durable scheduler | PostgreSQL |
| Ephemeral coordination in first coding pass | No Redis required |
| Identity | user UUID + phone login handle |
| Auth style | Passwordless OTP + opaque sessions |
| Destination number | Only verified primary user number |
| Channels | call + sms |
| Template model | versioned templates with caller persona + reason |
| Voice provider in first coding pass | Mock provider |
| SMS provider in first coding pass | Mock provider |
| OTP provider in first coding pass | Mock provider |
| Real voice target provider later | Vapi |
| Real sms target provider later | Twilio Messaging or similar |
| Real otp target provider later | Twilio Verify |
| Prompt strategy | Versioned templates, no free-form runtime generation |
| Storage | PostgreSQL |
| Billing model support | credit ledger + entitlement records |
| Recordings / transcripts | Off by default |
| Mobile client for MVP | iOS (SwiftUI) |
| Scheduling window | up to 24 hours |
| Concurrent active request rule | max 1 per user |

---

## Decisions Deferred

- Second voice provider for fallback
- Web client / admin UI
- Android client
- Inbound SMS replies
- AI-generated SMS variants
- Per-country sender-identity routing sophistication
- Subscription packages and pricing
- Full deletion workflows / DSR automation UI
- Redis introduction for higher concurrency
- Advanced fraud scoring
- Analytics warehouse

---

## Non-Negotiable Acceptance Criteria

The MVP backend is not done until all of the following are true:

- [ ] A user can verify a phone number with OTP and receive a session token.
- [ ] The backend stores exactly one verified primary number per user.
- [ ] The API can create immediate, 30-second, 5-minute, and exact-time requests.
- [ ] A request can target either `call` or `sms` when the template supports it.
- [ ] Scheduled requests survive API restarts because they are stored in PostgreSQL.
- [ ] The worker can dispatch due requests through the provider adapter.
- [ ] Mock voice and sms providers simulate realistic lifecycle events.
- [ ] Credits are checked server-side before dispatch.
- [ ] A user cannot trigger a call or text to any number except their own verified primary number.
- [ ] A second active live request is blocked while one is already active.
- [ ] History is queryable from the API across both channels.
- [ ] Phone numbers are encrypted at rest and masked in logs / responses.
- [ ] Basic rate limits exist for OTP and request creation.
- [ ] The project runs locally with Postgres only and documented setup steps.

---

## Final Reminder

This backend should feel conservative and understandable.

The product may feel playful, stylish, or socially clever on the surface, but
the backend must behave like a payments-and-communications system: explicit
states, strong invariants, minimal magic, and no trust in the client for
anything load-bearing.

If forced to choose between "more flexible" and "harder to misuse", choose
**harder to misuse**.

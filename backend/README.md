# BelievableCall — Backend (MVP)

Believable interruption / alibi app backend. The user taps once and receives a
believable **call** or **text** on **their own verified phone number** so they
can step away from a situation.

The source of truth for behavior is [`BACKEND_SPEC.md`](./BACKEND_SPEC.md).

## Stack

- Python 3.11+ · FastAPI · Pydantic v2 · SQLAlchemy 2.x · Alembic
- PostgreSQL in production; **SQLite by default** locally so the project runs
  with zero external services
- Providers behind adapters with working **mocks** (OTP / voice / SMS) — no
  external account needed for the first coding pass

## Load-bearing rules (enforced in code)

- A user may only trigger calls/texts to their **own verified primary number**.
  The client never sends a destination number; the request schema rejects any
  such field (`extra="forbid"`).
- One verified primary number per user.
- At most one active live request per user.
- Create-request is idempotent per `(user, client_request_id)`.
- Scheduled requests live in PostgreSQL (durable scheduler), not just in-memory.
- Credits are checked before dispatch, reserved at dispatch, captured on
  provider acceptance, released on pre-dispatch failure.
- Templates are versioned and server-controlled; SMS is one-way.
- **Stable sender identity** (SMS): the backend allocates a sender line once per
  `(user, sender persona, channel)` and reuses it for every later send from the
  same persona — independent of whether the user saves a contact (see below).

## Stable sender identity + save contact (SMS)

So a text from a persona such as *Boss* keeps coming from the **same** number
over time, the backend owns a sticky sender binding. The contact-save UI on iOS
is a pure convenience layer on top of it — continuity never depends on it.

- **Sender lines** are the `service_identities` pool (a provider-controlled
  outbound identity we own and can send from). Twilio/Vapi handles live on this
  row (`external_identity_id`, `twilio_messaging_service_sid`,
  `vapi_phone_number_id`) at the infrastructure edge; the domain stays
  provider-agnostic.
- **Sender bindings** (`user_sender_bindings`) map `(user, sender_persona_key,
  channel) → sender_line`, unique on that triple. Allocation happens at SMS
  **create** time so the response can return the sender identity synchronously:
  reuse an active binding if present, else pick an active SMS-capable line. If
  the bound line is disabled, the binding is re-pointed to a replacement
  (marked through `orphaned`) without mutating past history.
- With a **single** Twilio number, several personas simply bind to the same
  line — allowed by design (the unique constraint is on the persona, not the
  line). Multiple coherent saved-contact identities just need more numbers in
  the pool.
- Templates carry `sender_persona_key` / `sender_display_name` /
  `supports_contact_save` (defaulted from `caller_persona` / `display_name` at
  seed time), so different templates from one persona share a binding.
- Each request persists an immutable **sender snapshot**
  (`sender_binding_id`, `sender_persona_key`, `sender_display_name_snapshot`,
  `sender_phone_e164_snapshot`); the dispatcher sends through the bound line.
- API: `POST /v1/requests` and `GET /v1/requests/{id}` return a
  `sender_identity` object (`sender_binding_id`, `sender_persona_key`,
  `sender_display_name`, `sender_phone_e164`, `contact_prompt_recommended`);
  `GET /v1/history` exposes the snapshot fields. Calls and texts from one
  persona share a line whenever it can do both, so a saved contact shows for both.
- The own-number delivery invariant is unchanged: `sender_*` is the *from*
  side; delivery still only ever goes to the user's verified primary number.

### Keeping the sender pool in sync with Twilio

`service_identities` is a local mirror of Twilio's number inventory. Twilio owns
which numbers exist; this backend mirrors them so bindings/snapshots/contacts
show real numbers. After adding/removing/rotating Twilio numbers:

```bash
make sync-senders        # python -m app.admin.sync_sender_lines
```

It upserts the Messaging Service's numbers (or all account numbers) into the
pool, disables ones that vanished (their bindings then reallocate on next send),
and stops using the mock seed line for SMS once a real SMS number exists.

To guarantee the recipient always sees the bound number, SMS is sent with that
number as an **explicit `From`** (a Messaging Service can otherwise rotate the
sender). The env sender (`TWILIO_MESSAGING_SERVICE_SID` / `TWILIO_SMS_FROM_NUMBER`)
is only the fallback used when no bound line is resolved.

## Quick start (local, SQLite, all-mock)

First-time setup — one command (deps + config + DB schema + seed data):

```bash
cd backend
make bootstrap
```

Then configure-and-run the API (idempotent; safe to run every time):

```bash
make start            # migrate + seed, then uvicorn on :8000 (http://localhost:8000/docs)
```

Other useful targets:

```bash
make test             # run the full test suite (119 tests)
make worker           # scheduler + dispatch + reconciliation + cleanup loop
make api              # serve only (assumes the DB is already set up)
make setup            # prepare the DB only (migrate + seed), no server
make clean            # drop the local SQLite DB
```

### End-to-end by hand (mock OTP code is always `123456`)

```bash
# 1. start + confirm OTP -> session token
curl -s localhost:8000/v1/auth/phone/start \
  -H 'content-type: application/json' \
  -d '{"phone_number":"+491701234567","device_id":"d1","locale":"en"}'
# -> {"verification_id": "...", ...}

curl -s localhost:8000/v1/auth/phone/confirm \
  -H 'content-type: application/json' \
  -d '{"verification_id":"<id>","code":"123456","device_id":"d1"}'
# -> {"session_token":"<token>", ...}

# 2. list templates, then create a request (no destination number is ever sent)
curl -s localhost:8000/v1/templates -H "Authorization: Bearer <token>"
curl -s localhost:8000/v1/requests -H "Authorization: Bearer <token>" \
  -H 'content-type: application/json' \
  -d '{"client_request_id":"r1","template_id":"<id>","channel":"call","delay_seconds":0}'
```

The worker dispatches due requests through the mock provider; mock voice/SMS
lifecycle events can be posted to `/v1/webhooks/voice` and `/v1/webhooks/sms`.

## Interactive terminal app (mimics the frontend)

`scripts/app.py` is a keyboard-driven TUI that behaves like the iOS app: sign
in with your phone number, schedule a believable call/text, then watch it
**ring on screen** and read the caller's script. It talks to the API over HTTP
and embeds the dispatch + provider-webhook simulation, so a scheduled call
actually fires without running a separate worker.

```bash
make api          # terminal 1 — the backend must be running
make app          # terminal 2 — launch the TUI
# or open it in its own macOS window:
make app-window
```

Navigate with the arrow keys / Enter. The mock OTP code is `123456`.

## CLI (scriptable API client)

`scripts/cli.py` is a non-interactive client for scripting/testing:

```bash
python scripts/cli.py demo          # full all-mock flow end to end
python scripts/cli.py signup --phone +491701234567
python scripts/cli.py create --template boss_travel_assignment --channel call
python scripts/cli.py dispatch      # run one local worker tick
python scripts/cli.py simulate <request_id>
```

## Using PostgreSQL instead of SQLite

```bash
pip install ".[postgres]"
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/believablecall"
alembic upgrade head && python -m app.seeds.seed
```

The application code is plain Postgres + FastAPI and does not depend on any
Supabase-specific auth or Edge Functions. The durable scheduler uses
`FOR UPDATE SKIP LOCKED` on Postgres (a no-op on SQLite).

## Switching to real providers (later, manual)

Set the provider env vars and supply credentials (account setup is manual and
out of scope for the first coding pass):

```
OTP_PROVIDER=twilio_verify
VOICE_PROVIDER=vapi
MESSAGE_PROVIDER=twilio_messaging
```

The real adapters (`TwilioVerifyProvider`, `VapiVoiceProvider`,
`TwilioMessagingProvider`) implement the same interfaces as the mocks.

### Twilio Verify (real OTP)

`TwilioVerifyProvider` (`app/providers/otp/twilio_verify.py`) is implemented
and ready to use — only account setup + config is needed:

1. Create a Twilio account: https://www.twilio.com/try-twilio
2. Console > Account > **Account SID** and **Auth Token**.
3. Console > **Verify** > **Services** > create a new Service -> its SID
   (starts with `VA`).
4. In `.env`, set:
   ```
   OTP_PROVIDER=twilio_verify
   TWILIO_ACCOUNT_SID=ACxxxxxxxx...
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_VERIFY_SERVICE_SID=VAxxxxxxxx...
   ```
5. Restart the API (`make api` / `make start`).

Notes:
- Trial Twilio accounts can only send to phone numbers verified in the
  console — verify your own test number there first.
- `make test` always forces `OTP_PROVIDER=mock` (see `tests/conftest.py`), so
  the test suite never calls Twilio and the mock code `123456` keeps working
  for CI regardless of `.env`.
- Provider failures map to the standard error envelope: a Twilio outage
  surfaces as `provider_unavailable` (503, retryable); an invalid number on
  `/v1/auth/phone/start` surfaces as `invalid_phone_number` (422).

### Twilio Messaging (real SMS)

`TwilioMessagingProvider` (`app/providers/messaging/twilio_sms.py`) sends
one-way outbound SMS via Twilio Programmable Messaging. Account setup + config:

1. Same Twilio account; reuse **Account SID** and **Auth Token**.
2. Choose a sender, one of:
   - Console > **Messaging** > **Services** > create a Service -> its SID
     (starts with `MG`) — recommended, or
   - keep/buy an SMS-capable phone number (E.164, e.g. `+18885550000`).
3. In `.env`, set:
   ```
   MESSAGE_PROVIDER=twilio_messaging
   TWILIO_ACCOUNT_SID=ACxxxxxxxx...
   TWILIO_AUTH_TOKEN=your_auth_token
   # one of:
   TWILIO_MESSAGING_SERVICE_SID=MGxxxxxxxx...
   # TWILIO_SMS_FROM_NUMBER=+18885550000
   ```
4. Restart the API and the **worker** (`make worker` dispatches SMS requests).

Delivery status (→ **Completed**):
- The send alone gets a request to `provider_accepted`. To advance to
  `delivered`/`completed`, Twilio must post status callbacks to
  `POST /v1/webhooks/sms`, which means this app needs a public URL.
- Expose it (e.g. `ngrok http 8000`) and set
  `TWILIO_STATUS_CALLBACK_URL=https://<public-host>/v1/webhooks/sms`.
- Twilio sends callbacks form-encoded; the webhook route accepts both
  form-encoded (Twilio) and JSON (mock). Without a public callback URL the
  request stays at `provider_accepted` and reconciliation sweeps it after the
  inflight timeout.

Notes:
- Trial Twilio accounts can only text numbers verified in the console.
- `make test` forces `MESSAGE_PROVIDER=mock`, so the suite never calls Twilio.
- Failures map to the error envelope: 5xx/429 → `provider_unavailable`
  (retryable, 1 pre-send retry); 4xx (e.g. invalid number) → hard failure.

### Vapi (real voice calls)

`VapiVoiceProvider` (`app/providers/voice/vapi.py`) places outbound calls via
Vapi. The agent itself is not configured in Vapi: prompt, model, voice and
transcriber live in `app/agent` and go along with every call as a transient
assistant, so changes to the agent are code changes with tests.

1. Create a Vapi account: https://dashboard.vapi.ai
2. **API Keys** → copy a private key → `VAPI_API_KEY`.
3. Set up Twilio first (above), then link its numbers in Vapi:
   `make sync-senders-vapi`. This imports every voice-capable Twilio line into
   Vapi and stores the Vapi id on the line, so a persona calls from the same
   number it texts from and the contact the user saved shows up.
   `VAPI_PHONE_NUMBER_ID` is only a fallback.
4. In `.env`, set:
   ```
   VOICE_PROVIDER=vapi
   VAPI_API_KEY=...
   PUBLIC_BASE_URL=https://<public-host>
   VAPI_WEBHOOK_SECRET=<random>
   ```
5. Restart the API and the **worker** (`make worker` dispatches call requests).

`max_duration_seconds` caps call length. Background sound is off, so the call
doesn't sound like an office.

Call status (ringing → in progress → **Completed**):
- Each call tells Vapi to post events to `<PUBLIC_BASE_URL>/v1/webhooks/voice`
  (use `ngrok http 8000` locally) with `VAPI_WEBHOOK_SECRET` as header.
- Vapi echoes that secret as the `X-Vapi-Secret` header; the webhook rejects any
  request whose secret doesn't match (403) when `VOICE_PROVIDER=vapi` and the
  secret is set. Mock/local modes skip the check so `simulate` keeps working.
- Without a public Server URL the call still happens but status stays at
  `provider_accepted`; reconciliation sweeps it after the inflight timeout.

Notes:
- `make test` forces `VOICE_PROVIDER=mock`, so the suite never calls Vapi.
- Failures map to the error envelope: 5xx/429 → `provider_unavailable`
  (retryable, 1 pre-dial retry); 4xx → hard failure.

## Layout

```
app/
  api/        FastAPI routes + deps
  core/       config, security (phone encryption + hashing), logging, rate limit, errors
  db/         models + session + base
  domain/     auth, users, templates, requests, billing (the business rules)
  providers/  otp/voice/messaging adapters + mocks + factory
  workers/    scheduler, dispatch, reconciliation, cleanup
  seeds/      template YAMLs + idempotent seeding
alembic/      migrations
tests/        unit, integration, contract/regression
```

## Privacy

- Phone numbers are encrypted at rest (Fernet) and masked in API output.
- A deterministic HMAC hash is used for uniqueness / rate limits without
  decryption. Raw numbers are never written to structured logs.
- Recordings and transcripts are off by default.

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

## Quick start (local, SQLite, all-mock)

```bash
cd backend
make install          # create .venv (py3.11) and install deps
make env              # cp .env.example .env
make migrate          # alembic upgrade head  (creates the schema)
make seed             # seed plans + templates (en/de) + mock sender identity
make test             # run the full test suite (62 tests)
```

Run the API and worker (two terminals):

```bash
make api              # uvicorn on :8000  (http://localhost:8000/docs)
make worker           # scheduler + dispatch + reconciliation + cleanup loop
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

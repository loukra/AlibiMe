# AlibiMe

**Get a believable call or text on your own phone — your graceful way out of any situation.**

AlibiMe lets you summon a realistic phone call or SMS to *your own verified
number*, on demand or on a timer, so you can step away from an awkward date, a
dragging meeting, or an unsafe situation without making a scene. You pick a
believable scenario, choose call or text, set the timing — and your phone rings
or buzzes right on cue.

> The internal Swift module and original codename is **BelievableCall**; the
> shipping product is **AlibiMe**.

---

## The idea

The core experience is one tap away:

1. **Pick a template** — a believable situation like *Boss — urgent travel
   assignment*, *Best friend — needs you outside*, or *Roommate — issue at
   home*. Each template is one concept that can run as a **call**, a **text**,
   or **both**.
2. **Choose a channel** — call or text, whichever fits the moment.
3. **Choose timing** — now, in 30 seconds, in 5 minutes, or scheduled.
4. **Receive it** — the call/text arrives on your phone, sounding and reading
   like the real thing.

### The one rule that matters

AlibiMe **only ever contacts your own verified phone number.** There is no
third-party destination, ever — you can't use it to call or text someone else.
It's a personal exit tool, not a way to reach other people.

### What makes it believable

- **Real voice calls** via [Vapi](https://vapi.ai) — a short, in-character
  conversation that stays on script and ends naturally.
- **Real SMS** via [Twilio](https://www.twilio.com), with a **stable sender
  identity**: a text from "Boss" keeps coming from the same number over time,
  and you can optionally save that sender as a contact so it looks established.
- **Channel-specific wording** — a believable text and a believable call read
  differently, but they're the same underlying scenario.

---

## Features

- **One unified template library** — built-in scenarios spanning work, family,
  social, logistics, and safety. One template, multiple channels.
- **Custom templates** — build your own from safe, structured choices (persona ×
  reason × urgency × channels). The believable wording is composed by the
  backend from approved building blocks — there's no free-form text that could
  be abused.
- **Credits** — actions cost credits; an in-app **Add Credits** flow tops them
  up (free in the current build, ready to switch to real purchases later).
- **Save Contact** — turn a recurring SMS sender into a saved contact in one tap.
- **A calm corner** — an ambient screen of nothing but drifting waves, for when
  you just need a breath.

---

## How it's built

Two halves, each independently runnable and testable:

| | Stack |
|---|---|
| **`backend/`** | Python 3.11 · FastAPI · SQLAlchemy 2 · Alembic. SQLite by default (zero external services), Postgres in production. Pluggable providers (Twilio / Vapi / mocks). |
| **`frontend/`** | Swift · SwiftUI, built as a SwiftPM library + thin app target. iOS 17+, with **Liquid Glass** styling on iOS 26. |

The frontend talks to the backend only through a small set of REST endpoints
(`/v1/...`); every backend secret and provider call stays server-side.

---

## Running it locally

**Backend** (mock providers — no Twilio/Vapi account needed):

```bash
cd backend
make setup     # create venv + install + migrate + seed
make api       # serve on http://127.0.0.1:8000
make worker    # in another terminal: dispatch scheduled requests
```

In mock mode the OTP code is always `123456` and new accounts start with a few
free credits. See [`backend/README.md`](backend/README.md) for real Twilio/Vapi
setup and the `make api-lan` target for testing on a physical device.

**Frontend** (iOS):

```bash
cd frontend
open App/BelievableCall.xcodeproj   # run on a simulator or device from Xcode
```

For a device build, point the app at your machine via the `BC_BACKEND_URL`
scheme environment variable. See [`frontend/README.md`](frontend/README.md).

---

## Documentation

- [`DOCUMENTATION.md`](DOCUMENTATION.md) — full developer's guide: architecture,
  request lifecycle, how every piece connects, with code references.
- [`backend/README.md`](backend/README.md) — backend setup, providers, testing.
- [`frontend/README.md`](frontend/README.md) — iOS app structure and testing.

---

## Responsible use

AlibiMe is designed for one purpose: giving **you** a graceful, believable way
out of a situation, delivered only to **your own** verified number. It is not a
tool for deceiving or contacting other people, and the architecture enforces
that — the destination is always the authenticated user's own phone.

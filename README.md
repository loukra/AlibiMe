# AlibiMe

**Your personal alibi — a believable call or text, on your terms.**

AlibiMe is an alibi tool for everyone. It sends a realistic phone call or SMS to
*your own verified number*, on demand or on a timer, so you always have a
credible reason, a story to back up, or a way out — whatever your situation. You
pick a scenario, choose call or text, set the timing, and your phone rings or
buzzes right on cue, sounding and reading like the real thing.

> The internal Swift module and original codename is **BelievableCall**; the
> shipping product is **AlibiMe**.

---

## What people use it for

Everyone has a moment where a perfectly-timed call or text would make life
easier. A few:

- **Slip out of a bad date** — your "roommate has a problem at home" and you
  genuinely have to go.
- **Escape a dragging meeting or hangout** — "urgent work issue," handled.
- **Protect your private life** — carve out time for yourself for a day or two
  weeks without owing anyone an explanation.
- **Back up a story with family** — make a new relationship or partner feel real
  to the people around you.
- **Make a new chapter feel established** — a fresh job or move looks settled
  when the right people are checking in on you.
- **Get out of an unsafe or uncomfortable situation** — a believable reason to
  leave, immediately.

One template, your scenario, your timing. It's a tool for everyone.

---

## How it works

The core experience is one tap away:

1. **Pick a template** — a believable situation like *Boss — urgent travel
   assignment*, *Best friend — needs you outside*, or *Roommate — issue at
   home*. Each template is one concept that can run as a **call**, a **text**,
   or **both** — or build your own.
2. **Choose a channel** — call or text, whichever fits the moment.
3. **Choose timing** — now, in 30 seconds, in 5 minutes, or scheduled.
4. **Receive it** — the call/text arrives on your phone, and you take it from
   there.

### The one rule that matters

AlibiMe **only ever delivers to your own verified phone number.** It can't be
pointed at anyone else's phone — the call or text always comes to *you*, as a
prop you present in the moment. That keeps it a personal tool, not a way to
harass, spam, or impersonate someone to a third party's device.

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

AlibiMe delivers only to **your own** verified number — the architecture
enforces it, so the app can never be pointed at someone else's phone to harass,
spam, or impersonate. What you do with your own alibi is up to you; please keep
it legal and don't use it where a real call matters (emergencies, official or
legal obligations).

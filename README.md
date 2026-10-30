# AlibiMe

AlibiMe is an iOS app that calls you when you need a reason to leave. The
caller is an AI voice agent. You choose who it should be, say your best friend
or your roommate, and why they are calling, and the agent phones you and plays
the part in a short, natural conversation. Texts work too and always come from
the same number, so you can save it as "Mom" and the next one looks real.

<p align="center">
  <img src="docs/screenshots/home.png" width="230" alt="Home screen">
  &nbsp;
  <img src="docs/screenshots/save-prompt.png" width="230" alt="Prompt to save the sender as a contact">
  &nbsp;
  <img src="docs/screenshots/contact.png" width="230" alt="Prefilled contact">
</p>

## The AI part

Calls run on [Vapi](https://vapi.ai), which handles speech recognition, the
language model and the voice. The agent itself lives in this repo, in
`backend/app/agent`: its prompt, model, voice and transcriber go to Vapi with
every call, so nothing is configured by hand in a dashboard and every change to
the agent is a code change with tests.

The prompt is written for a private call between people who know each other.
The caller never introduces themselves, since the saved contact already shows
who it is, keeps sentences short, avoids anything that sounds like customer
service, gets their ask across and hangs up. Background noise is off, so it
doesn't sound like an office. For every call the backend fills in who is
calling and why, how urgent it is, the tone, the user's local time, which facts
the caller may mention and which it must not, and roughly how many turns to
take.

`backend/evals` tests the agent. It talks to the same prompt the real calls
use, with a scripted person on the other end who asks who's calling, whether
this is a bot, what exactly happened, or says they're busy. Rule checks catch
service phrases, self-introductions, admitting to be an AI, forbidden topics
and turns that run too long, and an optional LLM judge scores how natural the
call sounds. It runs offline with a mock model in the test suite, or against
OpenAI or Anthropic with a key.

Nothing a user types ever reaches the model. Even custom templates are put
together from fixed options, and the backend composes the wording from approved
building blocks. That rules out prompt injection and means the agent can't be
turned into a tool for calling or misleading someone else. It can only ever
call the number the user verified at sign-up.

<p align="center">
  <img src="docs/screenshots/templates.png" width="230" alt="Template library">
  &nbsp;
  <img src="docs/screenshots/builder.png" width="230" alt="Template builder with fixed options">
</p>

## How it's built

The backend is Python with FastAPI, SQLAlchemy and Alembic, the app is SwiftUI.
Texts and sign-in codes go through Twilio. A worker sends requests when they
are due, and phone numbers are stored encrypted and never logged.

Each persona calls and texts from the same number, so once the user saves it as
a contact, both show up under that name. The Action Button (or Siri, or a
Shortcut) can send a preset alibi without opening the app. Credits are bought
as App Store in-app purchases, and the backend checks Apple's signed
transaction before granting them. New numbers get free credits for one text and
one call, the first purchase comes with a bonus, and accounts can be deleted
from Settings. How the prices were worked out
is in [`docs/pricing.md`](docs/pricing.md).

```mermaid
flowchart LR
    App[iOS app] -->|template, channel, time| API[FastAPI]
    API --> DB[(Database)]
    Worker --> DB
    Worker -->|agent from app/agent| Vapi[Vapi voice agent]
    Worker --> Twilio[Twilio: texts]
    Vapi -->|answered, duration, cost| API
    Twilio -->|delivery status| API
    App -->|signed purchase| API
```

There are 185 backend tests, including the evals, and 120 iOS unit tests.

## Running it locally

```bash
cd backend
make bootstrap   # set up venv, database and seed data
make api         # http://127.0.0.1:8000
make worker      # second terminal
make eval        # agent evals, offline
```

Then open `frontend/App/BelievableCall.xcodeproj` in Xcode and run it on a
simulator. With the mock providers the sign-in code is always `123456`, and
purchases go through a mock store so nothing is charged.
BelievableCall was the working title and is still the name of the Xcode
project.

More detail is in [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) and the
specs in [`docs/specs/`](docs/specs/).

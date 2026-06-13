# BelievableCall — iOS Frontend

A native SwiftUI app that lets a user receive a believable **call** or **text**
on their **own verified number**, by choosing a prebuilt template, a channel,
and timing. Built to `FRONTEND_SPEC.md`, connected to the FastAPI backend in
`../backend`.

## Layout

```
frontend/
├── Package.swift
├── Sources/BelievableCall/
│   ├── App/            # AppModel state machine, DI container, RootView, @main
│   ├── Networking/     # APIClient, DTOs, error model, JSON coding
│   ├── Models/         # product-language models + DTO→model mapping
│   ├── Services/       # typed service protocols + Live* + Mock* impls
│   ├── Storage/        # Keychain session store, token holder, preferences
│   ├── DesignSystem/   # theme tokens, components, platform shims
│   └── Features/       # Auth, Home, Templates, Requests, History, Settings
└── Tests/
    ├── BelievableCallTests/             # unit tests (no network)
    └── BelievableCallIntegrationTests/  # live-backend tests (gated)
```

## Architecture notes

- **Product language vs. backend naming.** The UI says *template*, *call*,
  *text*, *credits*. The backend's wire names (`sms`, `scenario`-era ids, etc.)
  stay at the network boundary in `Networking/` and `Models/Mapping.swift`.
- **The own-number rule.** The request body only ever carries
  `client_request_id`, `template_id`, `channel`, and one of
  `delay_seconds`/`scheduled_at`. There is no destination-number field anywhere
  in the request flow — enforced and unit-tested
  (`testCreateRequestBodyContainsNoDestinationNumber`).
- **One networking owner.** Only `APIClient` touches `URLSession`. Services are
  protocols with `Live*` (real) and `Mock*` (preview/test) implementations.
- **State.** `@Observable` view models, async/await, a small top-level
  `AppModel.Phase` (launching / unauthenticated / authenticated) plus a
  normalized `RequestStatus`, so no screen reinvents backend state.

## Running the tests

The package compiles for iOS (the shipping target) **and** macOS, so the logic,
networking, mapping, and view-model layers run with `swift test` on the host.

This machine's default toolchain is the Command Line Tools, which lack XCTest,
so point the toolchain at full Xcode:

```bash
# Unit tests only (no backend needed):
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  swift test --filter BelievableCallTests
```

### Integration tests against the real backend

These are skipped unless `BC_BACKEND_URL` is set, so plain `swift test` stays
green. To run them, start the backend with mock providers and point the tests at
it:

```bash
# 1) In ../backend, on a throwaway DB with mock providers:
cd ../backend
DATABASE_URL="sqlite+pysqlite:///./fe_test.db" \
OTP_PROVIDER=mock VOICE_PROVIDER=mock MESSAGE_PROVIDER=mock \
  .venv/bin/alembic upgrade head
DATABASE_URL="sqlite+pysqlite:///./fe_test.db" \
OTP_PROVIDER=mock VOICE_PROVIDER=mock MESSAGE_PROVIDER=mock \
  .venv/bin/python -m app.seeds.seed
DATABASE_URL="sqlite+pysqlite:///./fe_test.db" \
OTP_PROVIDER=mock VOICE_PROVIDER=mock MESSAGE_PROVIDER=mock \
  .venv/bin/uvicorn app.main:app --port 8000

# 2) In frontend, run the integration suite (mock OTP code is 123456):
cd ../frontend
BC_BACKEND_URL=http://127.0.0.1:8000 \
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  swift test --filter BelievableCallIntegrationTests
```

The integration suite drives the full login → templates → create → get → cancel
→ history flow, plus the active-request and schedule-window invariants, through
the app's own networking layer.

## Running the app on a device / simulator

Open `Package.swift` in Xcode and run the `BelievableCall` scheme on an iOS
target. Building for iOS requires the iOS platform component
(Xcode → Settings → Components, or `xcodebuild -downloadPlatform iOS`).

The backend base URL defaults to `http://127.0.0.1:8000`. Override it with the
`BC_BACKEND_URL` environment variable in the run scheme for device builds.

## Test coverage summary

- **Unit (64):** auth VM transitions, phone normalization, template selection,
  channel-availability filtering, timing presets, request DTO mapping
  (no-destination invariant), error→copy mapping, session restore/expiry,
  history pagination, settings, date coding, `APIClient` header/decoding/error
  handling via a stub transport.
- **Integration (12):** real backend round-trips for login, wrong-OTP, profile,
  templates, create/get/cancel, SMS, active-request blocking, schedule-window
  rejection, history, unauthorized, entitlements, device registration.

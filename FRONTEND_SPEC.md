# BelievableCall — Frontend Specification

> This is the source of truth for the MVP iOS frontend. The SwiftUI app,
> design system, navigation, local state, API integration, and future polish
> derive from this file.
>
> The backend already exists in the given folder. The frontend must connect to
> that backend implementation as it exists. Do not rebuild, rename, or replace
> the backend. If the backend uses internal names like `scenario` or
> `sos-request`, keep those names inside the networking layer only; the UI may
> still use better product language such as "template", "call", and "text".

---

## Soul

This app should **not** feel like a prank app, a hacker tool, or a clunky admin
panel.

It should feel like a **fast, discreet, trustworthy iPhone app** that helps the
user receive a believable interruption on demand.

The user opens the app, chooses a believable template such as:
- boss needs you for urgent work
- boss needs you abroad for two weeks
- best friend needs you outside
- roommate has an issue at home
- sibling needs a family check-in
- safety check-in

Then the user chooses **call** or **text**, chooses **when**, taps once, and the
app gets out of the way.

The user should never feel that they are "configuring AI". They should feel that
they are selecting a believable prebuilt interruption.

**Core belief:** the frontend wins by being calm, fast, discreet, and obvious to
use with one hand under stress.

---

## The One Load-Bearing Frontend Idea

**The home screen is action-first, not settings-first.**

The primary job of the app is to let the user trigger a believable call or text
in seconds.

That means:
- the user lands directly on a fast action surface after login
- the selected template is always visible
- the available channels are obvious
- the common delays are one tap away
- exact scheduling exists, but does not slow down the common case
- cancellation is always easy to find while a request is still cancelable

The app is not a dashboard product. The app is a **one-action utility** with a
small amount of setup around it.

---

## The Other Load-Bearing Rule

**The frontend never lets the user choose an arbitrary target phone number for a
call or text.**

This rule must be visible throughout the UX:
- phone number entry exists only for login / verification and explicit number
  change
- after verification, the UI always assumes delivery goes to the user's own
  verified primary number
- the request form never asks "who should we call?"
- the user may choose **who appears to be contacting them** as a template, but
  never the actual destination number

This mirrors the backend safety invariant and must not be weakened in the UI.

---

## Scope (MVP)

### In

- **Platform:** native **iOS** app in **SwiftUI**.
- **Backend integration:** connect to the backend that already exists in the
  provided folder.
- **Authentication:** phone-number OTP login / signup.
- **Main channels:**
  - believable **call**
  - believable **text / SMS**
- **Timing modes:**
  - now
  - in 30 seconds
  - in 5 minutes
  - exact time within the next 24 hours
- **Template selection:** choose who is contacting the user and why.
- **Home action flow:** select template, select channel, select timing, send.
- **Pending request screen:** countdown, status, cancel if allowed.
- **History screen:** previous calls/texts with outcome and summary preview.
- **Settings screen:** verified number snapshot, locale, timezone, display name,
  credits summary, help/legal entry points, sign out.
- **APNs registration:** send push token to backend if available.
- **Light local persistence:** session, selected template, last-used channel,
  last-used timing, active request snapshot.
- **SwiftUI previews and mock API client for local UI development only.**

### Out (explicitly, for MVP)

- Android app.
- iPad-specific layout work.
- Watch app.
- Widgets / Live Activities / Dynamic Island.
- Voice cloning controls.
- User-authored prompt builder.
- Free-form story text field.
- In-app text chat with the provider.
- In-app VoIP calling UI.
- Complex social features.
- Multi-account switching.
- Address book import.
- Arbitrary number entry in the request flow.
- Replacing the existing backend.

---

## Product Language

The UI should use **human product language**, not backend jargon.

Preferred user-facing words:
- **Template** instead of `scenario`
- **Call** and **Text** instead of `channel`
- **Send now** / **In 30 seconds** / **In 5 minutes** / **Schedule** instead of
  raw scheduling terminology
- **Your number** / **Verified number** instead of internal phone-record terms
- **Credits** instead of ledger language

Important exception:
- if the existing backend in the folder still uses older API names such as
  `scenario_id` or `/v1/sos-requests`, keep that naming in the networking layer
  only
- do **not** leak those backend names into the visible UI copy

---

## Design Principles

### 1. Discreet, not gimmicky

Avoid anything that makes the app feel fake, pranky, childish, or meme-like.

Do **not** use:
- neon prank-call styling
- comedy illustrations
- loud fake incoming-call graphics as the core brand language
- wink-wink copy like "get out of dates" in every screen

Prefer:
- clean typography
- calm spacing
- muted confidence
- subtle motion
- serious, helpful copy

### 2. Native iPhone feel

The app should feel like a high-quality iOS utility, not a cross-platform clone.

Use:
- SwiftUI navigation and sheets
- SF Symbols
- system typography where possible
- standard iOS controls where they already feel good
- custom styling only where it improves clarity or distinctiveness

### 3. Thumb-first speed

The main home actions must be reachable and understandable with one hand.

The user should be able to:
1. open the app
2. confirm the template
3. tap a timing preset
4. be done

### 4. Calm urgency

Some use cases are socially awkward, some are safety-adjacent, some are just
practical alibis. The app should support all of them without becoming scary.

The emotional tone should be:
- calm
- clear
- reassuring
- not dramatic

### 5. User-facing simplicity, internal rigor

The app must hide backend complexity.

The user should not think about:
- provider setup
- webhook timing
- dispatch state machines
- session internals
- backend naming oddities

They should only see:
- template
- channel
- timing
- request status
- credits

---

## Design System

### Visual direction

The visual style should be **minimal, premium, discreet, and trustworthy**.

Recommended design direction:
- soft neutral backgrounds
- one strong accent color for the primary action
- one success color
- one warning color
- one destructive color for cancel / sign out
- light and dark mode support from day one

Suggested feel:
- background: warm white / soft gray in light mode, charcoal / graphite in dark mode
- cards: slightly elevated with rounded corners
- accent: deep blue, muted green, or similarly calm confident tone
- destructive: system red
- warning: amber

Do not hardcode an over-branded aesthetic before product-market fit.

### Typography

Use Apple system typography first:
- large prominent title on the home screen
- strong section headers
- medium-weight labels for template cards
- monospaced digits for countdown timers if helpful

The typography should communicate seriousness and speed, not novelty.

### Spacing and shape

- use an 8-point spacing rhythm
- use generous tap targets
- use rounded cards and pills
- do not create overly dense list rows

### Motion

Animations should be short and purposeful.

Rules:
- no playful bouncing
- no long hero animations
- keep transition durations roughly in the 150–250ms range
- respect Reduce Motion
- haptics may be used on primary actions, success, and cancel

---

## Information Architecture

Use a simple post-login structure:

### Root tabs

1. **Home**
2. **History**
3. **Settings**

This is enough for MVP.

Template browsing should not be a permanent separate tab. It should be reachable
from the Home screen via a picker sheet or push screen.

### Pre-auth flow

Before the tab bar exists, use a focused onboarding/auth flow:
1. welcome / value proposition
2. phone number entry
3. OTP confirmation
4. minimal profile confirmation
5. permission education if needed
6. land on Home

---

## Screen-by-Screen Specification

### 1. Launch / Session Restore

Responsibilities:
- load local session token from Keychain
- attempt session restore via backend if needed
- load active request snapshot from local storage
- determine whether to show auth flow or main app

Behavior:
- keep launch experience simple and fast
- do not show a long branded splash
- if a session exists but the network is slow, show a lightweight loading state

### 2. Welcome Screen

Purpose:
- explain the app in one clear paragraph
- communicate the core value without sounding shady

Suggested framing:
- receive a believable call or text to your own number
- choose a template and timing
- use it for social, work, family, logistics, or safety reasons

Avoid copy like:
- fake your friends
- prank anyone
- get away with lying

### 3. Phone Number Entry

Purpose:
- login / signup with the user's own number

Requirements:
- country picker if needed
- phone formatting assistance
- clear statement that the app only contacts the user's verified number
- CTA to request OTP

### 4. OTP Confirmation

Requirements:
- 6-digit code entry
- resend timer
- editable phone number link
- clear loading and error states

### 5. Minimal Profile Setup

Only collect what is truly needed in MVP:
- display name (optional)
- locale
- timezone

Do not overload onboarding with preferences that are not essential.

### 6. Home Screen

This is the most important screen in the product.

Structure from top to bottom:
- greeting / small header
- verified-number status card
- currently selected template card
- channel selector (`Call` / `Text`), filtered by template support
- timing presets:
  - now
  - 30 sec
  - 5 min
  - schedule
- large primary CTA
- credits summary
- active request card if one exists

Rules:
- the screen should work even if the user never opens any other part of the app
- the primary CTA text should adapt to the chosen channel and timing
  - `Call me now`
  - `Text me in 30 seconds`
  - `Schedule call`
- the user should not have to drill into a separate form for the common case

### 7. Template Picker

This is where the user chooses who is contacting them and why.

Display templates as well-described cards grouped by category:
- Work
- Family
- Social
- Logistics
- Safety

Each card should show:
- caller label
- reason label / short explanation
- optional preview line
- supported channels (`Call`, `Text`, or both)

Example cards:
- **Boss** — urgent work issue
- **Boss** — work trip abroad
- **Best friend** — needs you outside
- **Roommate** — issue at home
- **Sibling** — family check-in

Do not let the user edit the underlying story freely in MVP.

### 8. Schedule Sheet

Use a focused sheet for exact-time scheduling.

Requirements:
- native date/time picker
- enforce backend window of the next 24 hours
- show selected timezone in readable form
- clear confirmation CTA

### 9. Pending Request / Status View

If a request has been accepted, the UI should show a clear status card or detail
screen with:
- selected template
- channel
- execute time
- current status
- countdown if still scheduled
- cancel button if still cancelable
- summary of what will happen

Examples:
- `Call scheduled in 00:27`
- `Text queued`
- `Call in progress`
- `Completed`
- `Canceled`
- `Failed`

The user should always know whether the app has actually accepted the request.

### 10. History Screen

A simple chronological list is enough for MVP.

Each row should show:
- template label
- channel icon
- requested time
- final status
- optional short summary preview

Support:
- empty state
- pull to refresh
- pagination if backend already supports it

### 11. Settings Screen

Include:
- verified primary phone number snapshot
- display name
- locale
- timezone
- credits / plan summary
- sign out
- help / legal links
- app version

Optional in MVP if backend supports it cleanly:
- change primary number

If number change is not finished end to end, do not ship half of it in the UI.

---

## Main Interaction Model

### Fast path

The intended default path is:
1. open app
2. see current template
3. choose call or text
4. tap now / 30 sec / 5 min / schedule
5. confirm if needed
6. leave app

### Confirmation strategy

Do not add a heavy confirmation modal for every action.

Recommended:
- direct action for `now`, `30 sec`, and `5 min`
- one lightweight confirmation only if needed for the very first use or when
  the user has low credits left
- explicit confirmation inside the exact-time schedule sheet

### Active request rule

If the backend reports an active pending/live request, the home screen should
switch into a status-first state rather than pretending the user can create a
second parallel request.

---

## Backend Integration Rules

### The backend in the given folder is authoritative

The frontend must connect to the backend that already exists in the provided
folder.

This means:
- do not invent a parallel backend
- do not change route names from the frontend side
- do not duplicate business rules in Swift unless needed for UX hints
- backend responses are the source of truth for request state, cancelability,
  entitlements, and verified-number status

### API client requirements

Use a dedicated typed networking layer.

Recommended structure:
- `APIClient`
- `AuthService`
- `TemplateService`
- `RequestService`
- `HistoryService`
- `SettingsService`

The rest of the app should never call `URLSession` directly.

### Conceptual endpoint groups

The frontend should expect an API shape equivalent to:
- auth start / confirm / logout
- current user profile
- current device registration
- templates or scenarios catalog
- request create / get / cancel
- history
- entitlements

If the backend folder exposes exact endpoints such as:
- `POST /v1/auth/phone/start`
- `POST /v1/auth/phone/confirm`
- `GET /v1/me`
- `PATCH /v1/me`
- `PUT /v1/devices/current`
- `GET /v1/scenarios` or `GET /v1/call-templates`
- `POST /v1/sos-requests` or `POST /v1/call-requests`
- `GET /v1/call-history`
- `GET /v1/entitlements`

then the frontend must integrate with the implementation that is actually
present, not the prettier naming in this document.

### Channel support

If the backend already exposes channel support per template, the UI must filter
and render accordingly.

If the backend is temporarily behind on SMS support, the UI should:
- gracefully hide unsupported channels
- not hard-fail the app
- keep the code structure ready for both `call` and `text`

---

## Frontend Architecture

### Platform and language

- **Swift 5.10+**
- **SwiftUI**
- iOS 17+ recommended unless the project already targets lower

### State management

Keep the architecture simple and native.

Recommended approach:
- feature-oriented modules
- `@Observable` / observable view models
- dependency injection through environment or lightweight container
- async/await for networking

Avoid unnecessary complexity:
- no Redux-style global reducer system unless already present
- no Combine-heavy architecture unless it clearly simplifies an existing area
- no over-abstracted coordinators everywhere

### Suggested feature modules

- `AppCore`
- `AuthFeature`
- `HomeFeature`
- `TemplatesFeature`
- `RequestsFeature`
- `HistoryFeature`
- `SettingsFeature`
- `Networking`
- `DesignSystem`
- `Storage`

### Local storage

Use local storage only for light client concerns:
- session token in Keychain
- small preferences in `UserDefaults`
- active request snapshot if needed for fast restore
- cached template catalog if helpful

The backend remains the source of truth for durable business state.

---

## App State Model

The app should think in a small number of top-level states:

1. **launching**
2. **unauthenticated**
3. **verifying phone**
4. **authenticated, ready**
5. **authenticated, active request present**
6. **session expired**
7. **fatal configuration error**

Within authenticated mode, the home flow should also model request creation as:
- idle
- submitting
- scheduled
- active
- completed
- canceled
- failed

Do not let every screen invent its own separate interpretation of backend state.

---

## Data Models in the Frontend

Create app-facing models that map backend DTOs into UI language.

Recommended models:
- `UserProfile`
- `VerifiedPhoneSummary`
- `TemplateSummary`
- `ChannelOption`
- `TimingOption`
- `RequestSummary`
- `RequestStatus`
- `HistoryItem`
- `EntitlementSummary`
- `APIErrorEnvelope`

Important mapping note:
- if backend says `scenario`, map it to `TemplateSummary` in the app layer
- if backend says `sosRequest`, map it to `RequestSummary`
- keep raw DTOs at the network boundary

---

## App Lifecycle and Background Behavior

This app does **not** need to stay open for the call or text to happen.

Rules:
- once the backend accepts the request, the delivery is server-driven
- the app may be backgrounded or closed afterward
- on foreground/resume, refresh the current active request if one exists
- persist the latest known active request locally for fast UI restore

Do not depend on:
- long-running background execution
- custom VoIP infrastructure in the app
- the app staying open until the call arrives

### Push token handling

If APNs token registration is implemented:
- register the token after login or when it changes
- send it to the backend using the existing device endpoint
- token registration is useful, but not load-bearing for the actual call/text

---

## Error Handling and Recovery

The app must handle backend errors calmly and specifically.

Important cases:
- invalid phone number
- wrong OTP
- session expired
- verified number missing
- active request already exists
- insufficient credits
- invalid schedule window
- request not cancelable
- provider temporarily unavailable
- generic network failure

Rules:
- show clear human messages
- avoid raw backend codes in UI
- preserve enough detail for debugging in developer logs
- never lose the selected template/channel/timing after a recoverable failure

---

## Copy Guidelines

The copy should sound:
- clear
- neutral
- credible
- calm

Avoid copy that sounds:
- juvenile
- manipulative
- jokey
- criminal
- overly dramatic

Good examples:
- `Choose a template`
- `Call your verified number`
- `Text scheduled`
- `Cancel request`
- `Your verified number`

Bad examples:
- `Fake your way out`
- `Lie better`
- `Prank mode`
- `Escape this date now`

---

## Accessibility

Accessibility is part of the MVP, not polish for later.

Requirements:
- Dynamic Type support
- VoiceOver labels for all important actions
- sufficient color contrast
- large tap targets
- Reduce Motion support
- do not rely on color alone for status
- countdown and status should be understandable to assistive technology

---

## Testing Strategy

### Unit tests

Must cover:
- auth view model state transitions
- template selection logic
- channel availability filtering
- timing preset selection
- request creation mapping from UI model to backend request DTO
- error-to-user-message mapping
- session restore behavior

### UI tests

Must cover:
- first login flow
- OTP confirmation flow
- home fast path for `Call now`
- home fast path for `Text in 30 seconds`
- schedule flow
- active request cancel flow
- session-expired recovery

### Preview / mock data

SwiftUI previews should use mock services and local fixtures so screens can be
built and reviewed without live backend access.

Important:
- previews and mock services are for UI development only
- the actual app runtime must connect to the backend in the given folder

---

## Repository Layout (target)

Assuming the backend already exists in the repository, the frontend should live
next to it, not inside it.

Example target shape:

```text
repo/
├── backend/                  ← already exists; connect to this backend
├── BACKEND_SPEC.md          ← already exists
└── ios/
    ├── FRONTEND_SPEC.md     ← this file
    ├── BelievableCall.xcodeproj
    └── BelievableCall/
        ├── App/
        ├── Features/
        ├── Networking/
        ├── DesignSystem/
        ├── Models/
        ├── Storage/
        ├── Resources/
        └── Tests/
```

If the actual backend folder uses a different name, keep the same principle:
**frontend is a separate iOS app that connects to the existing backend folder as
its server dependency.**

---

## Decisions Locked

| Area | Decision |
|------|----------|
| Platform | iOS first, native SwiftUI |
| Primary flow | Home screen is action-first |
| Backend integration | Connect to the existing backend in the given folder |
| Phone number rule | No arbitrary destination number in request flow |
| Channels | Call and text in UI structure |
| Template model | User selects prebuilt templates, not free-form stories |
| Navigation | Home, History, Settings |
| State management | Simple native SwiftUI architecture |
| Storage | Keychain + lightweight local persistence |
| App lifecycle | Server-driven delivery; app may be closed after scheduling |
| Design tone | Discreet, trustworthy, not prank-like |
| Copy tone | Calm, neutral, credible |

---

## Decisions Deferred

- Final product name and branding polish
- Widgets / Live Activities
- Push-driven status updates beyond basic device registration
- Full in-app purchase UI if backend billing is still evolving
- Advanced history filters
- Exact visual identity beyond a clean MVP system
- iPad layout adaptations
- Android client

---

## Non-Negotiable Acceptance Criteria

The frontend is not done unless all of the following are true:

- the app can authenticate a user by phone OTP
- the app clearly communicates that delivery goes to the user's own verified number
- the home screen can create a request in a few taps
- the user can choose a template, channel, and timing
- the UI never asks for an arbitrary destination number in the request flow
- the app connects to the backend already present in the given folder
- the app can show active request state and cancel when allowed
- the app can show history and credits summary
- the app handles session expiry and common backend errors gracefully
- the app feels like a polished iOS utility, not a prank app

---

## Final Reminder

Optimize for a frontend that is:
- fast to understand
- fast to use
- easy to maintain
- directly connected to the backend that already exists
- product-focused in language
- calm and believable in design

If forced to choose between "more configurable" and "faster to use", choose
**faster to use**.

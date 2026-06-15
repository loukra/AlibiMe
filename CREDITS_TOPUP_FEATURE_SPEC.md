# BelievableCall — Add Credits Feature Specification

> This file defines one additive MVP feature: letting the user add credits from
> the app.
>
> It extends the existing backend and frontend that already exist in the given
> folder. Do not redesign billing from scratch. Reuse the current plans,
> entitlements, and credit-ledger architecture where possible.
>
> For the current development phase, credit packages are intentionally **free to
> claim**. Later, the same feature must be able to switch to real paid purchase
> flows without changing the user-facing structure of the screen.

---

## Soul

This feature is **not** a hidden admin cheat and **not** a one-off debug button.

It is the first real user-facing credits flow.

The user should be able to:
- see their current plan tier
- tap **Add Credits** directly below that plan tier
- get a bottom sheet that slides up from the bottom
- choose from a few predefined credit packages
- confirm the selection
- see their credit balance update immediately

For now, all packages are free in development mode.
Later, those same packages will become paid.

**Core belief:** the UI and data model should already look like a real product
feature now, even if the current fulfillment path is free.

---

## The One Load-Bearing Idea

**Credit packages are catalog-driven and backend-controlled.**

The frontend must not hardcode arbitrary package amounts as the source of truth.
It may have local preview mocks for SwiftUI previews, but the real app must load
available credit packages from the backend.

That means:
- the backend decides which packages are active
- the backend decides how many credits each package grants
- the backend decides whether a package is currently `free_dev` or `paid`
- the backend remains the source of truth for the resulting credit balance

The app only presents the catalog and triggers acquisition.

---

## The Second Load-Bearing Idea

**The bottom-sheet flow stays the same when the feature becomes paid later.**

The user-facing structure should not need to change when StoreKit / App Store
billing is added later.

Now:
- user selects a package
- taps confirm
- backend grants credits for free

Later:
- user selects the exact same package
- taps confirm
- app starts StoreKit purchase flow
- backend validates and grants credits

The package ids, API surface, ledger flow, and success states should remain as
stable as possible.

---

## Scope (for this feature)

### In

- **Add Credits** button directly below the visible **Plan tier** section.
- Button opens a **bottom sheet** / bottom drawer from the bottom.
- Bottom sheet shows selectable credit packages.
- Packages are loaded from backend.
- Current phase: all packages are claimable for free.
- Selecting a package grants credits and updates the visible balance.
- Backend records every grant in the credit ledger.
- Feature is architected so real paid purchase can be added later.
- Existing backend in the given folder remains authoritative.
- Existing frontend in the given folder remains the app shell this feature is
  added into.

### Out

- Real StoreKit / App Store purchase flow in this feature pass.
- Google Play billing.
- Promo code redemption.
- Subscription upgrades/downgrades.
- Credit transfer between users.
- Refund UI.
- Full purchase history screen.
- Complex accounting UI.

---

## Product Position

Credits are the consumable value layer of the product.

For MVP, this feature should feel simple:
- you have a plan tier
- you have available credits
- if you need more, you tap **Add Credits**

The user should never need to understand internal billing architecture.

---

## Frontend UX

## Placement

On the screen where the current **Plan tier** is shown:
- keep the existing plan tier card or section
- place a prominent **Add Credits** button directly **under** it
- this button should belong visually to the billing/credits area, not be mixed
  into generic settings rows

If there is already a credits summary on the settings/profile screen, the order
should be:
1. plan tier
2. add credits button
3. credit balance summary / explanation
4. rest of settings content

---

## Add Credits Button

### Label

Use:
- **Add Credits**

Avoid:
- Buy Credits (for now, because the current phase is free)
- Top Up Wallet
- Developer Credits
- Admin Add

### Visual treatment

The button should fit the existing quiet-premium design language:
- same rounded shape family as the rest of the app
- visually important but not aggressive
- likely a full-width button or a prominent card-style CTA
- placed close enough to plan tier that the relationship is obvious

---

## Bottom Sheet

### Presentation

Tapping **Add Credits** opens a bottom sheet that slides up from the bottom.

The sheet should feel native to iOS:
- drag handle at top
- rounded top corners
- dimmed background behind it
- dismissible by swipe down or close action
- smooth spring/fade motion, not flashy

### Sheet content

Top:
- title: **Add Credits**
- optional subtitle: **Choose a package**

Middle:
- list or grid of credit package cards

Bottom:
- primary action button for selected package
- small helper copy if needed

### Suggested copy for current dev phase

Title:
- **Add Credits**

Subtitle:
- **Choose a package**

Helper text:
- **For now, credit packages are free in this build.**

This copy should be controlled by backend/package metadata or build config so it
can be removed later without redesigning the feature.

---

## Credit Package Cards

Each package card should show:
- package title (for example `5 Credits`)
- number of credits granted
- small badge such as `Free for now`
- optional short description like `Good for a few quick actions`

### Example packages for now

- 5 credits
- 15 credits
- 30 credits
- 60 credits

The backend remains the source of truth. These are example seed values, not a
hardcoded frontend contract.

### Selection behavior

- one package selectable at a time
- selected package gets clear visual state
- primary button updates to reflect the selected package

Example primary button labels:
- **Add 5 Credits**
- **Add 15 Credits**

---

## Success Flow

After a successful claim:
- dismiss the bottom sheet
- refresh entitlements / credit balance from backend
- show a lightweight success state

Good success options:
- inline balance update plus subtle toast/banner
- or inline success message in the credits section

Example copy:
- **15 credits added**
- **Your balance has been updated**

The balance should feel immediate and trustworthy.

---

## Failure Flow

Important errors:
- session expired
- package no longer active
- package id invalid
- duplicate submission
- backend temporarily unavailable
- rate limited

UI rules:
- keep the sheet open on recoverable failure
- preserve current selection
- show a short human-readable error
- do not silently fail

---

## Backend Architecture

## Reuse Existing Credit System

Do **not** build a parallel wallet system.

This feature should reuse the existing backend architecture already defined in
`BACKEND_SPEC.md`:
- `plans`
- `entitlements`
- `credit_ledger`
- `GET /v1/entitlements`

This feature adds a clean package-catalog and package-acquisition flow on top of
that.

---

## Backend Source of Truth

The backend should own:
- which credit packages exist
- package ids / codes
- number of credits granted
- whether the package is currently free or paid
- whether the package is active
- final credit grant and ledger entry

The frontend must never self-award credits.

---

## Recommended Model Shape

### Reuse `plans` for credit packs

If the existing `plans` table already stores one-time packs such as:
- `credits_5`
- `credits_15`

then keep using that table.

Do **not** create a separate package catalog table unless the current `plans`
model is clearly insufficient.

Recommended meaning:
- `plans.kind = one_time` represents a credit package
- `plans.included_call_credits` is the number of credits granted

### Additive fields if needed

If the current backend needs display/fulfillment metadata, add fields such as:
- `display_name`
- `sort_order`
- `badge_text`
- `fulfillment_mode` (`free_dev | app_store_iap`)
- `price_minor` (nullable for now)
- `currency_code` (nullable for now)
- `active`

These fields may live directly on `plans` or in a small metadata table, but the
concept should remain simple.

---

## New Backend Entity

### CreditPackageClaims

Add a record of each claim / purchase intent.

Fields:
- `id` (UUID)
- `user_id`
- `plan_id`
- `plan_code`
- `credits_granted`
- `fulfillment_mode` (`free_dev | app_store_iap`)
- `status` (`pending | granted | failed | canceled`)
- `client_request_id`
- `store_transaction_id` (nullable for future)
- `granted_at` (nullable until success)
- `failure_reason` (nullable)
- `created_at`
- `updated_at`

Why this exists:
- creates an audit trail separate from the ledger
- gives a stable place for future purchase validation
- prevents duplicate grants from repeated taps
- keeps free-dev and paid flows on the same conceptual path

---

## Credit Ledger Behavior

On successful free claim in the current phase:
- create a `credit_package_claims` row
- grant credits through the normal ledger path
- append a `credit_ledger` entry with:
  - `entry_type = grant`
  - `reference_type = purchase`
  - `reference_id = credit_package_claims.id`
- update balance snapshot if the backend stores one
- mark claim as `granted`

Do not bypass the ledger just because the package is free right now.

---

## API Contract

Base path stays `/v1`.

### `GET /v1/credit-packages`

Returns all active packages that should be shown in the bottom sheet.

Response example:

```json
{
  "packages": [
    {
      "code": "credits_5",
      "display_name": "5 Credits",
      "credits": 5,
      "fulfillment_mode": "free_dev",
      "price_label": "Free for now",
      "badge_text": "Free",
      "active": true,
      "sort_order": 10
    },
    {
      "code": "credits_15",
      "display_name": "15 Credits",
      "credits": 15,
      "fulfillment_mode": "free_dev",
      "price_label": "Free for now",
      "badge_text": "Free",
      "active": true,
      "sort_order": 20
    }
  ]
}
```

Rules:
- only active packages returned
- sorted for direct UI display
- frontend does not invent or reorder critical package meaning

### `POST /v1/credit-packages/{code}/acquire`

Acquires the selected package.

Request example for current free-dev phase:

```json
{
  "client_request_id": "uuid"
}
```

Response example:

```json
{
  "claim_id": "uuid",
  "status": "granted",
  "granted_credits": 15,
  "credits_available": 27,
  "plan_code": "credits_15"
}
```

Rules:
- authenticated endpoint
- idempotent on `client_request_id`
- backend validates package is active and acquirable
- frontend must refresh `GET /v1/entitlements` after success unless the
  response already includes the exact data it needs

### Existing endpoint reused

#### `GET /v1/entitlements`

After success, frontend refreshes entitlements/credits from this existing
endpoint so the visible balance and tier stay in sync with backend truth.

---

## Fulfillment Modes

## Current mode: `free_dev`

In the current development phase:
- packages appear in the UI as normal selectable packages
- acquiring a package grants credits immediately
- no StoreKit / App Store checkout happens
- free behavior is intentional and explicit

This mode should be controlled by backend config or package metadata, not by the
frontend assuming everything is free forever.

### Safety note

`free_dev` must be easy to disable before a public paid release.

---

## Future mode: `app_store_iap`

Later, the same package can switch to paid mode.

At that point:
- `GET /v1/credit-packages` returns packages with paid metadata
- user still sees the same bottom sheet and the same packages
- frontend starts StoreKit flow for the selected package
- backend verifies and grants credits through the same claim + ledger path

The acquisition architecture should already anticipate:
- store product identifiers
- transaction ids
- verification result
- idempotent grant after transaction completion

---

## Frontend State Rules

The frontend should manage a small, explicit state machine for the sheet:

- `idle`
- `loading_packages`
- `ready`
- `submitting`
- `success`
- `failure`

Rules:
- disable repeated submission while `submitting`
- keep selection stable while the sheet is open
- if package fetch fails, show retry state in the sheet
- if acquisition succeeds, dismiss cleanly and refresh outer screen data

---

## Suggested View Model Shape

The exact implementation is flexible, but the feature should conceptually have:

- `CreditPackagesViewModel`
  - fetch packages
  - track selected package
  - submit acquisition
  - expose loading/error/success states

- `CreditsSummaryViewModel` or reuse existing profile/settings view model
  - load entitlements
  - refresh after package acquisition

Do not spread package logic across unrelated settings rows.

---

## Copy Guidelines

Current phase copy should be straightforward.

Good:
- **Add Credits**
- **Choose a package**
- **Free for now**
- **15 credits added**
- **Your balance has been updated**

Avoid:
- fake money language
- internal developer jargon
- technical billing language
- temporary copy that leaks implementation details

Avoid labels like:
- `debug credits`
- `grant package`
- `wallet mutation`

---

## Design Notes

This feature should match the app's quiet premium design direction.

### Button under Plan tier

The button should feel connected to the plan card but still actionable.
Possible treatments:
- full-width rounded button directly below the plan card
- card-style secondary CTA with subtle icon

### Bottom sheet design

Recommended visual style:
- soft frosted / elevated surface
- rounded corners
- clear package card selection states
- calm typography
- one primary confirm button

The sheet should feel like a natural part of the app, not an external payment
modal.

---

## Edge Cases

### No packages returned

If backend returns no active packages:
- show empty state in the sheet
- do not crash
- allow dismissal

Example copy:
- **No credit packages are available right now.**

### User closes the sheet

Closing the sheet must do nothing destructive.
No partial grant. No state leak.

### Double taps

Repeated taps on confirm must not grant credits twice.
Use backend idempotency and disable the button while submitting.

### Stale balance on outer screen

The outer screen should refresh after success.
Do not assume local optimistic math is the final truth.

---

## Seed Recommendation for Development

Start with four active packages:
- `credits_5`
- `credits_15`
- `credits_30`
- `credits_60`

All with:
- `kind = one_time`
- `fulfillment_mode = free_dev`
- `active = true`

This is enough to exercise:
- catalog loading
- bottom sheet selection
- ledger grant flow
- UI balance refresh
- future-proof package ids

---

## Implementation Guidance

### Backend

- reuse existing plans + entitlements + credit ledger
- add package-list endpoint
- add acquire endpoint
- add claim/audit model
- keep idempotency strict
- keep backend authoritative for final balance

### Frontend

- add **Add Credits** button under Plan tier
- present bottom sheet
- fetch packages from backend
- submit selected package
- refresh entitlements on success
- keep visual style aligned with existing design direction

---

## Locked Decisions

| Area | Decision |
|------|----------|
| Trigger location | `Add Credits` button directly under Plan tier |
| Presentation | Bottom sheet sliding up from bottom |
| Package source of truth | Backend |
| Current fulfillment | Free developer-mode grant |
| Future fulfillment | Paid store purchase using same package model |
| Credit source of truth | Backend ledger / entitlements |
| Hardcoding package catalog in frontend | No |
| Real StoreKit in this pass | Out |

---

## Summary

This feature should already behave like a real product feature, not like a
throwaway debug tool.

The user experience is simple:
- tap **Add Credits**
- pick a package
- confirm
- see the balance update

Under the hood, the architecture should already be on the correct path:
- backend-owned package catalog
- claim records
- ledger-based credit grants
- easy future switch from `free_dev` to real paid purchase

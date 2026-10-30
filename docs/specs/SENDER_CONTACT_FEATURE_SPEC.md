# BelievableCall — Sender Identity + Save Contact Feature Specification

> This file defines one additive MVP feature: stable sender identity for outbound
> **SMS** plus an optional **Save Contact** flow on iOS.
>
> It extends the existing backend and frontend that already exist in the given
> folder. Do not rebuild the product architecture from scratch. Implement this
> feature on top of the current backend and SwiftUI app.
>
> This feature is **Twilio-first for SMS**, but it must be designed so the same
> sender-identity system can later be reused by **Vapi for calls**.

---

## Soul

This feature is **not** a prank feature and **not** an impersonation engine.

Its purpose is continuity.

If the user receives a text from a sender persona such as **Boss**, that sender
should stay consistent over time. The user may then choose to save that sender
as a contact on their own device so future texts from that same sender feel
familiar and coherent.

The app stays user-controlled:
- the app never silently creates contacts
- the app never chooses a real person from the address book
- the app never asks the user to type in a fake sender number
- the user decides whether to save a contact
- the same sender number should continue to be used even if the user skips
  contact creation

**Core belief:** sender continuity must come from the backend's stable binding,
not from whether the user saved a contact.

---

## The One Load-Bearing Idea

**A stable sender identity is allocated by the backend and reused later.**

This feature does **not** work by asking iOS Contacts which phone number to use.
It works by the backend assigning a sender line once and keeping that assignment
stable for future outbound messages from the same persona.

For SMS in MVP:
- when a user first sends a template from a sender persona such as `boss`
- the backend allocates a sender line for that user + sender persona + channel
- later sends from that same sender persona reuse the same sender line
- this remains true whether or not the user ever saves a contact

This makes the system reliable, testable, and later reusable for voice.

---

## The Second Load-Bearing Idea

**Contact creation is optional, explicit, and fully user-confirmed.**

The app may suggest saving the sender as a contact after a successful schedule
or send action, but:
- the app must not auto-create a contact
- the feature must still work if the user dismisses the sheet
- the sender binding must remain intact if no contact is created
- the app must not require Contacts permission to send or schedule messages

The contact is a user convenience layer on top of sender continuity.
It is not the source of truth.

---

## Important Reality with One Twilio Number

With only **one active Twilio SMS number**, this feature can only support **one
coherent saved sender identity at a time**.

Why:
- one phone number can only appear as one saved contact identity on the user's
  phone
- if the same number is used for both **Boss** and **Roommate**, the saved
  contact will conflict

Therefore:
- the architecture must support multiple sender lines
- the first implementation may still work with one Twilio number
- but the full product value of persona-based saved contacts only appears once
  you have **multiple SMS-capable sender numbers** available in the pool

This is a product constraint, not a coding problem.

---

## Scope (for this feature)

### In

- Stable sender identity for **SMS**.
- Twilio as the only real provider implementation for this feature now.
- Backend-managed sender-line allocation and sticky reuse.
- Sender identity keyed by **sender persona**, not by a raw template id.
- Optional iOS **Save Contact** prompt after a successful SMS schedule/send.
- Prefilled contact name from template persona label such as **Boss**.
- Contact creation via standard iOS contact UI.
- Local tracking on device of whether a contact was created, dismissed, or not
  attempted.
- No change to the own-number-only delivery invariant.
- Data model designed so Vapi calls can later reuse the same sender-binding
  system.

### Out

- Automatic contact creation.
- Background address-book modification without user interaction.
- Importing the user's contacts.
- Letting the user manually choose or type the sender number.
- Real Vapi call support in this feature pass.
- Contact sync across multiple devices.
- Editing existing contacts automatically after number changes.
- A separate persona editor for users.

---

## Product Rules

1. **The user never selects the sender number.**
   The backend resolves it.

2. **Sender continuity is persona-based.**
   Templates with the same sender persona should reuse the same sender binding
   for that user and channel where possible.

3. **Contact creation is optional.**
   The user may skip it without losing sender continuity.

4. **The app must work with Contacts permission denied.**
   SMS scheduling and delivery still function normally.

5. **The app must not aggressively request Contacts access at app startup.**
   Contacts access is requested only in context when the user chooses to save a
   sender as a contact.

6. **Template labels should be role-based, not tied to a real third party.**
   Examples: `Boss`, `Coworker`, `Roommate`, `Sibling`, `Work Desk`.

7. **This is a continuity feature, not an impersonation feature.**
   Do not build UI copy that frames this as tricking other people.

---

## Terminology

### Sender Persona
A product-level identity such as:
- `boss`
- `coworker`
- `best_friend`
- `roommate`
- `sibling`

A sender persona has:
- `sender_persona_key`
- `sender_display_name`
- optional localized display strings

### Sender Line
A service-controlled phone number the product can use as an outbound sender.

For MVP this is a Twilio SMS-capable number.
Later it may also map to a Vapi-capable voice sender.

### Sender Binding
A stable mapping between:
- user
- sender persona
- channel
- sender line

This is the core object that makes future messages come from the same number.

### Contact Link
A local-device state representing whether the user created a contact for a
sender binding.

This is **not** the source of truth for sender assignment.

---

## High-Level User Flow

### First time a user sends an SMS from a persona

1. User selects a template whose sender persona is, for example, `boss`.
2. User schedules or sends the SMS.
3. Backend resolves or allocates a stable sender binding for:
   - user
   - sender persona = `boss`
   - channel = `sms`
4. Backend schedules the SMS through Twilio using the bound sender line.
5. Backend returns sender identity metadata in the API response:
   - `sender_persona_key`
   - `sender_display_name`
   - `sender_phone_e164`
   - `sender_binding_id`
   - `contact_prompt_recommended = true`
6. App shows success UI.
7. App presents a non-blocking follow-up prompt such as:
   - title: `Save this sender as a contact?`
   - body: `Future texts from Boss can come from the same sender. You can save
     this contact now or skip it.`
8. If the user taps save:
   - app requests Contacts access if needed
   - app presents a prefilled contact sheet for a new contact
   - name defaults to `Boss`
   - phone number defaults to the bound sender number
9. If the user cancels or closes the contact sheet:
   - no problem
   - sender binding remains active
   - future messages still use the same sender number

### Later SMS from the same sender persona

1. User picks another template with the same sender persona, for example another
   `boss` reason.
2. Backend looks up the existing sender binding.
3. Backend reuses the same sender line.
4. App may avoid showing the save-contact prompt again if it was already shown
   on this device.

---

## UX Requirements

### Prompt timing

The Save Contact prompt should appear **after** the SMS request is accepted.
It must never block scheduling.

Correct order:
- schedule/send success
- then optional Save Contact suggestion

Wrong order:
- ask for Contacts access before the user even schedules the SMS
- block the send flow on contact creation

### Copy guidance

Preferred copy:
- `Save this sender as a contact?`
- `Future texts from Boss can come from the same sender.`
- `You can save this contact now or skip it.`

Avoid copy like:
- `make it look fake`
- `trick people`
- `create a fake boss`
- `bind an account`

Use **contact**, not **account**.

### If the contact sheet is dismissed

That is a valid outcome.

The UI should:
- dismiss cleanly
- not treat it as an error
- not remove the sender binding
- optionally remember locally that the contact prompt was dismissed

### If Contacts permission is denied

The UI should:
- explain briefly that contact saving is optional
- offer a way to open Settings later
- continue using the same sender number for future SMS

### Entry points to create the contact later

If the user skips the initial prompt, the app may later expose:
- a `Save Contact` action in message history detail
- a `Save Contact` action in template detail
- a `Save Contact` action in a sender detail sheet

Do not repeatedly nag after every send.

---

## Data Model Additions

### Existing Template Model: add sender persona fields

Each SMS-capable template must include:
- `sender_persona_key`
- `sender_display_name`
- `supports_contact_save: bool`

Example:

```json
{
  "id": "boss_travel_assignment_abroad",
  "sender_persona_key": "boss",
  "sender_display_name": "Boss",
  "supports_channels": ["sms", "call"],
  "supports_contact_save": true
}
```

### New table: `sender_lines`

Service-controlled sender inventory.

Fields:
- `id`
- `e164`
- `provider_owner` (`twilio` for now)
- `capabilities` (`sms`, later `call`)
- `twilio_phone_number_sid`
- `twilio_messaging_service_sid`
- `vapi_phone_number_id` nullable for later
- `status` (`active`, `inactive`, `orphaned`)
- `display_label` optional internal label
- `created_at`
- `updated_at`

### New table: `user_sender_bindings`

Stable sender assignment.

Fields:
- `id`
- `user_id`
- `sender_persona_key`
- `channel` (`sms`, later `call`)
- `sender_line_id`
- `status` (`active`, `orphaned`, `released`)
- `first_bound_at`
- `last_used_at`
- `created_from_template_id`
- unique constraint on (`user_id`, `sender_persona_key`, `channel`)

### Existing request / history tables: add sender snapshot

Every outbound SMS request and message attempt should persist a sender snapshot:
- `sender_binding_id`
- `sender_persona_key`
- `sender_display_name_snapshot`
- `sender_phone_e164_snapshot`

This preserves history even if the inventory changes later.

### Frontend local state: `contact_link_state`

This should stay local to the device in MVP.

Fields:
- `sender_binding_id`
- `contact_status` (`unknown`, `created`, `dismissed`, `denied`, `not_now`)
- `ios_contact_identifier` optional
- `last_prompted_at`
- `created_at` optional

Do not send iOS contact identifiers to the backend in MVP.

---

## Backend Behavior

### Source of truth split

- **Twilio** is the source of truth for what sender numbers the company owns.
- **Our backend database** is the source of truth for how those numbers are
  assigned to users and personas.

Twilio owns inventory.
The app owns sender continuity.

### Sender allocation algorithm

On SMS request creation:

1. Resolve template.
2. Read `sender_persona_key`.
3. Look for an active binding in `user_sender_bindings` for:
   - `user_id`
   - `sender_persona_key`
   - `channel = sms`
4. If found, reuse it.
5. If not found:
   - choose an active SMS-capable sender line from `sender_lines`
   - create a new binding
6. Persist binding before creating or scheduling the Twilio message.
7. Return sender identity metadata to the frontend.

### Initial allocation strategy

For MVP, keep allocation simple:
- if only one SMS-capable sender line exists, use it
- if multiple exist later, choose by a deterministic allocator such as:
  - persona default
  - least recently assigned
  - round-robin within eligible pool

### Twilio scheduling rule

When scheduling a message:
- use the Twilio Messaging Service required for scheduled SMS
- when a stable binding exists, send with the bound sender line as the explicit
  sender so the number stays consistent

### Binding lifecycle

#### Active
Normal state. The bound sender line exists and is usable.

#### Orphaned
The bound line was removed or disabled. In this state:
- do not silently delete history
- mark the binding orphaned
- on next send, allocate a replacement line
- create a new snapshot for the new request
- the frontend may later suggest saving or updating the contact again

#### Released
Not used in MVP except for admin cleanup.

### API additions

The exact endpoint names should match the existing backend in the folder.
Do not rename working APIs unless absolutely necessary.

Required response additions on SMS request creation:

```json
{
  "request_id": "...",
  "channel": "sms",
  "status": "scheduled",
  "sender_identity": {
    "sender_binding_id": "...",
    "sender_persona_key": "boss",
    "sender_display_name": "Boss",
    "sender_phone_e164": "+15551234567",
    "contact_prompt_recommended": true
  }
}
```

History/detail APIs should also expose sender snapshot fields for rendering.

---

## Frontend Behavior

### Where this feature lives

This feature is primarily attached to the **SMS success flow**.

It should be implemented in the existing SwiftUI app and must connect to the
existing backend in the given folder.

### Save Contact prompt state

The frontend should decide whether to show the post-success prompt using:
- `sender_identity.contact_prompt_recommended`
- local `contact_link_state`

Simple MVP rule:
- show the prompt the first time a binding is seen on this device
- do not show it again automatically after it was dismissed or created
- allow manual re-entry later from history/template detail

### Contact creation path

When the user taps `Save Contact`:

1. If Contacts authorization is `notDetermined`:
   - show a short explainer screen or alert
   - then trigger the standard iOS permission request in context
2. If authorized or limited in a way that still allows this flow:
   - present a prefilled contact creation sheet
3. If denied:
   - show `Contacts access is optional. You can still use this sender without
     saving a contact.`
   - offer `Open Settings`

### Prefilled contact fields

For MVP:
- given name or organization name = `sender_display_name`
- phone number = `sender_phone_e164`

Do not prefill fake photos, addresses, email, notes, or other personal details.

### If the user saves the contact

Store locally:
- `contact_status = created`
- optional `ios_contact_identifier`
- `created_at`

### If the user dismisses without saving

Store locally:
- `contact_status = dismissed`
- `last_prompted_at`

Do not treat as failure.

### First-launch behavior

Do **not** request Contacts permission on first app launch.

Allowed first-launch behavior:
- a short settings/help note that the app can optionally save senders as
  contacts later if the user wants

Actual permission request must remain in-context.

---

## Twilio-First Implementation

### Twilio assumptions

The feature is implemented only for Twilio SMS now.

The backend should use:
- Twilio Messaging Service for scheduled SMS
- one or more SMS-capable Twilio phone numbers in the sender pool
- the bound sender number as the deterministic sender when a binding exists

### One-number startup mode

If the project currently has only one active Twilio number:
- the feature may still be implemented
- but only one sender identity can be coherent for saved-contact realism
- the product team should treat multiple persona-based contact identities as
  requiring additional sender numbers

### Number inventory sync

MVP can keep this simple:
- manually seed `sender_lines` from known Twilio numbers
- no need for automatic Twilio inventory sync in the first pass

Later, a small admin sync may be added.

---

## Vapi Extension Path (Later)

This feature must be designed so calls can later use the same concept.

### Reuse the same abstractions

Keep these abstractions provider-agnostic:
- `sender_persona_key`
- `sender_lines`
- `user_sender_bindings`
- sender snapshot on requests/history

### Later voice support

When Vapi call support is added later:
- calls may resolve sender identity using the same `sender_persona_key`
- a `call` binding can point to a line with a `vapi_phone_number_id`
- if the same underlying number is available for both SMS and voice, the system
  may bind both channels to the same `sender_line_id`
- if not, `sms` and `call` may have different bindings while still sharing the
  same sender persona label

### Important constraint

Do not hardcode Twilio-only concepts deep into the domain model.
Keep Twilio-specific fields at the infrastructure edge.

---

## Privacy, Safety, and Review Guardrails

- Contact creation must always be user-confirmed.
- Do not auto-save or auto-edit contacts.
- Do not require Contacts access to use the core product.
- Do not use the UI language of pranks, fake identities, or tricking people.
- Do not encourage the use of real third-party names by default.
- Prefer role-based labels such as `Boss`, `Coworker`, `Roommate`, `Work Desk`.
- Do not persist more contact data than needed.
- Keep device contact identifiers on device in MVP.

---

## Edge Cases

### User skips contact creation

Expected and supported.
Same sender binding remains active.

### User denies Contacts access

Expected and supported.
Same sender binding remains active.

### User deletes the saved contact later in the Contacts app

The backend should not care.
Sender continuity still works because it is backend-bound.
The app may offer Save Contact again later if it no longer finds local created
state.

### Bound sender line becomes unavailable

Mark binding orphaned and allocate a replacement on next send.
Do not mutate past history.

### Multiple templates share one sender persona

They should reuse the same binding.
Example:
- `boss_urgent_issue`
- `boss_travel_assignment_abroad`

Both should use the same sender line for that user and `sms` channel.

### User reinstalls the app

Backend binding remains.
Local contact-link state may be lost.
The app may offer Save Contact again on the new install.

---

## MVP Definition of Done

The feature is complete when all of the following are true:

- SMS requests return stable sender identity metadata.
- The backend reuses the same sender line for the same user + sender persona +
  channel.
- The frontend can show a post-success Save Contact prompt.
- The frontend can present a prefilled contact creation flow.
- If the user dismisses or denies permission, future messages still use the same
  sender number.
- The system works with Twilio SMS only.
- The domain model is ready for Vapi call reuse later.
- No part of the core send flow depends on Contacts permission.

---

## Explicitly Not Required in This Pass

- Real Vapi implementation.
- Contact syncing between devices.
- Automatic detection that a matching contact already exists system-wide.
- Editing existing contacts when a binding changes.
- Automatic buying or provisioning of Twilio numbers.
- Admin UI for sender-line pool management.


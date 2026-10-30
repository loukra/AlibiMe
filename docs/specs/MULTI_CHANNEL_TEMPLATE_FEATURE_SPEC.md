# BelievableCall — Unified Multi-Channel Templates Feature Specification

> This file defines one additive feature: the existing template system must
> support both **SMS** and **call** execution under the same logical template.
>
> Vapi already works for calls. SMS already exists as a channel in the product.
> This feature must make both channels use the same template architecture
> without introducing unnecessary parallel systems.
>
> Use the architecture that already exists in the given folder. If there is
> already a template model, template API, Vapi prompt compiler, template list
> view, or template detail flow, extend those pieces instead of creating a new
> disconnected implementation.

---

## Soul

The user should feel like they are choosing **one believable situation**, not
choosing between two unrelated products.

Example:
- **Boss — urgent work abroad** is one template concept
- that template may support **SMS**, **call**, or **both**
- the SMS version and the call version should feel consistent in meaning
- but they should not be forced to use identical text, because a believable SMS
  and a believable call behave differently

The product should have:
- one template library
- one template detail model
- one custom-template system
- one scheduling flow
- channel-specific execution behavior behind the scenes

**Core belief:** one template can have multiple channel variants, but it should
still be one template in the user’s mental model.

---

## The One Load-Bearing Decision

**Use one shared template core with channel-specific configs.**

That means:
- shared template data defines the meaning of the template
- channel config defines how that meaning is executed for `sms` or `call`
- Vapi uses the `call` config
- Twilio SMS uses the `sms` config

Do **not** build:
- a separate SMS template system
- a separate Vapi template system
- duplicate template libraries for each channel
- duplicated UI flows for SMS and call templates

The shared template is the product object.
The channel config is the runtime specialization.

---

## The Second Load-Bearing Rule

**Reuse what already exists. Do not add unnecessary architecture.**

If the current backend already has something like:
- `templates`
- `call_templates`
- `call_template_versions`
- template DTOs
- template list/detail endpoints
- Vapi prompt compilation from template data

then that existing system is the starting point.

Important implementation rule:
- **extend existing template architecture first**
- **do not rename working code just for conceptual purity**
- **do not create new top-level services/tables/endpoints unless the existing
  architecture truly cannot support the feature cleanly**

Example:
- if the codebase already centers on `call_templates`, it is acceptable in MVP
  to keep that table/model and add SMS-capable fields or child config tables,
  instead of forcing a large rename to `templates`
- the user-facing product language can still say **Template** everywhere

The goal is a clean extension, not a rewrite.

---

## Problem This Feature Solves

Today, a template concept can exist in a fragmented way:
- call behavior may live in one place
- SMS behavior may live in another place
- custom templates may become harder to reason about
- frontend may need to special-case channel-specific template models

This feature removes that fragmentation.

After this feature:
- one template can support `call`, `sms`, or both
- a template detail screen can show all supported channel behavior
- custom templates use the same model
- scheduling uses the same template ID and chooses a channel
- Vapi and Twilio both plug into the same template runtime system

---

## Scope

### In

- One logical template model shared across channels
- Channel support flags per template
- Channel-specific config for `call` and `sms`
- Vapi call flow uses the template's `call` config
- SMS flow uses the template's `sms` config
- Template list and detail view show supported channels
- Custom templates use the same shared-template + channel-config approach
- Minimal migrations/extensions to the current backend and frontend
- Reuse existing architecture where possible

### Out

- Rewriting all template code from scratch
- Breaking working Vapi integration unnecessarily
- Separate libraries named `sms_templates` and `call_templates` if not required
- Free-form prompt editing
- Free-form SMS body editing from the client
- Channel-specific duplicate user templates with unrelated IDs
- Aggressive renaming of stable backend APIs just to make naming prettier

---

## Product Position

This is not a channel split.
It is a channel-aware template system.

The user chooses a believable context such as:
- Boss — urgent work issue
- Boss — abroad assignment
- Friend — come outside
- Roommate — issue at home

Then the product may execute that context through:
- a text message
- a call
- both, if supported

The channel changes the output format.
It does not create a separate product object.

---

## Shared Template Model

Each template should have a **shared core** and one or more **channel configs**.

### Shared core fields

These fields represent the meaning of the template and should be shared between
all channels:

- `id`
- `code`
- `display_name`
- `category`
- `caller_role`
- `reason_code`
- `intended_outcome`
- `urgency_level`
- `description`
- `supported_channels`
- `default_channel`
- `active`
- `sort_order`
- ownership fields if custom templates exist (`system` vs `user`)

### SMS config

Fields for believable text execution:

- `channel = sms`
- `enabled`
- `preview_text`
- `body_template` or structured message config
- `follow_up_mode` if applicable
- `sender_continuity_supported`
- any safe SMS-specific runtime options already used in the backend

### Call config

Fields for believable call execution:

- `channel = call`
- `enabled`
- `preview_opening_line`
- `opening_message_template`
- `system_prompt_template` or existing structured call prompt source
- `allowed_follow_up_facts`
- `max_duration_seconds`
- `conversation_style` or equivalent existing bounded call config
- any Vapi-specific mapping fields already used in the backend

Important:
- SMS and call configs are related, but they are not required to use identical
  wording
- the shared core keeps meaning aligned
- the channel config makes execution believable in that channel

---

## Preferred Data-Model Strategy

### Primary rule

**Prefer the smallest clean extension of the current model.**

### If an existing shared template model already exists

If the codebase already has a real shared `templates` concept, use it.
Then add or reuse a child structure such as:
- `template_channel_configs`
- `template_versions` with per-channel fields
- existing JSON config blocks if that is already the established pattern

### If the current codebase is still call-template-centric

If the codebase already uses something like:
- `call_templates`
- `call_template_versions`

and that system is already live and powering Vapi successfully, do **not** rip it
out for this feature.

Instead, minimally extend it, for example by:
- adding `supported_channels`
- adding SMS config alongside the existing call config
- or adding a child channel-config table keyed to the existing template ID

This is acceptable for MVP.
The important thing is one logical template ID and one runtime selection path.

### Strong preference

If a child table is needed, prefer a generic structure like:
- `template_channel_configs`

instead of creating:
- `sms_templates`
- `call_templates_v2`
- `vapi_templates`

because the generic child config structure naturally supports future channels
without duplicating the template system again.

---

## Minimal-Change Implementation Guidance

Use these rules when implementing:

1. If a template list endpoint already exists, extend it.
2. If a template detail endpoint already exists, extend it.
3. If a Vapi prompt compiler already exists, keep using it.
4. If custom templates already exist or are being added, make them use this same
   shared-template model.
5. If existing DTO names are awkward but stable, preserve them internally and map
   to cleaner UI naming at the API/frontend boundary.
6. Do not add a new service layer if the current one can be extended cleanly.
7. Do not introduce duplicate compiled runtime objects for SMS and call unless
   the current architecture already requires them.

This feature is about **unifying behavior**, not multiplying code.

---

## Runtime Behavior

### Template selection

The user selects a template once.

The scheduling request then includes:
- `template_id`
- `channel`
- timing info

The backend resolves:
- the shared template core
- the matching channel config for that template

### Dispatch rules

- if the template does not support the requested channel, reject the request
- if `channel = sms`, compile SMS behavior from the template's SMS config
- if `channel = call`, compile call behavior from the template's call config
- call dispatch continues to use Vapi through the existing integration
- SMS dispatch continues to use the existing SMS provider path

### Vapi rule

The Vapi assistant must be built from the template's **call config**, not from a
separate unrelated prompt system.

That means the Vapi payload should come from the same template the user sees in
UI.

### SMS rule

The SMS payload must be built from the template's **sms config**, not from a
separate unrelated SMS-template library.

---

## Frontend Behavior

The frontend should present templates as a unified product surface.

### Template library

Each template card should show:
- template name
- reason summary
- supported channels (`SMS`, `Call`, or both)
- whether it is built-in or custom if relevant

### Template detail

The detail screen should show:
- the shared template identity
- channel availability
- SMS preview if supported
- Call preview if supported

Do not show two unrelated template objects for the same concept.

### Scheduling flow

The user should be able to:
- select one template
- then select one supported channel
- then choose timing

The UI should not require the user to go into a separate SMS-template picker and
separate call-template picker for the same underlying idea.

---

## Custom Templates

Custom templates must use the exact same conceptual model:
- one custom template
- shared core meaning
- channel support flags
- channel-specific configs

Important:
- custom templates still use safe structured properties only
- no raw prompt editing
- no raw SMS text injection from the user
- backend compiles the final runtime config from allowed fields

If the custom-template feature already exists or is being implemented, this
feature should extend that architecture rather than create a second custom
channel-template system.

---

## Validation Rules

The backend must validate:

- `template_id` exists and is accessible to the user
- requested `channel` is in `supported_channels`
- required channel config exists and is active
- custom-template combinations remain within allowed safe options
- no free text from the client is inserted directly into Vapi system prompts or
  SMS bodies

### Compatibility examples

- a call-only template cannot be scheduled as SMS
- an SMS-only template cannot be scheduled as a call
- a dual-channel template may have different preview blocks for each channel
- absence of one channel config must be explicit and handled cleanly

---

## API Guidance

Prefer extending existing endpoints instead of creating redundant ones.

### Good approach

If there is already something like:
- `GET /v1/templates`
- `GET /v1/templates/{id}`
- `POST /v1/sos-requests`

then extend those DTOs to include:
- `supported_channels`
- `default_channel`
- `sms_preview`
- `call_preview`
- channel-specific availability metadata

### Avoid

Creating parallel endpoints like:
- `/v1/sms-templates`
- `/v1/vapi-call-templates`
- `/v1/template-library-v2`

unless the existing architecture truly makes this unavoidable.

---

## Recommended DTO Shape

This is conceptual, not a forced rewrite.

### List item

```json
{
  "id": "uuid",
  "display_name": "Boss — urgent work abroad",
  "category": "work",
  "supported_channels": ["sms", "call"],
  "default_channel": "sms",
  "description": "Boss needs to discuss a time-sensitive work assignment.",
  "is_custom": false
}
```

### Detail DTO

```json
{
  "id": "uuid",
  "display_name": "Boss — urgent work abroad",
  "category": "work",
  "supported_channels": ["sms", "call"],
  "default_channel": "sms",
  "shared": {
    "caller_role": "boss",
    "reason_code": "travel_assignment_abroad",
    "urgency_level": "high",
    "intended_outcome": "leave_now"
  },
  "channels": {
    "sms": {
      "enabled": true,
      "preview_text": "Need you to call me back about a work assignment."
    },
    "call": {
      "enabled": true,
      "preview_opening_line": "Hey, I need to talk to you about the assignment abroad."
    }
  }
}
```

The exact shape can differ if the existing codebase already has DTOs.
Reuse the existing style wherever possible.

---

## Migration Guidance

### Allowed

- additive DB migration
- additive DTO changes
- additive frontend UI changes
- extending existing template compiler / resolver logic

### Avoid

- massive rename-only migration
- replacing the working Vapi flow with a new abstraction for no reason
- duplicate tables with duplicate content
- migration that breaks existing template IDs if avoidable

### Strong rule

If the existing call-template system already works with Vapi, preserve those
working template IDs and extend them.
Do not churn stable IDs unless there is a real blocker.

---

## Vapi Integration Guidance

Vapi already works.
That is an asset, not something to redesign casually.

Implementation rule:
- keep the working Vapi adapter path
- make it resolve the template's **call** config from the unified template
  architecture
- do not introduce a second call-template registry only for Vapi

The template data chosen by the user in the UI must be the same template data
that ultimately shapes the Vapi assistant behavior.

---

## SMS Integration Guidance

SMS should follow the same template-selection path.

Implementation rule:
- the same `template_id` chosen by the user drives the SMS output
- the backend selects the `sms` config for that template
- sender continuity and other SMS-specific logic can remain SMS-only runtime
  behavior, but it should still hang off the same template object

---

## UX Consequences

This feature should make the product feel simpler.

The user should experience:
- one template library
- one detail view
- one custom-template builder
- one scheduling entry point

They should not need to understand internal channel architecture.

The only visible difference is:
- some templates support only SMS
- some support only call
- some support both

---

## Non-Goals

This feature is not trying to:
- make SMS and call wording identical
- collapse all provider-specific runtime behavior into one identical payload
- force a perfect abstract architecture if the current codebase already has a
  workable template structure
- rebuild the product around a brand-new domain model during MVP

---

## Final Implementation Principle

**One template concept. Channel-specific behavior. Minimal code churn. Reuse the
existing architecture first.**

If there is already a working template system, extend it.
If Vapi already works, keep it working.
If the frontend already has template views, build on them.
Only add new code where the current architecture truly lacks the feature.

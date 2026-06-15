# Template Model Extension Spec

Additive extension to the existing template architecture.

This spec sits on top of the current model where:
- `Template` is the shared scenario meaning
- `TemplateVersion` is the locale-aware, channel-specific execution config
- custom templates go through the same compose / render / snapshot pipeline
- no free-form user text is allowed into provider content

Do not replace the current template system.
Do not create separate parallel systems for SMS templates and call templates.
Do not fork Vapi logic away from the existing template flow.
Use the current architecture and extend it carefully.

This version also locks the UX decision that **user context is edited in the Profile tab**, not forced during onboarding and not pushed on the Home screen.

---

## 1. Goal

The current model is good, but the custom-template builder is still too shallow.
Today the user can choose things like persona, reason, category, urgency, call length, and voice style.
That is not enough for believable real-world scenarios across work, social, family, privacy, transition, and safety situations.

We need to make templates more expressive **without** allowing prompt injection or arbitrary story writing.

The right direction is:
- keep the existing `Template` + `TemplateVersion` architecture
- extend the shared template model with more structured scenario fields
- add a reusable **user context profile** so the system can adapt work, home, family, and life-transition details safely
- keep all runtime wording generated from approved skeletons and label catalogs
- let the user manage that context from a dedicated **Profile** tab when they want to, instead of interrupting first use

This should let users build scenarios like:
- leave a bad date politely
- step out of an uncomfortable or unsafe situation immediately
- leave a long meeting or dragging hangout
- justify being unavailable for the rest of the day
- justify being away for a weekend, a week, or two weeks
- support a believable work callback or travel assignment
- support home / roommate / landlord / pet / delivery situations
- support family and care obligations
- support relationship privacy or a new life chapter feeling established

---

## 2. Non-negotiable constraints

These stay exactly as they are in the current architecture.

### 2.1 No free-form provider content
The user must **not** type raw call prompts, raw SMS bodies, raw follow-up facts, or arbitrary story text that will be sent to Vapi or Twilio.

User-entered text is allowed only for:
- local display labels
- optional private notes that are never sent to providers

### 2.2 One logical template, channel-specific behavior
There is still only one logical template.
Call and SMS remain channel variants of the same template.

### 2.3 Use the existing dispatch path
Custom templates must still resolve through:
- `Template`
- `TemplateVersion`
- version resolution
- compose/render
- request snapshot
- existing Vapi / Twilio dispatch logic

### 2.4 Keep immutable history
Once a request is created and dispatched, the rendered request plan remains frozen in the request snapshot.
Future template edits must not rewrite past history.

### 2.5 Do not overload the word "persona"
There are two different concepts:
- **caller persona** = who is contacting the user (`boss`, `roommate`, `sibling`)
- **user context** = the user's own life situation (`works in construction`, `lives with roommate`, `recently moved`)

Do not mix those into one field.

### 2.6 Profile context is optional
The app must remain fully usable with built-in templates and generic custom templates even when the user has never filled out a profile.

### 2.7 Do not interrupt onboarding or Home
Do not force profile context during signup, OTP verification, first login, or on the Home screen.
The user should be able to open the app after verification and immediately use default templates.

---

## 3. UX placement and product behavior

### 3.1 Profile is the place for context
The user sets reusable realism context in the **Profile** tab at the bottom navigation.

The Profile tab is where the user can optionally define things like:
- work context
- living setup
- family/care context
- relationship/privacy context
- transition/travel context

This should feel like profile customization, not mandatory onboarding.

### 3.2 No Home-screen nagging
Do not add cards, banners, blockers, or repeated nags on the Home screen asking the user to complete a profile.
The Home screen should stay focused on using templates quickly.

### 3.3 Templates page may show a light note
On the Templates page, where the user can create custom templates, it is okay to show a small informational note near the top **if no profile context exists yet**.

Example tone:
- “You can configure your profile for more tailored custom templates.”
- “Optional: add profile details to make custom templates more contextual.”

This note should:
- be small and non-blocking
- not interrupt template browsing
- not force navigation
- disappear or become less prominent once the user has already configured relevant profile sections

### 3.4 Default templates must work first
Users should be able to:
- verify their number
- enter the app
- use default templates
- schedule calls or SMS
- create basic custom templates

without completing profile context.

### 3.5 Profile context should improve quality, not unlock the app
Profile context is a quality enhancer for custom templates.
It is not a requirement for the core app experience.

---

## 4. Model direction

### 4.1 Keep the current main tables
Keep:
- `Template`
- `TemplateVersion`

Do not create a separate `SmsTemplate`, `CallTemplate`, or any duplicate template subsystem.

### 4.2 Add a new reusable user profile layer
Add a new table or extend the existing user-profile/settings surface with a structured reusable context object:
- `UserContextProfile`

Purpose:
- hold reusable, structured facts about the user's own context
- allow multiple templates to sound more believable without making the user re-enter the same life context every time
- keep this separate from caller persona and sender identity

If the current backend already has a profile/settings model under `/me`, reuse that surface instead of inventing an unnecessary parallel profile system.

### 4.3 Extend `Template` with richer structured scenario fields
The new fields below belong to the **shared core** because they apply across both channels.

### 4.4 Reuse existing `TemplateVersion` fields wherever possible
Do **not** add lots of new channel-specific fields unless the current system truly needs them.
For the first pass, reuse existing fields such as:
- `supports_call`
- `supports_sms`
- `call_system_prompt_template`
- `call_opening_line_template`
- `call_followup_facts_json`
- `call_voice_profile_code`
- `call_max_duration_seconds`
- `sms_body_template`
- `sms_followup_body_template`
- `sms_sender_style`

The new structured template inputs should mainly influence how the composer builds those existing fields.

---

## 5. New shared-core template model

Extend `Template` with the following additive fields.

## 5.1 Required new fields on `Template`

| Field | Type | Purpose |
|---|---|---|
| `urgency_code` | str | urgency level for both channels |
| `outcome_code` | str | what the user needs the scenario to achieve |
| `setting_code` | str | current social / physical context |
| `tone_code` | str | emotional tone |
| `detail_profile_code` | str | how detailed / contextual the story should feel |
| `discretion_level_code` | str | how subtle the wording must be |
| `formality_code` | str | casual / neutral / professional tone shaping |
| `expected_response_code` | str | what kind of reply from the user is natural |
| `followup_behavior_code` | str | whether and how the scenario continues |
| `continuity_scope_code` | str | one-off vs multi-day / multi-week continuity |
| `context_modules_json` | JSON array[str] | which user-context modules this template is allowed to use |

These are all **safe coded values**, not free text.

## 5.2 Optional helper field on `Template`

| Field | Type | Purpose |
|---|---|---|
| `builder_config_json` | JSON | optional storage of the original structured selections used to compose the template |

This field is optional.
Use it only if it makes editing / re-opening custom templates much easier.
Do **not** add it if the current codebase does not need it.

### Why `builder_config_json` is optional
The current architecture already has explicit shared-core fields.
Adding every future custom-builder knob as its own top-level DB column may become noisy.

A good rule:
- fields needed for filtering, listing, or querying belong as real columns
- extra structured editor state can live in `builder_config_json` if necessary

For this feature, the explicit columns in section 5.1 are enough for the first pass.

---

## 6. New reusable `UserContextProfile`

Add a new table, or extend an existing profile/settings entity with equivalent nullable fields:
- `user_context_profiles`

One row per user.

Purpose:
- capture reusable personal context that makes work, home, family, privacy, and transition templates believable
- keep those selections structured and safe
- let the composer choose better wording without raw user-written stories
- allow the user to edit this information from the Profile tab whenever they want

## 6.1 Table shape

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID unique FK -> users | one profile per user |
| `work_industry_code` | str? | nullable scalar |
| `work_role_level_code` | str? | nullable scalar |
| `work_setting_code` | str? | nullable scalar |
| `work_schedule_code` | str? | nullable scalar |
| `work_travel_scope_code` | str? | nullable scalar |
| `living_setup_code` | str? | nullable scalar |
| `home_responsibility_codes_json` | JSON array[str]? | nullable multi-select |
| `dependent_context_codes_json` | JSON array[str]? | nullable multi-select |
| `family_support_level_code` | str? | nullable scalar |
| `family_proximity_code` | str? | nullable scalar |
| `relationship_visibility_code` | str? | nullable scalar |
| `relationship_stage_code` | str? | nullable scalar |
| `privacy_preference_code` | str? | nullable scalar |
| `transition_state_code` | str? | nullable scalar |
| `transition_horizon_code` | str? | nullable scalar |
| `created_at` | datetime | |
| `updated_at` | datetime | |

## 6.2 Nullability rule

Every user-context field must be nullable / optional.

That means:
- the user may never create a profile row yet
- or the profile row may exist with many null fields
- or only one section may be filled
- or just a few fields inside a section may be filled

This is intentional.
It supports:
- privacy
- safety-sensitive usage
- minimal onboarding friction
- users who only want default templates
- users who only need one context area, such as work but not family

Do not require completeness.
Do not infer missing values.
Do not treat missing values as validation failures.

## 6.3 Why this should be a separate reusable profile

Do **not** try to store all of this on `Template`.
That would duplicate the same user facts across many templates.

Examples:
- the user's work domain might affect 10 work templates
- their living setup might affect 6 home templates
- their life transition might affect several continuity templates

This is reusable user context, not scenario meaning.

## 6.4 Safe fallback behavior

If profile context is missing, template composition must fall back to generic safe wording.

Example:
- with context: “I need you back for a client issue on site.”
- without context: “I need you back for a work issue.”

Missing profile data should reduce specificity, not break the template.

---

## 7. Option catalogs for the new model

These catalogs should live in the existing structured options system.
They should be returned by the backend through the template options endpoint and any user-profile endpoint used by the Profile tab.

All options are approved code values with localized labels.

---

## 7.1 Category options

Use these as the top-level scenario categories:

- `work`
- `home_logistics`
- `family_care`
- `social_exit`
- `relationship_privacy`
- `travel_transition`
- `personal_boundaries`
- `safety_discomfort`

---

## 7.2 Caller persona options

These are the **caller personas** already conceptually present in the system, but they should be expanded and grouped better.

### Work personas
- `manager`
- `team_lead`
- `coworker`
- `hr_office_contact`
- `client`
- `office_line`

### Home / logistics personas
- `roommate`
- `landlord_building_contact`
- `neighbor`
- `repair_service_contact`
- `delivery_service_contact`

### Family personas
- `sibling`
- `parent`
- `family_member`
- `childcare_contact`
- `eldercare_contact`
- `family_friend`

### Social personas
- `best_friend`
- `close_friend`
- `friend`
- `group_organizer`
- `ride_contact`

### Relationship / personal personas
- `partner`
- `spouse`
- `romantic_contact`

### Safety-support personas
- `trusted_friend`
- `pickup_contact`

Avoid institution-heavy or risky personas such as:
- police
- doctor
- lawyer
- bank
- government office

Those should not be part of the normal custom-template catalog.

---

## 7.3 Reason options

### Work reasons
- `work_urgent_task`
- `work_schedule_change`
- `work_shift_cover`
- `work_client_issue`
- `work_document_needed`
- `work_callback_needed`
- `work_travel_assignment`
- `work_meeting_moved`
- `work_decision_needed`

### Home / logistics reasons
- `home_problem`
- `home_delivery_arriving`
- `home_repair_issue`
- `home_key_access_issue`
- `home_pet_issue`
- `home_utility_issue`
- `home_visitor_arrival`
- `home_move_packing_issue`

### Family / care reasons
- `family_checkin`
- `family_plans_changed`
- `family_help_needed`
- `family_pickup_handoff`
- `family_elder_support_issue`
- `family_childcare_timing_issue`

### Social reasons
- `social_friend_outside`
- `social_ride_arrived`
- `social_location_changed`
- `social_pickup_needed`
- `social_group_plan_changed`
- `social_quick_favor`

### Relationship / privacy reasons
- `privacy_partner_needs_you`
- `privacy_private_plans`
- `privacy_need_checkin`
- `privacy_leave_for_personal_reasons`
- `privacy_keep_details_private`

### Transition / continuity reasons
- `transition_work_trip`
- `transition_onboarding_crunch`
- `transition_helping_with_move`
- `transition_staying_elsewhere`
- `transition_new_routine`
- `transition_family_visit`
- `transition_recurring_obligation`

### Safety / immediate exit reasons
- `safety_step_out_now`
- `safety_need_pickup`
- `safety_private_call_now`
- `safety_leave_immediately`
- `safety_friend_waiting_outside`

---

## 7.4 Urgency options

- `low`
- `medium`
- `high`
- `immediate`

---

## 7.5 Outcome options

This is one of the most important missing parameters.
It answers: **what does the user need this scenario to achieve?**

- `step_out_briefly`
- `leave_now`
- `leave_within_10m`
- `end_conversation`
- `cancel_later_today`
- `unavailable_rest_of_day`
- `unavailable_overnight`
- `unavailable_weekend`
- `unavailable_one_week`
- `unavailable_two_weeks`

---

## 7.6 Setting options

This is the current social / physical context where the user is.

- `date`
- `casual_hangout`
- `dinner`
- `party`
- `work_meeting`
- `team_event`
- `family_gathering`
- `public_transit`
- `online_call`
- `at_home`
- `bar_restaurant`
- `walking_outside`
- `waiting_room`

---

## 7.7 Detail profile options

- `minimal`
- `grounded`
- `contextual`
- `continuity`

Meaning:
- `minimal` = vague, low-detail, safest default
- `grounded` = one believable anchor
- `contextual` = can use relevant user context safely
- `continuity` = suitable for repeated use over days or weeks

---

## 7.8 Discretion level options

- `public_safe`
- `normal`
- `direct`

Meaning:
- `public_safe` = subtle wording, good when others may hear
- `normal` = standard believable wording
- `direct` = stronger and clearer, useful for urgent exits

---

## 7.9 Tone options

- `warm`
- `casual`
- `professional`
- `apologetic`
- `concerned`
- `firm`
- `rushed`
- `calm`

---

## 7.10 Formality options

- `casual`
- `neutral`
- `professional`

---

## 7.11 Expected response options

- `no_reply_needed`
- `quick_acknowledgement`
- `say_call_back`
- `say_on_my_way`
- `say_reply_later`
- `step_out_and_answer`
- `confirm_tonight`

---

## 7.12 Follow-up behavior options

- `one_touch_only`
- `one_reminder_if_ignored`
- `text_then_call`
- `call_then_text`
- `later_same_day_checkin`
- `recurring_next_few_days`

---

## 7.13 Continuity scope options

- `one_off`
- `same_day`
- `overnight`
- `weekend`
- `multi_day`
- `one_week`
- `two_weeks`
- `recurring`

---

## 7.14 User-context profile options

## Work context

### `work_industry_code`
- `office_admin`
- `tech_product`
- `finance_business`
- `retail`
- `hospitality`
- `food_service`
- `healthcare`
- `education`
- `construction_trades`
- `manufacturing`
- `warehouse_logistics`
- `transport_driving`
- `sales`
- `media_creative`
- `public_service`
- `freelance_contractor`

### `work_role_level_code`
- `staff`
- `coordinator`
- `specialist`
- `lead`
- `manager`
- `owner_founder`
- `contractor`
- `shift_worker`
- `on_call_worker`

### `work_setting_code`
- `office`
- `remote`
- `hybrid`
- `store_shopfloor`
- `restaurant_bar`
- `clinic_hospital`
- `school_campus`
- `site_field`
- `warehouse`
- `client_site`

### `work_schedule_code`
- `regular_daytime`
- `early_shift`
- `late_shift`
- `night_shift`
- `rotating_shift`
- `flexible`
- `on_call`

### `work_travel_scope_code`
- `none`
- `local`
- `regional`
- `multi_day`
- `international`

## Home context

### `living_setup_code`
- `alone`
- `with_roommate`
- `with_partner`
- `with_family`
- `shared_house`

### `home_responsibility_codes_json`
- `deliveries`
- `repairs`
- `landlord_building`
- `pets`
- `utilities`
- `keys_access`
- `visitors`
- `moving_setup`

### `dependent_context_codes_json`
- `dog`
- `cat`
- `multiple_pets`
- `childcare`
- `elder_support`

## Family / care context

### `family_support_level_code`
- `none`
- `occasional_help`
- `regular_support`
- `primary_support_contact`

### `family_proximity_code`
- `same_home`
- `same_city`
- `nearby`
- `out_of_town`

## Relationship / privacy context

### `relationship_visibility_code`
- `private`
- `close_circle_knows`
- `mostly_public`

### `relationship_stage_code`
- `new`
- `developing`
- `established`

### `privacy_preference_code`
- `low`
- `medium`
- `high`

## Transition / travel context

### `transition_state_code`
- `none`
- `new_job_recently`
- `training_onboarding_phase`
- `moved_recently`
- `settling_new_place`
- `more_travel_than_usual`
- `new_routine_phase`

### `transition_horizon_code`
- `today_only`
- `few_days`
- `one_week`
- `two_weeks`

---

## 8. Backend architecture changes

## 8.1 Extend the options endpoint
Extend the existing template options endpoint to include the new option catalogs:
- outcomes
- settings
- detail profiles
- discretion levels
- tones
- formalities
- expected responses
- follow-up behaviors
- continuity scopes
- user-context profile options

The frontend custom-template editor should build entirely from these backend-provided option catalogs.

## 8.2 Extend `POST /v1/templates`
Accept the new structured template inputs.
Still reject any provider-bound free text.

Expected payload direction:
- existing core template data
- new shared-core coded fields
- selected context modules
- selected channels
- existing channel builder options already supported by the system

## 8.3 Add profile endpoints or reuse existing `/me`
Preferred direction:
- extend the existing `/me` or profile/settings surface if it already exists
- keep context/profile editing attached to the Profile tab

Possible shapes:
- `GET /v1/me/profile`
- `PUT /v1/me/profile`

or, if the codebase already has a cleaner separation:
- `GET /v1/me/context-profile`
- `PUT /v1/me/context-profile`

Do not add both unless the current architecture truly needs both.

## 8.4 Composition must tolerate null profile values
The composer must accept partial or empty profile context.
It should only use modules/fields that are present and relevant.
Everything else must fall back to generic approved wording.

---

## 9. Frontend behavior

The custom-template builder should become a structured wizard, not one giant form.

### 9.1 Profile tab
Add or extend a **Profile** tab in the bottom navigation.
This is where the user edits optional context/profile information.
Replace the Calm tab with the new Profile Tab

The Profile tab should:
- make it clear this information is optional
- allow partial completion
- allow clearing/removing data later
- not pressure the user into filling every field

### 9.2 Templates page note
On the Templates page, if no relevant profile context exists yet, show a small non-blocking note near the top.

Example:
- “You can configure your profile for more tailored custom templates.”

This note can include a CTA to open the Profile tab, but it should remain optional and dismissible or naturally ignorable.

### 9.3 Do not ask on Home
Do not add profile-completion prompts to the Home screen.
The Home screen should stay focused on quick use of default templates and recent selections.

### 9.4 Custom-template flow
Recommended flow:

#### Step 1: scenario core
- category
- caller persona
- reason

#### Step 2: outcome and tone
- urgency
- outcome
- setting
- tone
- formality
- detail profile
- discretion level

#### Step 3: continuity and follow-up
- expected response
- follow-up behavior
- continuity scope

#### Step 4: optional context modules
Show only relevant modules:
- work
- home
- family
- relationship
- transition

These should pull from the user's saved profile context where possible, but must also allow “none / skip / generic”.

#### Step 5: channels
- call
- SMS
- both

Then reuse the existing channel-specific settings already supported by the app:
- call length
- voice style
- whatever SMS style knobs already exist

### 9.5 First use stays easy
After verification / first login, the user should be able to use default templates immediately.
No profile wizard should block first use.

---

## 10. Safe composition rules

These rules are critical.

### 10.1 No raw custom story writing
Do not add:
- free text "what should the caller say"
- free text "story details"
- free text "job description"
- free text "company name"
- free text "location"
- free text "medical problem"
- free text "legal issue"

### 10.2 Use context codes, not claims
The user should choose safe structured codes like:
- `construction_trades`
- `manager`
- `with_roommate`
- `moved_recently`

The system may then generate generic but believable phrasing.

### 10.3 Prefer generic realism over dangerous specificity
Good:
- urgent work issue
- project change
- schedule change
- delivery issue
- family support matter
- personal plans
- travel assignment

Bad:
- specific illness claims
- police matters
- court matters
- bank fraud claims
- government threats
- false accusations

### 10.4 Context is optional
A user should be able to create a valid template without a completed context profile.
The system should degrade gracefully to generic wording.

### 10.5 Context should be deletable
Users should be able to remove saved profile context later.
Deleting context must not break existing built-in or custom templates; it should only reduce future specificity.

---

## 11. Recommended migration strategy

Keep this additive.

### Backend
1. add the new shared-core fields to `Template`
2. add `UserContextProfile` or extend the existing profile/settings model with equivalent nullable fields
3. extend the options catalogs
4. extend the custom-template create flow
5. update the composer to use the new fields
6. update render context only where truly needed
7. keep `TemplateVersion` mostly unchanged for the first pass

### Frontend
1. extend the template models / DTOs with the new shared-core fields
2. add or extend a bottom **Profile** tab for optional context editing
3. add the small profile note to the Templates page when relevant
4. extend the custom-template editor into a structured multi-step builder
5. keep Home focused on fast default-template usage
6. keep using the current template catalog and request flow

---

## 12. Final implementation guidance

Use the architecture that already exists.

That means:
- reuse `Template`
- reuse `TemplateVersion`
- reuse the compose layer
- reuse the version / locale system
- reuse the request snapshot system
- reuse the existing Vapi integration path
- reuse the existing frontend template library / picker / custom-template editor if present
- reuse the existing profile/settings model or Profile tab if it already exists

Do not add unnecessary duplicate code.
Do not create parallel template systems.
Do not turn custom templates into raw prompt editing.
Do not add Home-screen profile nags or mandatory onboarding profile steps.

The real upgrade here is:
- richer structured template meaning
- reusable optional profile context
- better composition quality
- safer, more believable scenarios across many real-life situations
- while keeping first use simple and low-friction

# Deploy checklist

Everything between "works on the laptop" and "people can buy credits", in the
order it has to happen. Each item says whether it is **done** (in the repo and
tested), **to do** and who can do it: anyone with the repo, only with the
accounts (Apple, Twilio, Vapi, OpenAI), or on the server. Whoever finds
something that belongs here adds it right away.

The server may already host other apps. AlibiMe gets its own user, folder,
port, domain and database there; `deploy/README.md` has the steps.

## 1. Done and tested locally

- [x] **Credits live on the server only.** The app shows the balance the
  backend reports; every call and text is charged by the backend before it goes
  out (`workers/dispatch.py`).
- [x] **Purchases are verified with Apple's library** and bound to the account
  (`appAccountToken`), one grant per transaction. Tested with StoreKit in the
  simulator against the real verifier (`APP_STORE_ENVIRONMENT=Xcode`).
- [x] **First-purchase bonus once per phone number**, free credits once per
  phone number, also after deleting the account.
- [x] **The server refuses to start with mocks.** Outside `APP_ENV=local` or
  `test` (an unset `APP_ENV` counts as production) the API and the worker stop
  while the OTP, voice, text or purchase provider is a mock, the secret is the
  dev default or `PHONE_ENCRYPTION_KEY` is empty.
- [x] **No double charge when the backend is down during a purchase.** The
  paid purchase stays unfinished, the sheet says the payment went through and
  the button only retries adding the credits. Unit tested, and against the
  local API: the same transaction twice adds the credits once, another account
  gets `transaction_already_redeemed`. Simulator click-through in 2.
- [x] **No free credits for virtual numbers** (carrier lookup via Twilio when
  the number starts its verification) and, with DeviceCheck, once per iPhone.
  Tested with mocks.
- [x] **Calls into another country end before the second billed minute**
  (`CROSS_BORDER_CALL_MAX_SECONDS`).
- [x] **Account deletion** in Settings (`DELETE /v1/me`), as the App Store
  requires.
- [x] **Worker end to end with mocks.** A call and a text go from the API
  through the worker to the mock provider and end `completed`, charged 2 and 1
  credits. Locally a request waits at `provider_accepted` until
  `python scripts/cli.py simulate <request id>` sends the mock delivery
  events; without that, reconciliation marks it failed after 30 minutes.
- [x] **Backend URL per build configuration.** `BC_BACKEND_URL` in
  `App/Signing.xcconfig`: the local server for Debug, a placeholder
  (`api.alibime.example`) for Release. Only Debug builds accept an override
  from the scheme or `defaults write`.

## 2. Still to test locally (simulator, StoreKit scheme)

- [ ] Backend stopped during a purchase: "Add my credits" appears, a retry
  after restarting adds them once, nothing is charged twice. (Backend side and
  view model done, see 1; the click-through is left.)
- [x] Free credits, against the local API with the app's calls and mock
  DeviceCheck: the first number gets 3, a second number on the same device 0,
  a VoIP number 0.
- [ ] Ask to Buy: enable it in `App/AlibiMe.storekit`, buy, approve in Xcode's
  transaction manager; the credits arrive without restarting the app.
- [ ] Failed and interrupted purchases (StoreKit file options): a clear
  message, no credits, no charge. (Unit tested: a cancel stays quiet, a
  pending purchase explains itself, a server error keeps the paid purchase.)

## 3. Needs your accounts

Apple Developer / App Store Connect:

- [ ] **Decide the bundle id before creating anything.** It is still
  `com.believablecall.app`; products, keys and the App Store record hang on it
  and can't move later.
- [ ] Paid Apps agreement, banking and tax forms.
- [ ] **Small Business Program** (15% instead of 30%) before the first sale.
- [ ] The three consumables with the ids from `backend/app/seeds/seed.py` and
  the prices from `docs/pricing.md` (4.99, 9.99, 19.99 EUR).
- [ ] App Store Server Notifications V2 URL:
  `https://<api domain>/v1/webhooks/app-store` (Production and Sandbox).
- [ ] A **DeviceCheck key** (Certificates, Identifiers & Profiles, Keys): team
  id, key id, the `.p8` file. Only downloadable once.
- [ ] Apple's root certificates (apple.com/certificateauthority, the `.cer`
  files) for the purchase verifier.
- [ ] A sandbox tester account.

Twilio:

- [ ] Paid (non-trial) account; a trial can only call verified numbers.
- [ ] Verify service for the login codes; Lookup with Line Type Intelligence
  enabled (the VoIP check, about $0.008 per lookup).
- [ ] Caller numbers bought, then `make sync-senders-vapi`.
- [ ] **Check whether an EEA number can call German users** (a German number
  needs proof of address). Without it, a free call to a German user costs more
  than a buyer brings in (`docs/pricing.md`).

Vapi:

- [ ] Funded account, API key, webhook secret; voices picked
  (`AGENT_VOICE_ID_*`, placeholders now).

OpenAI (or Anthropic):

- [ ] A key for the evals against the real model (`make eval`), then read the
  report before launch.

Tests that need these accounts:

- [ ] A real call and a real text end to end, from a US line and from the
  line German users would get.
- [ ] A sandbox purchase on an iPhone with a TestFlight build
  (`APP_STORE_ENVIRONMENT=Sandbox`): this is the first time Apple's real
  signature is checked.
- [ ] A sandbox refund: the notification arrives and takes the credits back.
- [ ] DeviceCheck on a real iPhone: sign up, delete the account, sign up with
  a second number: no second free credits.
- [ ] Compare `estimated_cost_minor` of the first calls and texts with the
  Vapi and Twilio invoices.

## 4. On the server

- [ ] **Free RAM and disk** (`free -h && nproc && df -h /`), with whatever
  else runs on the server.
- [ ] A domain for the API (DNS to the server), then certbot.
- [ ] User `alibime`, `/opt/alibime`, Python 3.11 venv,
  `pip install -e ".[postgres,appstore]"`.
- [ ] Postgres: database and role `alibime`, `alembic upgrade head`, seed.
- [ ] `/opt/alibime/backend/.env` from `deploy/alibime.env.example`, mode 600.
  The API refuses to start until nothing in it is a mock or a dev secret.
- [ ] Apple's root certificates and the DeviceCheck key in
  `/opt/alibime/secrets`, readable by `alibime` only.
- [ ] systemd units for API, worker and backup; nginx site; the firewall
  only lets SSH, HTTP and HTTPS in, and port 8010 stays on loopback.
- [ ] Webhook URLs set in Twilio (status callback), Vapi (server URL and
  secret) and App Store Connect, all on the API domain.
- [ ] **Backups copied off the server** (the nightly dump sits on the same
  disk otherwise). Restore once to check it works.
- [ ] From outside: `https://<api domain>/health/ready` answers; a login code
  arrives; the app built against the server signs in.

## 5. Before submitting to the App Store

- [ ] The API domain in `App/Local.xcconfig` (gitignored):
  `BC_BACKEND_URL[config=Release] = https:/$()/api.<domain>`. Without it a
  Release build talks to the placeholder and nothing works.
- [ ] Real support and privacy URLs (Settings still links to
  `believablecall.example`).
- [ ] Privacy policy: the draft is `docs/privacy-policy.md`. Fill in the
  brackets (controller, hosting, transfer basis per US provider), have it
  checked once, put it online, and add a German version.
- [ ] **Decide on call transcripts.** Vapi may record calls and keep
  transcripts in its account by default (no `artifactPlan` is sent), and the
  backend keeps raw Vapi webhooks, which can include the transcript, for 30
  days (`webhook_events`). Either switch recording off and store only the
  fields the backend needs, or name both in the privacy policy.
- [ ] Privacy nutrition labels: phone number, purchases, call content
  (processed by Vapi), no tracking.
- [ ] Review notes: a demo account the reviewer can sign in with, and how the
  call works.
- [ ] Export compliance (only standard HTTPS).

## 6. After launch

- [ ] Watch the first days: failed calls, failed redemptions
  (`invalid_store_transaction`), free-credit claims per day.
- [ ] Monthly: provider invoices against `estimated_cost_minor`, conversion
  against the break-even table in `docs/pricing.md`.

# Pricing

How much a call and a text cost us, and what the credit packs charge for them.
Prices were checked on 30 October 2026 on the providers' public pages. Everything
marked **verify** should be checked against a real invoice before launch.

## What it costs us

A call has two parts: Vapi runs the agent (speech recognition, language model,
voice), and Twilio carries the phone line. A text is only Twilio.

| Item | Price | Source |
|---|---|---|
| Vapi, all in (hosting $0.05 plus Deepgram, GPT-4o, ElevenLabs) | $0.08 to $0.13 per minute | vapi.ai/pricing |
| Twilio call from a US number to a US mobile | $0.014 per minute | twilio.com voice pricing, US |
| Twilio call from a US number to a German mobile | $0.376 per minute | twilio.com voice pricing, DE |
| Twilio call from an EEA number to a German mobile | $0.042 per minute | same page |
| Twilio SMS to a US mobile | about $0.0125 (base plus carrier fee) | twilio.com SMS pricing, US |
| Twilio SMS to Germany | $0.112, plus possible carrier fees | twilio.com SMS pricing, DE |
| US phone number | $1.15 per month | twilio.com voice pricing, US |

Twilio bills calls per started minute, so a 61-second call is two minutes.

That makes one call, at the 90-second template maximum and a typical 45 seconds:

| Call to | 45 seconds | 90 seconds |
|---|---|---|
| US mobile | about $0.11 | about $0.22 |
| German mobile, from a US number | about $0.48 | about $0.95 |
| German mobile, from an EEA number | about $0.14 | about $0.28 |

The German mobile surcharge is the one number that matters. Calling German users
from a US number costs about nine times as much per minute as calling them from
an EEA number.

## What a pack brings in

Apple keeps 15% in the Small Business Program (30% without it), and in Germany
the price includes 19% VAT. Per credit, after both:

| Pack | Price | Net per credit |
|---|---|---|
| 12 credits | €2.99 | €0.18 |
| 40 credits | €7.99 | €0.14 |
| 100 credits | €17.99 | €0.13 |

## The proposal

- A text costs 1 credit, a call 4 credits.
- A new phone number gets 4 free credits, enough for one real call. The grant is
  tied to the number (as a hash), so deleting the account and signing up again
  doesn't give it twice.
- Packs as above: 12, 40 and 100 credits.

With these numbers a call brings in €0.51 to €0.71 and a text €0.13 to €0.18.
US calls and texts have a comfortable margin. German texts are thin (about
€0.10 cost). German calls from a US number would lose money past the first
minute, which is why cross-border calls are capped at 55 seconds. The free
starter call costs about €0.45 per German sign-up, plus
Twilio Verify for the login code.

## What to do before launch

1. **Verify** whether an EEA Twilio number (not German, which needs proof of
   address) can call German users. That single change makes German calls
   profitable at these prices.
2. Calls into another country are already capped at 55 seconds so they bill as
   one minute (`CROSS_BORDER_CALL_MAX_SECONDS`, the templates allow up to 90).
   With an EEA line for German users the cap no longer applies to them.
3. Enrol in the App Store Small Business Program before the first sale.
4. Create the three consumable products in App Store Connect with the ids in
   `backend/app/seeds/seed.py` and the prices above.
5. After the first real calls, compare `estimated_cost_minor` on the call and
   message attempts with the Vapi and Twilio invoices and adjust the credit
   costs (`CALL_CREDIT_COST`, `SMS_CREDIT_COST`), which need no app update.

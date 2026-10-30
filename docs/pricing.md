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

## The model

- A call (about a minute at most) costs 2 credits, a text 1.
- A new phone number gets 3 free credits: one text and one call. The text
  offers to save the number as a contact, say as "Mom", and the call then shows
  up as Mom. That is the moment that sells the app, so the free test covers it.
- The first purchase gets 3 bonus credits on top.
- Both the free credits and the bonus are once per phone number (kept as a
  hash), so deleting the account and signing up again doesn't repeat them.
- Packs: 10 credits for €4.99, 25 for €9.99, 60 for €19.99.

## What a pack brings in

Apple keeps 15% in the Small Business Program (30% without it), and in Germany
the price includes 19% VAT. Per credit, after both:

| Pack | Price | Calls | Net per credit |
|---|---|---|---|
| 10 credits | €4.99 | 5 | €0.36 |
| 25 credits | €9.99 | 12 | €0.29 |
| 60 credits | €19.99 | 30 | €0.24 |

A credit has to bring in half a call. That is about €0.22 for a German mobile
called from a US number, €0.07 from an EEA number, and €0.05 in the US. Every
pack covers even the worst case.

## Paying for the free users

Most people who install the app will only use their free credits, so buyers
have to pay for them. What one free user costs (login code, one text, one call
of 55 seconds):

| User | Cost |
|---|---|
| German number, called from a US line | about €0.68 |
| German number, called from an EEA line | about €0.38 |
| US number | about €0.17 |

What a buyer leaves after their first 10-credit pack, if every credit goes into
a full call and after the bonus: about €0.76 from a US line to Germany, about
€2.70 from an EEA line, about €3.20 in the US.

The share of users who have to buy for the free credits to pay off is the cost
of a free user divided by what a buyer leaves:

| | One pack per buyer | Buyer also takes a 25 pack later |
|---|---|---|
| Germany, US line | about 90% | about 27% |
| Germany, EEA line | about 14% | about 5% |
| US | about 5% | about 2% |

Freemium apps commonly convert a few percent of users, so the German case only
works with an EEA line. Texts and calls shorter than a minute make all of this
cheaper; these are worst cases on list prices with an estimated exchange rate.

## What to do before launch

1. **Verify** whether an EEA Twilio number (not German, which needs proof of
   address) can call German users. Without it, free calls to German users cost
   more than buyers bring in.
2. Calls into another country are already capped at 55 seconds so they bill as
   one minute (`CROSS_BORDER_CALL_MAX_SECONDS`, the templates allow up to 90).
3. Enrol in the App Store Small Business Program before the first sale.
4. Create the three consumable products in App Store Connect with the ids in
   `backend/app/seeds/seed.py` and the prices above.
5. After the first real calls, compare `estimated_cost_minor` on the call and
   message attempts with the Vapi and Twilio invoices. Credit costs, free
   credits and the bonus are settings (`CALL_CREDIT_COST`, `SMS_CREDIT_COST`,
   `FREE_TEST_CREDITS`, `FIRST_PURCHASE_BONUS_CREDITS`) and need no app update;
   prices change in App Store Connect.

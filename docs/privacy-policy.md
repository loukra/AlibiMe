# AlibiMe privacy policy (draft)

This is a working draft. Everything in [square brackets] still has to be filled
in before it goes online, and a lawyer or a privacy generator should check it
once. It describes what the app and backend in this repository actually do.

Last updated: [date]

## Who is responsible

[Name, postal address, email address for privacy questions]

## What AlibiMe does with your data, in short

AlibiMe calls or texts you at a time you choose, so you have a reason to
leave. To do that it needs your phone number, the call or text you asked for,
and the time. Calls are spoken by an AI voice. We do not sell your data, show
no ads and use no tracking or analytics tools.

## Your account

You sign in with your phone number and a code we send by SMS. We store:

- your phone number, encrypted, plus a keyed hash of it so we can find your
  account without decrypting it
- your display name, language and time zone, if you set them
- a random ID for your device, the app and iOS version, and a push token if
  you allow notifications
- the sessions that keep you signed in (they expire after 30 days unused)

Legal basis: carrying out our contract with you (Art. 6(1)(b) GDPR).

## Calls and texts

For each call or text you request we store the template you picked, the
channel, the time, its status (for example delivered or not answered) and a
one-line summary or text preview. Your history stays until you delete it with
your account.

If you fill in the optional profile (work, home, family and similar, as
choices from a list), we use it to make calls sound plausible. For a call, a
short text built from those choices goes to the AI model together with the
template.

To place a call or send a text we pass your phone number, the text or the
instructions for the AI voice, and the sender number to the providers below.
During a call the AI hears and transcribes what is said on the line,
including anyone near you who can be heard.

Legal basis: carrying out our contract with you (Art. 6(1)(b) GDPR).

## Credits and purchases

Purchases go through Apple's App Store. We never see your payment details.
Apple sends us a signed record of the purchase, and we keep its transaction ID,
the package and the credits it added, so a purchase can't be counted twice and
refunds can be handled.

Legal basis: carrying out our contract with you (Art. 6(1)(b) GDPR) and our
legal duty to keep business records (Art. 6(1)(c) GDPR).

## Preventing abuse

New numbers get a few free credits once. To stop people collecting them again
and again, we use Apple's DeviceCheck, which tells us whether this iPhone has
already received them without telling us who you are. We also keep a keyed
hash of each phone number that received free credits or a first-purchase
bonus. That hash stays after you delete your account; it cannot be turned back
into your number. We limit how many requests and sign-in codes one account or
number can trigger per hour.

Legal basis: our legitimate interest in preventing misuse of free credits and
of the call service (Art. 6(1)(f) GDPR).

## Service providers

These companies process data for us on our instructions:

| Provider | What for | Data |
|---|---|---|
| Twilio Inc. (USA) | sign-in codes, texts, phone lines | phone number, text content, delivery status |
| Vapi Inc. (USA) | carrying out AI calls | phone number, call instructions, the call audio [and a recording and transcript, see note] |
| OpenAI (USA) | the AI model that writes the caller's words | call instructions, profile text, what is said on the call |
| ElevenLabs (USA) | turning those words into a voice | the words the caller says |
| Deepgram (USA) | transcribing what you say during the call | the call audio |
| Apple Inc. | App Store purchases, DeviceCheck, push notifications | purchase records, device check token, push token |
| [Hosting provider, country] | running our server and database | everything listed above |

[Confirm for each US provider how the transfer is covered: certification under
the EU-US Data Privacy Framework, or standard contractual clauses, and that a
data processing agreement is in place.]

[Note on Vapi: by default Vapi may record calls and keep transcripts in its own
account. Either switch that off before launch or name the retention here.]

## How long we keep data

- Account, history and profile: until you delete your account.
- Raw delivery reports from Twilio and Vapi: 30 days. [These can include the
  call transcript; see the open point in the deploy checklist.]
- Server backups: 14 days, so deleted data is fully gone after at most 14 days.
- Purchase records: as long as tax law requires [usually up to 10 years].
- Phone number hashes for free credits: kept, as explained above.

## Deleting your account

Settings, Delete account removes your account right away: phone numbers,
sessions, history, custom templates, profile and credits. Calls or texts that
were still waiting are cancelled. Only the hashes described above and the
purchase records we must keep remain.

## Contacts

If you choose to save a caller as a contact, iOS asks for access to your
contacts. The contact is saved on your phone only; we never read or upload
your address book.

## Your rights

You can ask us for access to your data, correction, deletion, restriction of
processing and a copy in a portable format, and you can object to processing
based on legitimate interest (Art. 15 to 21 GDPR). Write to [email]. You can
also complain to a data protection authority, for example [the authority for
the controller's federal state].

## Changes

If this policy changes, the new version will be on this page with a new date.

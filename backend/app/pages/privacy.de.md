# AlibiMe Datenschutzerklärung (Entwurf)

Das ist ein Arbeitsentwurf. Alles in [eckigen Klammern] muss noch ausgefüllt
werden, bevor er online geht, und ein Anwalt oder ein Datenschutz-Generator
sollte ihn einmal prüfen. Er beschreibt, was die App und ihr Server
tatsächlich tun.

Stand: [Datum]

## Wer verantwortlich ist

[Name, Postanschrift, E-Mail-Adresse für Datenschutzfragen]

## Was AlibiMe mit deinen Daten macht, kurz gesagt

AlibiMe ruft dich an oder schreibt dir eine SMS, wann du willst, damit du
einen Grund hast zu gehen. Dafür braucht die App deine Telefonnummer, den
gewünschten Anruf oder die SMS und die Uhrzeit. Anrufe spricht eine KI-Stimme.
Wir verkaufen deine Daten nicht, zeigen keine Werbung und nutzen keine
Tracking- oder Analyse-Tools.

## Dein Konto

Du meldest dich mit deiner Telefonnummer und einem Code an, den wir per SMS
schicken. Wir speichern:

- deine Telefonnummer, verschlüsselt, dazu einen Hash mit geheimem Schlüssel,
  damit wir dein Konto finden, ohne die Nummer zu entschlüsseln
- deine Sprache und Zeitzone, dazu deinen Vornamen, falls du einen aus unserer
  Liste wählst
- eine zufällige ID, die die App für dein Gerät erzeugt
- die Sitzungen, die dich angemeldet halten (sie laufen nach 30 Tagen ohne
  Nutzung ab)

Rechtsgrundlage: Erfüllung unseres Vertrags mit dir (Art. 6 Abs. 1 lit. b
DSGVO).

## Anrufe und SMS

Für jeden Anruf und jede SMS, die du anforderst, speichern wir das gewählte
Alibi, den Weg (Anruf oder SMS), die Uhrzeit, den Status (zum Beispiel
zugestellt oder nicht angenommen) und eine einzeilige Zusammenfassung oder
Vorschau der SMS. Dein Verlauf bleibt, bis du ihn mit deinem Konto löschst.

Wenn du das freiwillige Profil ausfüllst (Arbeit, Zuhause, Familie und
Ähnliches, als Auswahl aus einer Liste), nutzen wir es, damit Anrufe
glaubwürdig klingen. Für einen Anruf geht ein kurzer Text aus dieser Auswahl
zusammen mit dem Alibi an das KI-Modell.

Um einen Anruf zu starten oder eine SMS zu senden, geben wir deine
Telefonnummer, den Text oder die Anweisungen für die KI-Stimme und die
Absendernummer an die unten genannten Dienstleister weiter. Während eines
Anrufs hört und transkribiert die KI, was in der Leitung gesagt wird, auch von
Menschen in deiner Nähe, die zu hören sind, damit sie antworten kann. Das
passiert live: Anrufe werden nicht aufgezeichnet, und weder wir noch Vapi
speichern ein Transkript oder eine Zusammenfassung des Anrufs.

Rechtsgrundlage: Erfüllung unseres Vertrags mit dir (Art. 6 Abs. 1 lit. b
DSGVO).

## Credits und Käufe

Käufe laufen über Apples App Store. Deine Zahlungsdaten sehen wir nie. Apple
schickt uns einen signierten Kaufbeleg, und wir speichern dessen
Transaktions-ID, das Paket und die gutgeschriebenen Credits, damit ein Kauf
nicht doppelt zählt und Erstattungen bearbeitet werden können.

Rechtsgrundlage: Erfüllung unseres Vertrags mit dir (Art. 6 Abs. 1 lit. b
DSGVO) und unsere gesetzliche Pflicht, Geschäftsunterlagen aufzubewahren
(Art. 6 Abs. 1 lit. c DSGVO).

## Missbrauch verhindern

Neue Nummern bekommen einmalig ein paar kostenlose Credits. Damit niemand sie
immer wieder abholt, nutzen wir Apples DeviceCheck. Das sagt uns, ob dieses
iPhone sie schon bekommen hat, ohne uns zu verraten, wer du bist. Außerdem
speichern wir einen Hash mit geheimem Schlüssel von jeder Telefonnummer, die
kostenlose Credits oder einen Bonus zum ersten Kauf bekommen hat. Dieser Hash
bleibt auch nach dem Löschen deines Kontos; deine Nummer lässt sich daraus
nicht zurückgewinnen. Wir begrenzen, wie viele Anfragen und Anmeldecodes ein
Konto oder eine Nummer pro Stunde auslösen kann.

Rechtsgrundlage: unser berechtigtes Interesse, Missbrauch der kostenlosen
Credits und des Anrufdienstes zu verhindern (Art. 6 Abs. 1 lit. f DSGVO).

## Dienstleister

Diese Unternehmen verarbeiten Daten in unserem Auftrag und nach unseren
Weisungen:

| Dienstleister | Wofür | Daten |
|---|---|---|
| Twilio Inc. (USA) | Anmeldecodes, SMS, Telefonleitungen | Telefonnummer, SMS-Inhalt, Zustellstatus |
| Vapi Inc. (USA) | Durchführung der KI-Anrufe | Telefonnummer, Anweisungen für den Anruf, der Ton des Anrufs, solange er läuft |
| OpenAI (USA) | das KI-Modell, das die Worte des Anrufers schreibt | Anweisungen für den Anruf, Profiltext, was im Anruf gesagt wird |
| ElevenLabs (USA) | macht aus diesen Worten eine Stimme | die Worte des Anrufers |
| Deepgram (USA) | transkribiert, was du im Anruf sagst | der Ton des Anrufs |
| Apple Inc. | App-Store-Käufe, DeviceCheck | Kaufbelege, DeviceCheck-Token |
| [Hosting-Anbieter, Land] | Betrieb unseres Servers und unserer Datenbank | alles oben Genannte |

[Für jeden US-Dienstleister bestätigen, wie die Übermittlung abgesichert ist:
Zertifizierung nach dem EU-US Data Privacy Framework oder
Standardvertragsklauseln, und dass ein Auftragsverarbeitungsvertrag besteht.]

[Bestätigen, wie lange OpenAI, ElevenLabs und Deepgram API-Daten bei sich
speichern (OpenAI kann API-Eingaben zum Beispiel für eine begrenzte Zeit zur
Missbrauchserkennung aufbewahren), und das hier nennen.]

## Wie lange wir Daten speichern

- Konto, Verlauf und Profil: bis du dein Konto löschst.
- Zustellberichte von Twilio und Vapi, reduziert auf Status, Dauer, Kosten und
  Fehlercode: 30 Tage.
- Server-Backups: 14 Tage, gelöschte Daten sind also nach höchstens 14 Tagen
  vollständig weg.
- Kaufbelege: so lange, wie das Steuerrecht es verlangt [meist bis zu 10
  Jahre].
- Hashes von Telefonnummern für kostenlose Credits: bleiben, wie oben erklärt.

## Dein Konto löschen

Einstellungen, Konto löschen entfernt dein Konto sofort: Telefonnummern,
Sitzungen, Verlauf, eigene Alibis, Profil und Credits. Anrufe oder SMS, die
noch ausstanden, werden abgebrochen. Nur die oben beschriebenen Hashes und die
Kaufbelege, die wir aufbewahren müssen, bleiben.

## Kontakte

Wenn du einen Anrufer als Kontakt sichern willst, fragt iOS nach Zugriff auf
deine Kontakte. Der Kontakt wird nur auf deinem iPhone gespeichert; dein
Adressbuch lesen oder hochladen wir nie.

## Deine Rechte

Du kannst von uns Auskunft über deine Daten verlangen, ihre Berichtigung,
Löschung, die Einschränkung der Verarbeitung und eine Kopie in einem
übertragbaren Format, und du kannst einer Verarbeitung widersprechen, die auf
berechtigtem Interesse beruht (Art. 15 bis 21 DSGVO). Schreib an
{support_email}. Du kannst dich auch bei einer Datenschutzaufsichtsbehörde
beschweren, zum Beispiel bei [der Behörde für das Bundesland des
Verantwortlichen].

## Änderungen

Wenn sich diese Erklärung ändert, steht die neue Fassung mit neuem Datum auf
dieser Seite.

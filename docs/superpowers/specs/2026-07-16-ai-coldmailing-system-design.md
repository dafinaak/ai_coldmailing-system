# Design: AI Coldmailing System (v1)

Datum: 16.07.2026
Status: Abschnitte 1–3 im Gespräch freigegeben; schriftliche Abnahme steht aus.

## Zweck

Ein wiederverwendbares KI-Coldmailing-System als eigenes Angebot/Produkt,
einsetzbar bei mehreren Kunden (Vorbild in der Positionierung: wholix.ai).
Der Unterschied zu Serienbrief-Werkzeugen: pro Lead wird recherchiert und
individuell getextet.

## Umfang v1

- Leads finden (Firmen + Ansprechpartner beschaffen)
- KI-Personalisierung (pro Lead recherchieren, Anschreiben + Follow-ups texten)
- Versand + Follow-ups (Zustellbarkeit, Sequenzen)

Bewusst nicht in v1: Antworten-Erkennung/Einsortierung, Reporting an Kunden.
(Abmeldungen und unzustellbare Adressen behandelt das Versand-Tool trotzdem
von Anfang an — das ist Grundhygiene, kein Reporting.)

## Erfolgskriterium v1

Ein kompletter technischer Durchlauf mit Testdaten: Zielgruppe rein,
personalisierte Sequenz geht automatisch raus, Nachweis wie unter
"Test & Nachweis" beschrieben. Antwortquoten sind für v1 zweitrangig.

## Gewählter Weg (Ergebnis des Sparrings)

Weg "Baukasten": Die Zustellbarkeit (Warmup, Postfach-Rotation, Sequenzen,
Bounce-Handling) wird bei einem spezialisierten Versand-Tool zugekauft.
Selbst gebaut wird die Schicht, die das Angebot ausmacht: Lead-Beschaffung
aus mehreren Quellen und KI-Personalisierung.

Verworfene Alternativen:
- Ein-Tool-Weg (alles z.B. in Instantly): kaum Differenzierung, im Grunde
  Wiederverkauf.
- Alles selbst bauen (eigene Versand-Infrastruktur): Monate Aufwand,
  Zustellbarkeits-Risiko; kann später kommen, wenn Tool-Kosten drücken.

## Bausteine

1. **Lead-Schicht (mehrere Quellen).** Apollo ist gesetzt; weitere Quellen
   können andocken (Kandidaten je nach Zielgruppe: Dealfront, Cognism,
   Apify-Scraper, Hunter — Auswahl in der Plan-Phase). Drei feste Regeln:
   - Alle Quellen liefern ins gleiche einheitliche Lead-Format.
   - Dubletten werden aussortiert, auch gegen frühere Kampagnen desselben
     Kunden.
   - Jede E-Mail-Adresse wird vor Verwendung verifiziert.
2. **KI-Schicht.** Nimmt jeden Lead, holt die Firmen-Webseite, schreibt
   daraus Aufhänger, Anschreiben und 2–3 Follow-up-Texte. Das KI-Modell ist
   eine Einstellung, keine Festlegung (Vergleichstest in der Bau-Phase).
   Die Prompts sind das Herzstück des Produkts und liegen versioniert im
   Projektordner. Ein automatischer Prüfschritt bewertet jeden Text;
   Durchgefallenes landet in einer Nacharbeit-Liste.
3. **Versand-Schicht (zugekauft).** Smartlead oder Instantly, angesteuert
   per API. Entscheidung in der Plan-Phase anhand aktueller Fakten:
   API-Umfang, Trennung der Kunden (Workspaces), Warmup, Preis.
4. **Kunden-Konfiguration.** Eine Konfigurationsdatei je Kunde: Zielgruppe
   (Branche, Größe, Region, Rolle), Angebot, Tonalität, Absender. Neuer
   Kunde = Datei anlegen, Postfächer einrichten, gleiche Flows laufen lassen.

Orchestrierung (was die Bausteine verbindet): Activepieces oder ein kleines
Skript — Entscheidung in der Plan-Phase, je nachdem was mit den APIs der
gewählten Tools einfacher und wartbarer ist.

## Datenfluss

1. **Zielgruppe rein:** Konfigurationsdatei des Kunden.
2. **Leads beschaffen:** Quellen abfragen → einheitliches Format → Dubletten
   raus → Adressen verifizieren → saubere Lead-Liste (als Datei abgelegt).
3. **Personalisieren:** Pro Lead Webseite holen, KI textet, automatische
   Qualitätsprüfung, am Anfang zusätzlich Stichprobe von Hand.
4. **Freigabe:** Ohne ausdrückliche Freigabe durch den Menschen geht nichts
   raus. Fest eingebaut, pro Kampagne.
5. **Versand:** Kampagne, Leads und Texte gehen per API ans Versand-Tool;
   das verteilt auf Postfächer, versendet zeitversetzt, fasst nach und
   behandelt Abmeldungen/Bounces.

## Fehlerbehandlung

- Jeder Baustein legt sein Ergebnis zwischen ab; nach einem Abbruch geht es
  ab dem fehlgeschlagenen Schritt weiter, nicht von vorn.
- Fällt eine Lead-Quelle aus oder bremst (API-Limits): Wiederholversuche mit
  Wartezeit; andere Quellen laufen weiter; die Lücke steht im Bericht.
- Unbrauchbarer KI-Text: in die Nacharbeit-Liste, nie ungeprüft raus.
- Nichts wird still verschluckt: Jeder Lauf endet mit einem Bericht —
  gefunden / verworfen (mit Grund) / verifiziert / personalisiert /
  Nacharbeit.

## Test & Nachweis

Niemals mit echten Empfängern testen. Stattdessen:

- Erfundener Test-Kunde ("Demo GmbH") mit eigener Konfigurationsdatei.
- Lead-Liste nur aus eigens angelegten Test-Postfächern (Gmail, Outlook,
  eigene Domain), damit verschiedene Empfänger-Systeme sichtbar sind.
- Kompletter Durchlauf über eine reine Test-Domain, inklusive Freigabe-Schritt.
- Bewiesen, wenn: Mails kommen in den Test-Postfächern an (Posteingang,
  nicht Spam), Follow-up kommt zeitversetzt, Bericht stimmt mit der
  Realität überein.

Erst danach echte Empfänger — und das pro Kampagne wieder nur mit Freigabe.

## Rechtlicher Rahmen (Hinweis, keine Rechtsberatung)

Kalt-E-Mails an Firmen sind in Deutschland rechtlich enger gefasst als z.B.
in den USA (UWG). Das Abmelde-Handling des Versand-Tools ist von Anfang an
eingebaut. Ob und wie das System pro Kunde und Zielmarkt eingesetzt wird,
ist eine Geschäftsentscheidung des Betreibers; für die Feinheiten ist ein
Anwalt der richtige Ansprechpartner.

## In der Plan-Phase zu klären

- Versand-Tool: Smartlead vs. Instantly (Kriterien: API-Umfang,
  Kunden-Trennung, Warmup, Preis).
- Lead-Quellen neben Apollo: welche lohnen sich für die ersten Zielgruppen
  (Kosten/Nutzen, DACH-Abdeckung).
- E-Mail-Verifizierung: im Versand-Tool eingebaut nutzen oder eigener Dienst.
- Orchestrierung: Activepieces vs. kleines Skript.
- KI-Modell: Vergleichstest mit denselben Beispiel-Leads (in der Bau-Phase).

## Projektstruktur (geplant)

```
AI Coldmailing system/
├── project-context.md          # Stand, Entscheidungen, nächste Schritte
├── docs/superpowers/specs/     # Design-Dokumente (dieses hier)
├── kunden/                     # eine Konfigurationsdatei je Kunde
├── prompts/                    # die KI-Prompts, versioniert
└── flows/                      # Activepieces-Flows bzw. Skripte
```

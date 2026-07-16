# Projekt: AI Coldmailing System

## Worum es geht
Ein wiederverwendbares KI-Coldmailing-System als eigenes Angebot/Produkt —
einsetzbar bei mehreren Kunden. Hintergrund laut interner Notiz (16.07.2026):
Das Team bezieht diese Leistung derzeit von Wholix (wholix.ai) und will sie
intern selbst abbilden. Der erste echte "Kunde" im System ist also das
eigene Unternehmen; danach wird es Kunden angeboten.

Umfang der ersten Version (v1):
- Leads finden (Firmen + Ansprechpartner beschaffen)
- KI-Personalisierung (pro Lead recherchieren, individuelles Anschreiben texten)
- Versand + Follow-ups (Zustellbarkeit, Sequenzen)

Bewusst NICHT in v1: Antworten-Erkennung/Einsortierung, Reporting.

## Rahmenbedingungen
- Grüne Wiese: keine Lead-Datenbank, kein Versand-Tool, keine
  Outreach-Domains/Postfächer vorhanden.
- Erfolgskriterium v1: kompletter technischer Durchlauf — Zielgruppe rein,
  personalisierte Sequenz geht automatisch raus. Antwortquoten sind für v1
  zweitrangig.
- Test niemals mit echten Empfängern: Nachweis mit Testdaten und eigens
  angelegten Test-Postfächern.

## Aktueller Stand
- Verstehen, Sparring und Design abgeschlossen; Design von Leonard
  freigegeben (16.07.2026):
  docs/superpowers/specs/2026-07-16-ai-coldmailing-system-design.md
- Werkzeug-Entscheidungen getroffen (siehe unten), Umsetzungsplan
  geschrieben: docs/superpowers/plans/2026-07-16-ai-coldmailing-system.md
- Jira-Aufgabe: AP-195 (digitaldiamonds.atlassian.net)
- Freigabe des Umsetzungsplans durch Leonard steht aus.

## Entscheidungen
- v1-Umfang: Leads + Personalisierung + Versand/Follow-ups (siehe oben).
- Erfolgskriterium: technischer End-zu-End-Durchlauf.
- Lösungsweg: Baukasten — fertiges Versand-Tool für Zustellbarkeit +
  eigene KI-Schicht für Recherche und Personalisierung.
  Alternativen (Ein-Tool-Weg, alles selbst bauen) bewusst verworfen:
  zu wenig Differenzierung bzw. zu langsam/riskant für v1.
- Versand-Tool: Instantly — das Team bezahlt es bereits und nutzt es
  (Vorgabe vom Chef, 16.07.2026). Offen: hat der Team-Tarif API-v2-Zugang?
- Lead-Quelle v1: nur Apollo; Architektur bleibt mehrquellenfähig.
- E-Mail-Verifizierung: eingebaute Prüfung von Instantly (Leonard hat die
  Detail-Entscheidung delegiert); externer Dienst nur bei Bedarf später.
- Verbindung der Bausteine: kleines Python-Skript statt Activepieces-Flows
  (viel Logik, wartbarer als Skript; Activepieces ggf. später für Trigger).
- KI-Modell: bleibt Einstellung (Standard claude-sonnet-5), Vergleichstest
  in der Bau-Phase.

## Nächste Schritte
- Lösungsweg wählen (Sparring).
- Danach: Plan erstellen, vom Menschen freigeben lassen, bauen.

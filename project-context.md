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
- v1 KOMPLETT GEBAUT und nach main gemergt (16.07.2026): Pipeline-Pakete
  1–10 plus Härtungs-Pass, 62 automatische Tests, alle grün. Abschluss-
  Review über den ganzen Bau: bestanden, keine Blocker.
- Bedienung: `python -m pipeline lauf|freigeben|senden`, Angebots-Analyse
  über `python -m pipeline.offer <url> <kunde.yaml>`. API-Schlüssel über
  .env (Vorlage: .env.example).
- Design: docs/superpowers/specs/2026-07-16-ai-coldmailing-system-design.md
- Plan (mit allen Nachträgen): docs/superpowers/plans/2026-07-16-ai-coldmailing-system.md
- Jira-Aufgabe: AP-195 (digitaldiamonds.atlassian.net)
- Wholix-Analyse (Screenshots + HAR-Mitschnitt app.wholix.ai.har, liegt
  lokal, per .gitignore vom Git ausgeschlossen — enthält Sitzungsdaten):
  bestätigte den Bauplan; daraus nachgezogen: Domain-Sperrliste,
  Schutz-Voreinstellungen (20 Mails/Tag, Fenster Mo–Fr 8–19).
- OFFEN: Task 11 (End-zu-End-Nachweis) — braucht von Leonard: Okay für
  Test-Domain-Kauf (~10–15 €/Jahr), Test-Postfächer, Apollo-Konto (gratis
  reicht), Anthropic-API-Schlüssel, Instantly-Zugang (wer hat den
  API-Schlüssel? enthält der Team-Tarif API v2?) und Okay für den ersten
  Schreibzugriff aufs Team-Instantly.
- Am echten Konto zu verifizieren (TODOs im Code markiert): Instantly
  Zeitzonen-Ersatz Europe/Belgrade, Wochentags-Konvention, daily_limit
  pro Postfach, Lead-Dedupe bei Wiederholungs-Import; Apollo id-only-Match
  und Credit-Verhalten von reveal_personal_emails.
- Für v1.1 vor der ersten ECHTEN Kampagne (nicht vor Task 11): Prüf-KI
  soll auch Follow-ups bewerten; Freigabe-Vorschau zeigt alle Texte oder
  verweist ausdrücklich auf personalisierung.json. Für v2: Antworten-
  Behandlung (echte Antworten vs. Abwesenheit/Unzustellbar).

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

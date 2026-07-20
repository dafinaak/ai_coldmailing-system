# Projekt: AI Coldmailing System

## Nordstern (geklärt 20.07.2026)
Das Tool wird INTERN genutzt (nicht für externe Kunden) und soll Wholix
1:1 ersetzen: EINE eigene Plattform fürs Team, die alles kann, was Wholix
kann — mit Instantly als unsichtbarem Motor darunter (Versand, Anwärmen,
Zustellbarkeit; bewusst zugekauft, NICHT selbst gebaut). Der Wholix-Account
dient nur als Vorlage zum Nachbauen. "1:1 für den Nutzer, Motor bleibt
Instantly" — nicht den Versand-Motor selbst nachbauen (Monate + Spam-Risiko).
Begriff "Kunde" → "Angebot" umbenannt (interne Setups, keine echten Kunden).
Noch zum vollen Wholix-Ersatz fehlend (Fahrplan folgt): volles Postfach
(Antworten lesen+schreiben im Tool), Kampagne im Tool scharf schalten,
Postfach-Anbindung/Anwärm-Status, CRM-Rand (Anrufe/Notizen/AI-Chat).

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
- Instantly-API-Schlüssel liegt vor (17.07.2026, in .env) und ist
  VERIFIZIERT: API v2 antwortet (rein lesende Prüfung) — der Team-Tarif
  enthält die API, größtes Restrisiko damit ausgeräumt. Im Team-Konto:
  10 verbundene Postfächer auf 10 Outreach-Domains, 8 mit aktivem Warmup.
- Subdomain mailingsystem.polepositionautomation.de wurde von Leonard
  angelegt (A-Record auf 178.104.175.42). Für den Endnachweis vermutlich
  nicht nötig (vorhandene warme Postfächer nutzbar; neues Postfach müsste
  erst wochenlang anwärmen) — Entscheidung Leonards steht aus.
- Task 11 GESTARTET und fast durch (17.07.2026): Echter Lauf gefahren
  (3 Apollo-Leads mit E-Mail, 2 ohne — im Bericht gezählt), Empfänger auf
  Leonards 3 Test-Adressen umgebogen (--neu-ab dedupe), alle 3 Texte
  personalisiert und von Leonard freigegeben. Pausierte Kampagne
  "[TEST] Demo GmbH" (ID 580bdbf7-fe41-43d4-b07d-8460997925f8) im
  Team-Instantly angelegt und rein lesend verifiziert: Status Entwurf,
  daily_limit 20, Fenster Mo–Fr 8–19 (Wochentags-Konvention und
  Zeitzonen-Ersatz Europe/Belgrade am echten Konto BESTÄTIGT),
  3 Leads mit personalisierten Variablen.
- Unterwegs gefunden und behoben: KI-Token-Budget 1500 war zu knapp
  (Denk-Tokens schnitten Antworten ab) -> 4000; senden-Tests von der
  Demo-Kundendatei entkoppelt. 69 Tests grün.
- BEWEISPROTOKOLL End-zu-End-Test (17.07.2026):
  - Kampagne von Leonard aktiviert (Absender email@poleposition-automation.online).
  - Versand belegt per Instantly-Historie: Mail 1 an Gmail 08:51 UTC,
    an digitaldiamonds 09:09 UTC; Follow-ups 09:00/09:18 UTC.
  - ZUSTELLUNG BESTÄTIGT durch Leonard: Gmail und digitaldiamonds
    (Microsoft) beide im POSTEINGANG, nicht im Spam.
  - IONOS: erste Adresse war ein Tippfehler (Domain existierte nicht —
    niemand hat etwas erhalten; Empfänger in der Kampagne ausgetauscht,
    Konfiguration korrigiert). Korrigierte Adresse
    l.luzhnica@polepositionsolutions.de: ZUGESTELLT IM POSTEINGANG
    (bestätigt von Leonard, 17.07.2026).
  - ERGEBNIS: v1-Erfolgskriterium erfüllt — kompletter Durchlauf von
    Zielgruppe bis Posteingang bei allen drei Anbietern (Gmail,
    Microsoft, IONOS), keine Mail im Spam. Jira AP-195 abgeschlossen.
  - ECHTER FUND durch den Test: Instantly zählt Schritt-Wartezeiten
    NACH dem Schritt, nicht davor -> Follow-ups gingen nach Minuten
    statt Tagen raus (nur an Leonards eigene Adressen, kein Schaden).
    Behoben in Commit ef28ba9 (72 Tests); korrekte Tages-Abstände beim
    nächsten Echtlauf live nachverifizieren.
  - Noch offen für den Abschluss: IONOS-Zustellung bestätigen, dann
    Jira AP-195 auf erledigt.
- Für v1.1 zusätzlich vorgemerkt: Nachnamen-Schreibweise darf die KI
  nicht "korrigieren" (Fall "Boedoecs" statt "Bodocs" im Testlauf);
  kunde_name vs. Absender-Firma sauber trennen (Demo GmbH/Digital
  Diamonds gemischt in Mail 1).
- Apollo-API-Schlüssel liegt vor (16.07.2026), gespeichert in .env
  (gitignored — Schlüssel stehen nie im Repo oder in Notizen).
- Text-KI läuft über OpenRouter: Schlüssel in .env, LÄUFT ca. 23.07.2026 AB
  (Endnachweis vorher fahren oder neuen Schlüssel holen). KI-Baustein hat
  jetzt eine Anbieter-Weiche (OpenRouter vor Anthropic), per Echt-Aufruf
  bewiesen (Modell anthropic/claude-sonnet-5 antwortet). 69 Tests grün.
- Versand-Domain für den Test: Subdomain der eigenen Firmen-Domain
  (Leonard kann DNS-Einträge anlegen; welche Domain und welcher
  DNS-/Mail-Anbieter, ist noch offen). Für echte Kampagnen später:
  separate Domain kaufen (so macht es auch Wholix), damit der Ruf der
  Hauptdomain geschützt bleibt.
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
- TEAM-INTERFACE: GEBAUT, GEPRÜFT, DEPLOYED (20.07.2026).
  - Alle 9 Bau-Pakete + Abschluss-Review + Fix-Wave: 280 Tests grün,
    nach main gemergt (Merge 2149b42). Abschluss-Reviewer: "Ready to
    merge: Yes" nach verifizierten Fixes (u.a. bewiesener
    Kundensperren-Bug, Instantly-Cache in Produktion, blockierende
    Routen, Produktions-Einstiegspunkt web/main.py).
  - LIVE unter https://mailingsystem.polepositionautomation.de
    (Cloudflare → ci-nginx [Template mailingsystem.conf.template,
    Container-Neustart nötig statt reload!] → Container coldmail-web
    auf prod-srv01-automations; Code /opt/coldmailing/app, Daten-Volume
    /opt/coldmailing/daten, Schlüssel via compose env_file
    /opt/coldmailing/.env — nie im Image).
  - Smoke bestanden: /health 200 übers Internet, Login-Seite korrekt,
    echter Mini-Lauf (limit 1) im Container: Apollo+KI erreicht,
    Laufordner+Bericht geschrieben, Stopp vor Freigabe.
  - Erstzugang: Nutzer "Leonard", Passwort in
    /opt/coldmailing/ERSTZUGANG.txt auf dem Server (chmod 600) — nach
    erstem Login löschen. Weitere Team-Nutzer: users.yaml in
    /opt/coldmailing/daten (Hash-Einzeiler in deploy/DEPLOY.md).
- OFFEN: IF-Task 11 Abnahme = Kollegen-Test (Termin von Leonard);
  Backlog aus Abschluss-Review in .superpowers/sdd/progress.md.
- Parallel offen: v1.1 vor erster echter Kampagne, neuer
  OpenRouter-Schlüssel nach dem 23.07., Instantly-Status-Mapping am
  echten Konto verifizieren.

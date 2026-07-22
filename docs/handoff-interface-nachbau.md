# Übergabe-Prompt: Wholix-Interface nachbauen

> Diesen Text einem frischen Agenten geben. Er hat Zugriff auf dieses
> Repository, aber NICHT auf den Gesprächsverlauf, in dem der Auftrag
> entstanden ist. Alles Nötige steht hier oder in den verlinkten Dateien.

---

## Deine Rolle und dein Ziel

Du baust das interne Web-Interface eines KI-Kaltmail-Systems zu einer
**optischen und funktionalen Kopie von Wholix** aus (wholix.ai). Das Tool
wird intern vom Team benutzt; **Instantly** bleibt der unsichtbare
Versand-Motor darunter (schon bezahlt, läuft — NICHT nachbauen).

Der Daten-Motor (Firmen finden, Entscheider finden, Mails bauen/prüfen,
Texte schreiben) ist bereits gebaut und getestet. **Dein Auftrag ist die
Oberfläche**, nicht der Motor.

## Zuerst lesen (verbindlich, in dieser Reihenfolge)

1. `AGENTS.md` — Projekt-Regeln. Vor allem: **Zuverlässigkeit zuerst** und
   **Interface = Wholix-Nachbau**. Diese Regeln überschreiben deine
   Standard-Gewohnheiten.
2. `docs/wholix-nachbau-roadmap.md` — die Feature-Inventur (43 Funktionen),
   der Abschnitt **"Scope-Entscheidungen (22.07.2026)"** (was gebaut wird
   und was NICHT), die Architektur-Entscheidung, und der **Bau-Fahrplan in
   Phasen**. Das ist dein wichtigstes Dokument.
3. `~/.claude/CLAUDE.md` (globale Nutzer-Regeln, falls vorhanden) — Sprache
   und Arbeitsweise des Nutzers.

## Verbindliche Regeln (aus den obigen Dateien, hier zusammengefasst)

- **Sprache:** Alles, was der Nutzer oder das Team sieht (Oberfläche,
  Texte, Erklärungen, deine Antworten), ist **Deutsch, einfache
  Alltagssprache** — keine Fachwörter, keine Fremdwörter, keine
  Ausrufezeichen, kein Werbe-Ton. Das Team ist teils nicht-technisch; jede
  Beschriftung muss ein kompletter Anfänger verstehen.
- **Zuverlässigkeit vor allem.** Baue nichts Wackeliges. Teste alles.
- **"Fertig" heißt: gebaut UND bewiesen.** Für Optisches: Screenshot oder
  Live-Demo. Nie nur "fertig" behaupten.
- **Nach außen wirkende Schritte nur mit kurzer Freigabe des Nutzers:**
  echte Postfächer verbinden, echte Mails senden, Produktion ändern, Geld
  ausgeben. Innerhalb des Projektordners: frei arbeiten.
- **Nie in Produktion testen.** Für alles, was Mails betrifft:
  Test-Postfächer und Test-Empfänger benutzen (im Repo gibt es dafür
  Muster, siehe `kunden/demo-gmbh.yaml`).
- **Vorgehen:** verstehen → 2–3 Lösungswege mit Abwägung vorschlagen → der
  Nutzer entscheidet → Plan → in kleinen, prüfbaren Schritten bauen.
  Entscheide den Lösungsweg nie allein.

## Der Auftrag: Wholix-Interface nachbauen

**Umfang:** Der Funktionsumfang laut `docs/wholix-nachbau-roadmap.md`,
MINUS der im Abschnitt "Scope-Entscheidungen" gestrichenen 9 Funktionen.
Von 43 bleiben **34**. Nicht gestrichene Blöcke, die noch fehlen: die
Kampagnen-Ansicht auf Wholix-Stand, die Freigabe-Tabelle, das **volle
Mail-Programm**, das **CRM mit Verkaufs-Stufen**, Leads bearbeiten.

**Design-Ziel:** Die Oberfläche soll **aussehen und sich bedienen wie
Wholix**. Vorlagen: die 10 Bildschirmfotos im Ordner
`~/Desktop/wholix interface screenshots` und der Netzwerk-Mitschnitt
`app.wholix.ai.har` (zeigt, welche Daten Wholix im Hintergrund holt — vor
allem für den E-Mail-Bereich).

**Bestätigte Architektur-Entscheidung: Weg A.** Für das volle
Mail-Programm werden die Postfächer **zusätzlich direkt** mit unserem Tool
verbunden (Google-/Microsoft-Anmeldung, einmal pro Postfach), damit das
Tool das komplette Postfach lesen und darauf antworten/schreiben kann.
**Instantly bleibt der Versand-Motor** (Kampagnen + Anwärmen). Den Versand
NICHT selbst nachbauen. Das direkte Postfach-Anbinden ist neue Arbeit:
erst mit einem **Test-Postfach** beweisen, bevor echte Postfächer dran
kommen — und für echte Postfächer vorher die Freigabe des Nutzers holen.

## Empfohlene Bau-Reihenfolge (schnellster sichtbarer Wholix-Look zuerst)

1. **Kampagnen-Ansicht auf Wholix-Stand** (Fahrplan Phase 1) — fehlende
   Kacheln (geöffnet / fehlgeschlagen / unzustellbar), Tages-Limit +
   Sendefenster, Warteschlangen-Status. Alles aus Instantly-Daten, kein
   Blocker, schnell sichtbar.
2. **Freigabe-Tabelle auf Wholix-Stand** (Phase 2).
3. **Das Mail-Programm** (Phase 3, der große Brocken, braucht Weg A) und
   **das CRM mit Stufen** (Phase 4).

Nach jeder sichtbaren Einheit dem Nutzer einen Screenshot/eine Demo zeigen.

## Technische Landkarte

- **Web-Oberfläche:** `web/` — FastAPI + Jinja2. Routen in `web/routen/`,
  Vorlagen in `web/templates/`, Layout in `web/templates/layout.html`,
  Navigation in `web/nav.py`. Einstieg `web/main.py` / `web/app.py`.
- **Instantly lesen (nur lesend, gecacht):** `web/instantly_leser.py`.
  Was über die Instantly-API geht und was nicht, steht in
  `docs/instantly-api-machbarkeit.md` und
  `docs/instantly-leadsuche-machbarkeit.md`. **Wichtig:** Instantly kennt
  nur den Kampagnen-Verkehr — das komplette Postfach (Ordner, Junk,
  Entwürfe) geht nur über die direkte Postfach-Anbindung (Weg A).
- **Läufe starten/überwachen:** `web/laufmanager.py` (startet die Pipeline
  als Unterprozess, liest den Fortschritt). Fortschrittsseite
  `web/templates/auftrag_fortschritt.html`.
- **Daten-Motor (nicht dein Fokus, aber gut zu kennen):** `pipeline/` —
  `sourcing.py` (Apify → Hunter → Dropcontact → info@), `personalize.py`
  (Texte + Nachbesserungs-Schleife), `quality.py` (Prüfer), Quellen in
  `pipeline/sources/`. Er liefert die Leads/Kampagnen, die dein Interface
  anzeigt.
- **Deployment:** `deploy/` (Docker auf Hetzner hinter geteiltem nginx),
  `deploy/DEPLOY.md`. Zugänge über `.env` (siehe `.env.example`).

## So arbeitest du im Repo

- **Tests:** Python-Suite mit pytest. Vor und nach jeder Änderung grün
  halten:
  `source .venv/bin/activate && python -m pytest -q`
  (Aktueller Stand: 428 Tests grün.) Für neue Oberflächen-Logik Tests
  ergänzen (die Web-Tests liegen in `tests/web/`).
- **Git:** auf einem eigenen Branch arbeiten (nicht direkt auf `main`),
  kleine nachvollziehbare Commits. Commit-Nachrichten und alles im
  Team-Jira in klarem Deutsch/Englisch, das nicht-technische Leute
  verstehen.
- **Dokumentieren:** Größere Deliverables kommen ins Jira des Teams
  (Projekt `AP`, siehe globale Regeln). Für Zwischenstände die Roadmap
  aktualisieren.

## Was du NICHT tust

- Den Versand oder das Anwärmen nachbauen — das macht Instantly.
- Die gestrichenen 9 Funktionen bauen (siehe Scope-Entscheidungen).
- Den Daten-Motor (`pipeline/`) umbauen — er ist fertig und getestet.
- Echte Postfächer verbinden oder echte Mails senden, ohne vorher den
  Nutzer zu fragen und mit einem Test-Postfach zu beweisen.

## Randnotiz (nicht dein Baustellen-Teil)

Der Daten-Motor läuft technisch, wartet aber auf eine Budget-Bestätigung
des Chefs für die bezahlten Zugänge (Hunter/Dropcontact). Das betrifft nur
echte Lead-Läufe, nicht den Interface-Bau: die Oberfläche kannst du mit
den vorhandenen Instantly-Daten und Test-Daten voll entwickeln. Details in
`docs/datenquellen-strategie.md`.

## Dein erster Schritt

Lies die drei Pflicht-Dateien, dann melde dich beim Nutzer mit einem
kurzen Plan für **Phase 1** (Kampagnen-Ansicht auf Wholix-Stand): welche
Kacheln/Ansichten du in welcher Reihenfolge baust und wie du das Ergebnis
zeigst. Baue erst nach seinem Okay.

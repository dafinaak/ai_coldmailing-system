# Umsetzungsplan: Team-Interface (Poleposition)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox syntax. Besonderheit dieses Plans: Für Seiten-Markup ist die eingefrorene Design-Vorlage `docs/design/Poleposition-v4.dc.html` die Quelle (Struktur, Zustände, Texte) zusammen mit `docs/text-leitfaden-interface.md` — Markup wird daraus abgeleitet statt hier dupliziert. Logik-Code steht wie gewohnt im Plan.

**Ziel:** Die bestehende, geprüfte Pipeline für das ganze Team im Browser bedienbar machen — Wholix-artige Struktur mit sieben Bereichen, erreichbar unter https://mailingsystem.polepositionautomation.de.

**Architektur:** FastAPI + Jinja2-Templates (server-gerendert, Fortschritt per Polling), gleiche Codebasis wie die Pipeline (importiert deren Module direkt). Läufe starten als Unterprozesse des bestehenden CLI; der Web-Teil liest denselben Laufordner-Zustand, den die Pipeline schreibt (keine neue Datenhaltung, keine Queue). Deployment als eigener Docker-Container auf dem Arbeitsserver (Hetzner, `prod-srv01-automations`), hinter dem vorhandenen nginx mit neuem Server-Block; Daten (kunden/, laeufe/, globale Sperrliste, users) in einem Volume.

**Tech-Stack:** Python 3.11, FastAPI, uvicorn, Jinja2, itsdangerous (Session-Cookie), passlib[bcrypt] (Passwort-Hashes), pytest + httpx (Route-Tests). Kein JS-Framework; kleine Vanilla-JS-Stücke nur für Polling und Checkliste.

**Design-Grundlage:** docs/superpowers/specs/2026-07-17-team-interface-design.md (eingefroren 17.07.2026).

## Globale Regeln

- Alle Sicherheitsregeln der Pipeline bleiben unangetastet: Freigabe-Pflicht, Test-Adressen-Sperre, Kampagnen entstehen pausiert. Die Web-Schicht ruft die bestehenden Module — sie umgeht sie nie.
- Alle sichtbaren Texte wörtlich aus docs/text-leitfaden-interface.md bzw. der v4-Vorlage. Keine neuen Formulierungen ohne Leitfaden-Prüffrage.
- Jede Route (außer /login, /health) verlangt Anmeldung. Freigaben speichern den Namen der angemeldeten Person.
- Schreibende Aktionen nur per POST; jede Seite rendert auch leere/Fehler-Zustände (siehe v4).
- Keine echten API-Aufrufe in Tests (Instantly/Apollo/KI gefaked); Web-Tests treiben die Routen mit httpx gegen die App mit tmp-Datenverzeichnis.
- Jeder Task endet mit grünem `pytest` und einem Commit.
- Deployment-Schreibzugriffe auf den Server sind von Leonard freigegeben (17.07.2026, "kann da drauf deployed werden"); trotzdem: vor Eingriffen an geteilter Infrastruktur (nginx-Konfig, Docker-Aufräumen) kurze Ankündigung im Chat.

## Risiken und offene Fragen

1. **Server-Platte war im Mai zu 84 % voll.** Task 10 prüft zuerst live und räumt (laut Server-Doku empfohlen) Docker-Build-Cache auf. Ohne Platz kein Deploy.
2. **Instantly-API-Umfang für Postfach/Statistiken** (emails-Liste, Antworten, analytics) ist am echten Konto nur teilweise verifiziert — Tasks 6/9 beginnen mit Live-Doku/Read-only-Probe und passen Felder an.
3. **Nebenläufigkeit:** mehrere Nutzer gleichzeitig. v1-Ansatz: ein uvicorn-Prozess, Datei-basierte Zustände, einfache Sperrdatei pro Kunde gegen parallele Läufe desselben Kunden. Kein verteiltes Locking.
4. **Secrets:** .env auf dem Server (wie beim ViralLab-Stack), nie im Repo/Image.
5. **Kollegen-Test** (Erfolgskriterium) braucht einen echten Kollegen — Termin von Leonard.

---

### Task 1: Web-Gerüst mit Anmeldung

**Files:** Create: `web/__init__.py`, `web/app.py` (FastAPI-Factory `create_app(daten_dir)`), `web/auth.py`, `web/templates/layout.html` + `login.html`, `web/static/stil.css` (aus v4 abgeleitet), `users.yaml.example`, `tests/web/test_auth.py`
**Interfaces:** `create_app(daten_dir: Path) -> FastAPI`; `users.yaml`: Liste `{name, passwort_hash}`; Session-Cookie signiert (Secret aus env `WEB_SECRET`); `web.auth.aktueller_nutzer(request) -> str | None`; Redirect auf /login wenn nicht angemeldet; Logout.
TDD: unangemeldet → 303 auf /login; falsches Passwort → Fehlermeldung; korrekt → Cookie, Name im Layout sichtbar; /health ohne Login 200. Layout: Seitenleiste mit den sieben Bereichen + Badge-Platzhalter (aus v4).

### Task 2: Globale Sperrliste (Backend + Seite)

**Files:** Create: `web/routen/sperrliste.py`, `web/templates/sperrliste.html`, `tests/web/test_sperrliste.py`; Modify: `pipeline/dedupe.py` + `pipeline/__main__.py` (globale Liste mitlesen), `tests/test_dedupe.py`
**Interfaces:** Datei `daten_dir/sperrliste-global.yaml` (Liste von Domains, Wildcard wie gehabt). `dedupe(..., sperrliste=...)` bekommt vom Aufrufer die VEREINIGUNG aus globaler + Kunden-Liste (Zusammenführung in `__main__.lauf` und im Web-Aufrufer, Helfer `lade_globale_sperrliste(daten_dir)` in `pipeline/config.py`). Seite: Liste anzeigen, Domain hinzufügen/entfernen (POST), Hilfssätze aus Leitfaden.
TDD: Pipeline-Test — Lead mit global gesperrter Domain fliegt raus, auch wenn Kunden-Liste leer; Web-Test — hinzufügen/entfernen ändert Datei; Anzeige beider Ebenen.

### Task 3: Kunden-Bereich

**Files:** Create: `web/routen/kunden.py`, `web/templates/kunden_liste.html` + `kunde_form.html`, `tests/web/test_kunden.py`
**Interfaces:** Liste aus `daten_dir/kunden/*.yaml` (load_kunde); Formular mit allen Feldern + Hilfssätzen (v4/Leitfaden); Speichern validiert über `load_kunde`-Regeln und schreibt YAML (Muster aus pipeline/offer.uebernehmen: safe_dump, nur bekannte Felder); Knopf "Angebot automatisch von der Firmen-Webseite ableiten" ruft `pipeline.offer.draft_offer` (KI gefaked in Tests) und füllt nur leere Felder, Badge "VORSCHLAG VON DER WEBSEITE".
TDD: anlegen → Datei entsteht und lädt; Pflichtfeld fehlt → Formular-Fehlertext; Ableiten überschreibt Handeingabe nicht.

### Task 4: Aufträge starten + Hintergrund-Runner + Fortschritt

**Files:** Create: `web/laufmanager.py`, `web/routen/auftraege.py`, `web/templates/auftrag_neu.html` + `auftrag_fortschritt.html`, `tests/web/test_laufmanager.py`
**Interfaces:** `Laufmanager(daten_dir)` mit `starte(kunde_pfad, limit) -> lauf_dir` (Unterprozess `python -m pipeline lauf … `, stdout/stderr → `lauf_dir/lauf.log`, PID-Datei; Sperrdatei je Kunde verhindert Parallel-Lauf desselben Kunden), `setze_fort(lauf_dir)`, `status(lauf_dir) -> dict` (aus step_done-Dateien + Prozess-lebt + lauf.log: Zustände laeuft/angehalten/wartet_auf_freigabe/uebergeben/fertig; Fehlermeldung in Laiensprache per Muster-Zuordnung bekannter Fehlertexte, sonst generischer 3-Teile-Text). Fortschrittsseite pollt alle 3 s (fetch auf JSON-Route), zeigt die 5 Schritte aus dem Leitfaden.
TDD: mit gefaktem Pipeline-Aufruf (Skript, das Step-Dateien schreibt und schläft) — Status wechselt korrekt; Absturz → angehalten + Fortsetzen startet mit --fortsetzen; Doppel-Start desselben Kunden → verweigert mit verständlichem Text.
**PFLICHT-PRÜFPUNKT (aus Task-2-Review, 17.07.2026):** Der Unterprozess MUSS mit `cwd=daten_dir` gestartet werden — sonst liest `lade_globale_sperrliste(Path("."))` im falschen Verzeichnis und die globale Sperrliste fällt LEISE aus (fehlende Datei ergibt absichtlich []). Zwei Tests sind Pflicht: (a) Assertion, dass der Unterprozess mit cwd=daten_dir gestartet wird; (b) Integrationstest, der beweist, dass die globale Sperrliste greift, wenn daten_dir ungleich Code-Verzeichnis ist.

### Task 5: Prüfen & Freigeben

**Files:** Create: `web/routen/freigabe.py`, `web/templates/freigabe_liste.html` + `freigabe_lesen.html`, `tests/web/test_freigabe.py`; Modify: `pipeline/approval.py` (approve bekommt `name: str`, schreibt ihn in FREIGABE.txt; is_approved unverändert), `tests/test_approval.py`
**Interfaces:** Wartend = Läufe mit `pruefung_ok` vorhanden, nicht freigegeben, nicht übergeben. Lese-Ansicht: Empfängerliste links (Name/Firma/E-Mail, gelesen-Häkchen clientseitig), rechts Volltexte (Betreff, Anschreiben, Nachfass 1+2 mit echten Tages-Abständen aus der Kunden-Konfig). Aussortierte mit Grund UND aufklappbarem Volltext (aus personalisierung.json nacharbeit — Task erweitert die dortige Ablage um den abgelehnten Text, kleine Pipeline-Anpassung + Test). Freigeben = Checkliste (3 Punkte) → Knopf aktiv → POST: `approve(store, name)` + direkt `senden`-Logik der Pipeline (Kampagne pausiert anlegen); Ergebnis-Ansicht "liegt jetzt pausiert in Instantly" + Link. Ablehnen: Pflicht-Begründung, gespeichert als `abgelehnt.json` (wer/wann/warum), Lauf gilt als erledigt-abgelehnt.
TDD: Freigabe ohne alle Häkchen → 400; mit → FREIGABE.txt enthält Name, Instantly-Fake bekommt Kampagne; Test-Adressen-Sperre der Pipeline greift weiterhin (Fake-Lead mit fremder Adresse → Fehltext sichtbar, nichts gesendet); Ablehnen ohne Begründung → Formular-Fehler.
**Carry-Forward aus Task-4-Review: `web/laufmanager.py status()` um den Zustand "abgelehnt" erweitern (abgelehnt.json), sonst zeigt ein abgelehnter Lauf für immer "wartet auf Freigabe". Mit Test.**

### Task 6: Kampagnen-Bereich

**Files:** Create: `web/instantly_leser.py`, `web/routen/kampagnen.py`, `web/templates/kampagnen_liste.html` + `kampagne_detail.html`, `tests/web/test_kampagnen.py`
**Interfaces:** `InstantlyLeser(api_key, session=None)` (nur GET): `kampagnen_stand(ids) -> dict` (status, versendet, je-Schritt-Zähler soweit API sie liefert — Step-0-Probe am echten Konto, Felder danach fixiert), Cache 60 s mit Zeitstempel "Stand HH:MM". Liste vereinigt lokale Läufe (versand/versand_komplett) mit Live-Stand; Detail mit Schritt-Fortschritt, Wer/Wann, Instantly-Link, "pausiert"-Hinweis.
TDD: gefakte API-Antworten → Tabelle/Detail korrekt; API down → Seite lädt mit "Live-Stand gerade nicht erreichbar" statt Absturz.

### Task 7: Dashboard

**Files:** Create: `web/routen/dashboard.py`, `web/templates/dashboard.html`, `tests/web/test_dashboard.py`
**Interfaces:** Kacheln: wartende Freigaben (Anzahl aus Task-5-Logik, verlinkt), aktive Kampagnen, heute versendet, neue Antworten (aus Task-9-Leser; solange nicht gebaut: Platzhalter 0 mit TODO). Banner für angehaltene Aufträge (Task-4-Status). Listen: wartende Freigaben mit "Jetzt prüfen", Kampagnen-Kurzliste. Badge in der Seitenleiste = wartende Freigaben (Task 1-Platzhalter füllen).
TDD: mit präparierten Laufordnern stimmen Zahlen, Banner erscheint bei angehalten, Badge korrekt.

### Task 8: Kontakte

**Files:** Create: `web/kontakte.py`, `web/routen/kontakte.py`, `web/templates/kontakte.html`, `tests/web/test_kontakte.py`
**Interfaces:** `sammle_kontakte(daten_dir) -> list[dict]` — aggregiert alle Läufe aller Kunden (leads.json + pruefung_ok + versand-Zustand): Name, Firma, E-Mail, Kunde, Kampagne/Auftrag, zuletzt kontaktiert (Versanddatum falls übergeben, sonst "nur gefunden, nie angeschrieben" — ehrliche Beschriftung!). Dedupe per E-Mail, neuester Eintrag gewinnt. Suche (ein Feld, filtert über alle Spalten, serverseitig). Rein lesend.
TDD: Aggregation über zwei Kunden/drei Läufe korrekt; gefunden-aber-nie-gesendet wird als solches beschriftet; Suche filtert.

### Task 9: Postfach (lesend)

**Files:** Create: `web/routen/postfach.py`, `web/templates/postfach.html`, `tests/web/test_postfach.py`; Modify: `web/instantly_leser.py` (+ `konversationen(campaign_ids) -> list` aus der emails-API: gesendet + empfangen je Kontakt chronologisch; Feldnamen nach Read-only-Probe am echten Konto, Schritt 0 des Tasks)
**Interfaces:** Ansicht: Konversationsliste (Kontakt, Betreff, letzte Nachricht, Richtung), Detail chronologisch, Knopf "In Instantly antworten ↗". Kein Antwortfeld. Hinweis-Zeile, wenn die API keine Antworten liefert ("Antworten siehst du derzeit nur in Instantly") statt stiller Leere.
TDD: gefakte emails-Antworten → Gruppierung/Sortierung korrekt; leere/fehlende Daten → ehrlicher Hinweis.

### Task 10: Deployment auf den Arbeitsserver

**Files:** Create: `Dockerfile`, `deploy/docker-compose.coldmail.yml`, `deploy/nginx-mailingsystem.conf`, `deploy/DEPLOY.md`
Schritte (mit Ankündigung im Chat vor 2 und 5):
- [ ] 1. Live-Check per SSH (Schlüssel aus ViralLab/server): Plattenstand, laufende Container, nginx-Konfig lesen.
- [ ] 2. Docker-Build-Cache aufräumen (`docker builder prune -af` — von der Server-Doku selbst empfohlen), Plattenstand danach dokumentieren.
- [ ] 3. Verzeichnis `/opt/coldmailing/` anlegen: Code (git clone/rsync), Volume-Ordner `daten/` (kunden/, laeufe/, sperrliste-global.yaml, users.yaml). **PFLICHT (aus Task-4-Review, 17.07.2026): Schlüssel NICHT über eine .env-Datei im Code-Verzeichnis bereitstellen — die Pipeline-Unterprozesse laufen mit cwd=daten_dir und läsen dann die falsche Datei leise nicht. Stattdessen Schlüssel als echte Container-Umgebungsvariablen setzen (docker-compose `env_file:` auf eine .env AUSSERHALB des Images, z.B. /opt/coldmailing/.env, die compose in die Container-Umgebung injiziert — dann ist der Datei-Ort egal, weil os.environ gewinnt). Smoke-Test in Schritt 6 muss einen echten Mini-Lauf enthalten, der beweist, dass die Schlüssel im Unterprozess ankommen.**
- [ ] 4. Container bauen und starten (eigene compose-Datei, Netzwerk mit nginx teilen; interner Port 8000, nicht öffentlich).
- [ ] 5. nginx: neuer Server-Block `mailingsystem.polepositionautomation.de` → Container (Zertifikat: vorhandenes Wildcard prüfen; falls es die Subdomain nicht abdeckt: Lets-Encrypt-Zertifikat holen), reload.
- [ ] 6. Smoke-Test über HTTPS: /health, Login, Kunden-Seite; Screenshot für den Nachweis.
- [ ] 7. users.yaml mit echten Team-Namen anlegen (Passwörter setzt Leonard/Team, Übergabe dokumentiert in DEPLOY.md), Backup-Hinweis (daten/ in die Server-Backup-Routine aufnehmen — Empfehlung an Team notieren).

### Task 11: Abnahme (Erfolgskriterium)

- [ ] Begleiteter Durchlauf mit einem echten, nicht eingeweihten Kollegen: Kunde anlegen → Anschreiben erstellen lassen → prüfen → freigeben → Kampagne pausiert in Instantly sehen. Versand ausschließlich Test-Adressen. Beobachtungen protokollieren; Stolperstellen werden Fix-Liste. Danach project-context aktualisieren und Jira-Task (neu anzulegen: "Team web interface") auf Done.

## Selbst-Review

- Spec-Abdeckung: alle 7 Bereiche (T2–T9), Anmeldung+Namen (T1/T5), globale Sperrliste inkl. Pipeline-Wirkung (T2), eingefrorene Varianten Checkliste + Liste/Lesebereich (T5), Zustände/Polling (T4/T7), ehrliche Leere-/Fehlzustände (T6/T8/T9), Deployment+HTTPS (T10), Erfolgskriterium (T11).
- Bewusste Abweichung vom Skill-Format: Template-Markup wird aus der eingefrorenen v4-Vorlage abgeleitet statt im Plan dupliziert (Quelle ist versioniert im Repo).
- Offene Live-Verifikationen sind als Schritt 0 der Tasks 6/9 eingeplant, nicht versteckt.

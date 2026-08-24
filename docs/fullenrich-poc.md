# FullEnrich-only Anreicherung — Testlauf

Stand: 24.08.2026. Auftrag von Dafina: messen, ob **FullEnrich allein**
die Kette Firma → Entscheider → persönliche Mail, Durchwahl, Mobilnummer
für unsere echten Firmen schafft.

Der Test ersetzt nichts. **Apollo, Hunter, Dropcontact, Clay und
LinkedIn werden nicht aufgerufen** und ihr Code bleibt unangetastet.

## Die Reihenfolge — und warum sie so ist

Die Automatisierungs-Prüfung läuft **vor** jedem FullEnrich-Aufruf. Eine
Firma, die selbst Automatisierung anbietet, fällt später ohnehin aus der
Kampagne; sie anzureichern wäre bezahltes Geld für einen Lead, den wir
nicht benutzen dürfen.

```text
Firmen aus master.db (deterministisch gezogen)
        │
   Webseite lesen: Startseite + Leistungs-/Lösungs-/Über-uns-Seiten
        │
   Automatisierungs-Klassifizierung (KI, strukturierte Antwort)
        │
        ├── YES       → EXCLUDED, STOPP, kein API-Aufruf, kein Credit
        ├── UNCERTAIN → EXCLUDED, STOPP, zur Handprüfung
        │
        └── NO
                │
            FullEnrich  POST /company/lookup
                │
            FullEnrich  POST /people/search   (CEO/GF/Inhaber/…)
                │
            Rangfolge + Firmen-Abgleich
                │   (no_match → STOPP, keine Anreicherung)
                │
            FullEnrich  POST /contact/enrich/bulk → GET …/{id}
                │
            persönliche Mail · Arbeits-Mail · Durchwahl · Mobil
                │
            Qualitätsprüfung
                │
            zulässiger Kontakt
```

UNCERTAIN heißt **nicht** „keine Automatisierung". Wer nicht klar
beurteilt werden kann, wird nicht angereichert und landet auf der
Handprüfungs-Liste — dieselbe Regel wie in der Produktivstrecke seit
21.08.2026.

## Einrichtung

In `.env`:

```text
FULLENRICH_API_KEY=…
FULLENRICH_ENABLED=true
```

Der Schlüssel steht im FullEnrich-Dashboard unter **MCP, API &
Integrations → Automate at scale with API → Connect**.

`FULLENRICH_ENABLED` ist der Sicherheitsschalter aus Punkt 35 des
Auftrags: **ohne ihn macht der Befehl keinen einzigen bezahlten
Aufruf.** Der Trockenlauf (`--dry-run`) läuft auch ohne ihn.

`.env` ist in `.gitignore`. Der Schlüssel wird nirgends geloggt, nicht
in Fehlermeldungen ausgegeben und nicht in Rohantworten gespeichert.

Zusätzlich gebraucht wird ein KI-Schlüssel (`ANTHROPIC_API_KEY`,
`OPENROUTER_API_KEY` oder `OPENAI_API_KEY`) — für die
Automatisierungs-Prüfung, nicht für FullEnrich.

## Befehle

```bash
# Schlüssel prüfen - kostet laut FullEnrich-Doku 0 Credits
python -m pipeline fullenrich-poc --schluessel-pruefen

# Trockenlauf: Webseiten + Automatisierung, KEIN FullEnrich, keine Kosten
python -m pipeline fullenrich-poc --limit 100 --dry-run

# Echter Lauf
python -m pipeline fullenrich-poc --limit 100 --max-credits 500
```

| Option | Wirkung |
|---|---|
| `--limit N` | Wie viele bestehende Firmen (Standard 100) |
| `--seed N` | Auswahl-Seed. Gleicher Seed = exakt dieselben Firmen |
| `--dry-run` | Kein FullEnrich-Aufruf, keine Credits |
| `--max-credits N` | Harte Bremse: danach keine API-Aufrufe mehr |
| `--ttl-tage N` | Wie lange gelesene Webseiten wiederverwendet werden |
| `--ohne-rohantwort` | Rohantworten nicht mitspeichern |

## Wie die Firmen gewählt werden

Aus `daten/master.db`, Tabelle `companies`. Bedingung: Name **und**
Domain vorhanden — ohne Domain kann weder der Firmen-Abgleich noch die
Personensuche laufen.

Deterministisch (`random.Random(seed)`, Standard `20260824`). Derselbe
Seed zieht denselben Satz. Die IDs landen in
`daten/fullenrich-poc-auswahl.json`.

**Es wird nichts eingefügt und nichts geändert** — nur gelesen.

## Wie die Webseiten-Prüfung arbeitet

`pipeline/website_tiefe.py`. Der Grund, warum es sie gibt: das
vorhandene `pipeline/website.py` holt **nur die Startseite**. Der Audit
vom 21.08.2026 hat gezeigt, dass genau daran die Automatisierungs-Prüfung
scheiterte — alle drei bestätigten Fehlurteile kamen von Unterseiten.

Ablauf: Startseite holen → Links auslesen → die inhaltlich passenden
Unterseiten auswählen (`/leistungen/`, `/loesungen/`, `/produkte/`,
`/beratung/`, `/ueber-uns/` …) → bis zu vier davon mitlesen. Impressum,
Datenschutz, Karriere, Blog und Dateien bleiben draußen.

Jeder Abschnitt trägt seine Quelle (`[Quelle: <URL>]`), damit der
Klassifizierer sagen kann, **wo** er etwas gefunden hat.

**Zwischenspeicher:** je Domain eine Datei unter
`daten/webseiten-cache/`. Innerhalb der TTL (Standard 14 Tage) wird
nicht neu geholt.

Bei Fehlschlägen (keine Adresse, nicht erreichbar, zu wenig Text) gilt
`UNCERTAIN` — **nie automatisch „keine Automatisierung"**.

## Wie klassifiziert wird

`pipeline/automation_llm.py`. Der Klassifizierer sucht **nicht** nach dem
Wort „Automatisierung", sondern unterscheidet:

| Fall | Urteil |
|---|---|
| Automatisierung als Leistung für Kunden (RPA, Workflow, KI-Agenten, n8n/Make/Zapier) | YES |
| reine IT-Betreuung: Managed Services, Support, Netzwerk, Server, Security | NO |
| Industrie-/Gebäudeautomation (SPS, Maschinen) — andere Branche | NO |
| „wir automatisieren unsere eigenen Abläufe" | NO |
| Produkt, das Automatisierungs-Funktionen nur enthält | NO |
| zu dünn, zu allgemein, widersprüchlich | UNCERTAIN |

Antwort ist strukturiert:

```json
{"automation_status": "YES|NO|UNCERTAIN", "confidence": 0.0,
 "reason": "…", "evidence": "…", "source_url": "…"}
```

Eine `source_url`, die nicht wirklich gelesen wurde, wird verworfen —
eine erfundene Quelle wäre schlimmer als keine.

Der alte Baustein `branchen_filter.ist_wettbewerber()` bleibt
unangetastet; die Produktivstrecke benutzt weiterhin ihn.

## Wie Entscheider gewählt werden

Gesucht wird mit deutschen **und** englischen Titelvarianten (CEO,
Geschäftsführer, Inhaber, Managing Director, Founder, Managing Partner,
Director, Proprietor …), eingeschränkt auf die Firmen-Domain.

Rangfolge laut Auftrag: CEO → Geschäftsführer → Owner/Inhaber →
Managing Director → Founder → Managing Partner → Director → sonstige.

**Nie blind der erste Treffer.** Alternativkandidaten werden
mitgespeichert.

Wichtig: der Titel kommt ausschließlich aus `employment[].title`. Die
`headline` ist Selbstbeschreibung („Digital problem solver") und wird
**nicht** als Funktionsbezeichnung übernommen — im ersten echten Lauf
bekamen so Leute ohne Entscheider-Rolle einen Titel angedichtet.

## Wie Mail und Telefon getrennt gemessen werden

Olivers Anforderung verlangt ausdrücklich die **persönliche** Mail und
eine **persönliche** Nummer. Deshalb:

- Eine Arbeits-Mail zählt **nie** als persönliche Mail. Beide werden
  getrennt gezählt, ebenso „beide gefunden" und „keine gefunden".
- Eine Nummer, die mit der Firmenzentrale aus unserer Datenbank
  übereinstimmt, zählt **nie** als Durchwahl oder Mobilnummer. Sie wird
  als `company_switchboard_ignored` vermerkt.
- Mobil vs. Festnetz entscheidet die deutsche Vorwahl (015x/016x/017x).
  Bei ausländischen Nummern bleibt der Typ `type_unknown` — die Nummer
  geht nicht verloren, wird aber nicht geraten.

**Einschränkung der API:** das `Phone`-Objekt trägt nur `number` und
`region`. FullEnrich sagt **nicht**, ob eine Nummer mobil ist. „Mobile
rate" im Bericht ist unsere Einordnung, nicht die von FullEnrich.

## Was die API kostet

Laut Doku (geprüft 24.08.2026), Credits werden **nur bei Treffer**
verbraucht:

| Fund | Credits |
|---|---|
| E-Mail (Deliverable / High Probability / Catch-all) | 1 |
| persönliche E-Mail | 3 |
| Mobilnummer | 10 |
| **jede Person/Firma aus der Suche** | **0,25** |

Die Such-Credits meldet die API **nicht** pro Aufruf zurück — der
Bericht weist sie deshalb ausdrücklich als Schätzung aus.

Rate-Limit: **60 Aufrufe pro Minute** über alle Endpunkte zusammen.

Ein bereits angereicherter Kontakt kostet innerhalb von 3 Monaten
**0 Credits**. FullEnrich hat außerdem einen festen Testkontakt, der
immer 0 Credits kostet — den nutzt `--schluessel-pruefen`.

## Wo die Ergebnisse liegen

| Was | Wo |
|---|---|
| Ergebnis-Datenbank | `daten/fullenrich-poc.db` (eigene Datei) |
| Gezogene Stichprobe | `daten/fullenrich-poc-auswahl.json` |
| Webseiten-Cache | `daten/webseiten-cache/` |
| Alle Firmen | `fullenrich-alle-<stempel>.csv` |
| **Nur zulässige Kontakte** | `fullenrich-kontakte-<stempel>.csv` |
| **Handprüfung** | `fullenrich-handpruefung-<stempel>.csv` |
| Alles in einer Excel | `fullenrich-<stempel>.xlsx` (drei Blätter) |

`master.db` wird nicht angefasst.

## Den Bericht lesen

Die Quoten beziehen sich auf die **zulässigen** Firmen, nicht auf alle.
Wenn 30 Firmen am Automatisierungs-Tor hängen bleiben, sind 70 die
Bezugsgröße — sonst sähe die Sperre wie eine Schwäche von FullEnrich aus.

„Usable contact" = richtige Firma, echter Entscheider, mindestens eine
Mail. „Fully enriched" = zusätzlich mindestens eine persönliche Nummer.

## Den Test wiederholen

```bash
python -m pipeline fullenrich-poc --limit 100 --seed 20260824
```

Gleicher Seed, gleiche Firmen. Jeder Lauf bekommt eine eigene
`test_run_id`; alte Ergebnisse bleiben erhalten.

## Ab- und anschalten

`FULLENRICH_ENABLED` aus `.env` nehmen (oder auf `false` setzen) — dann
sind bezahlte Aufrufe gesperrt. Der Befehl läuft nur, wenn er
aufgerufen wird: kein Hook, kein Cron, kein Aufruf aus der
Produktivstrecke. Die POC-Datenbank kann man löschen, ohne dass etwas
fehlt.

## Bekannte Grenzen

1. **Kein Telefontyp von der API.** Siehe oben — die Einordnung ist
   unsere, nicht ihre.
2. **Suchtreffer-Kosten sind geschätzt**, weil die API sie nicht pro
   Aufruf meldet.
3. **Die Personensuche ist unscharf** (`exact_match: false` bei den
   Titeln), damit „Geschäftsführer" auch „Geschäftsführender
   Gesellschafter" trifft. Preis dafür: es kommen auch Leute ohne
   Entscheider-Rolle zurück. Die Rangfolge und die Qualitätsprüfung
   fangen das ab, aber der Bericht weist „mit echtem Entscheider-Titel"
   getrennt aus.
4. **Firmen-Abdeckung misst dieser Test nicht.** FullEnrich reichert an,
   was wir ihm geben; ob unsere Datenbank alle IT-Dienstleister der
   Region kennt, ist eine andere Frage (Google Maps, Gelbe Seiten,
   Overpass, North Data) und wird hier nicht beantwortet.

# Umsetzungsplan: AI Coldmailing System (v1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ziel:** Eine Pipeline, die aus einer Kunden-Konfiguration automatisch Leads aus Apollo holt, mit KI individuelle Anschreiben plus Follow-ups textet und sie nach menschlicher Freigabe als Kampagne an Instantly übergibt.

**Architektur:** Ein Python-Paket `pipeline/` mit klar getrennten Bausteinen (Quelle → Dedupe → Personalisierung → Prüfung → Freigabe → Versand). Jeder Lauf legt seine Zwischenergebnisse als JSON-Dateien in einem Laufordner ab, sodass nach einem Abbruch ab dem fehlgeschlagenen Schritt fortgesetzt wird. Externe Dienste (Apollo, Anthropic, Instantly) sitzen hinter dünnen, austauschbaren Klassen.

**Tech-Stack:** Python 3.11+, `requests`, `pyyaml`, `anthropic`, `pytest`. Keine Datenbank — Dateien reichen für v1.

**Design-Grundlage:** `docs/superpowers/specs/2026-07-16-ai-coldmailing-system-design.md` (freigegeben 16.07.2026).

## Globale Regeln

- Niemals echte Empfänger: Versand ausschließlich an Adressen aus der Test-Empfänger-Liste der Kunden-Konfiguration. In v1 gibt es keinen Code-Pfad, der andere Empfänger aktiviert.
- Kein Instantly-Schreibzugriff ohne Freigabe-Datei im Laufordner (Task 8), und vor dem allerersten Schreibzugriff aufs geteilte Team-Konto kurz Bescheid geben.
- API-Schlüssel nur in `.env` (steht in `.gitignore`), nie im Code, nie committen.
- Sprache im Code: englische Bezeichner für Technik-Allgemeines; deutsche Fachbegriffe der Domäne (Kunde, Sperrliste, Testnamen, CLI-Befehle wie `lauf`/`freigeben`/`senden`) sind ausdrücklich gewollt. Doku und Prompts auf Deutsch.
- Jeder Task endet mit grünem `pytest` und einem Commit.
- KI-Modell kommt aus der Umgebungsvariable `KI_MODELL` (Standard `claude-sonnet-5`) — nie fest verdrahten.
- Apollo- und Instantly-Payloads werden im jeweiligen Task zuerst gegen die Live-Doku verifiziert (docs.apollo.io, developer.instantly.ai) — die Codeblöcke hier sind der Ausgangspunkt, die Doku ist die Wahrheit.

## Risiken und offene Fragen (vor Start gelesen haben)

1. **Instantly-Tarif des Teams unklar.** API-v2-Zugang ist tarifabhängig. Task 9 beginnt mit dieser Prüfung; falls der Tarif keine API hat, entscheidet Leonard über ein Upgrade (~97 $/Monat) bevor weitergebaut wird.
2. **Apollo-Gratis-Plan:** reicht für den v1-Test (wenige Leads), aber Export-/API-Credits sind knapp bemessen. Für echten Kundenbetrieb ist ein bezahlter Plan einzukalkulieren (~50–100 $/Monat).
3. **Eingebaute Verifizierung in Instantly** ist womöglich ein kostenpflichtiges Extra — wird in Task 9 geprüft; Fallback ist ein externer Dienst (MillionVerifier, ~37 $/10.000), dafür gibt es einen markierten Erweiterungspunkt in Task 5.
4. **Rechtlicher Rahmen (UWG):** betrifft erst echte Kampagnen, nicht den v1-Test. Steht im Design; Entscheidung pro Kunde/Zielmarkt liegt beim Betreiber.
5. **Test-Domain kostet Geld** (~10–15 €/Jahr) und Postfach-Anlage berührt externe Konten — Task 11 holt dafür vorab Leonards Okay ein.

---

### Task 1: Projektgerüst

**Files:**
- Create: `pipeline/__init__.py`, `tests/__init__.py` (leer — macht `tests` importierbar, spätere Tasks importieren Test-Helfer quer), `tests/test_scaffold.py`, `requirements.txt`, `.env.example`
- Modify: `.gitignore` (existiert bereits mit `*.har`-Eintrag — die Einträge `.env`, `__pycache__/`, `.venv/`, `laeufe/` sind dort schon vorhanden; prüfen, nicht doppeln)

**Interfaces:**
- Produces: importierbares Paket `pipeline`, lauffähiges `pytest`.

- [ ] **Step 1: Dateien anlegen**

`requirements.txt`:
```
requests>=2.31
pyyaml>=6.0
anthropic>=0.40
pytest>=8.0
```

`.gitignore`:
```
.env
__pycache__/
.venv/
laeufe/
```

`.env.example`:
```
APOLLO_API_KEY=hier-eintragen
ANTHROPIC_API_KEY=hier-eintragen
INSTANTLY_API_KEY=hier-eintragen
KI_MODELL=claude-sonnet-5
```

`pipeline/__init__.py`:
```python
"""AI-Coldmailing-Pipeline: Leads -> Personalisierung -> Freigabe -> Versand."""
__version__ = "0.1.0"
```

`tests/test_scaffold.py`:
```python
import pipeline

def test_paket_importierbar():
    assert pipeline.__version__
```

- [ ] **Step 2: Umgebung aufsetzen und Test laufen lassen**

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m pytest -v`
Expected: `1 passed`

- [ ] **Step 3: Commit**

```bash
git add pipeline tests requirements.txt .gitignore .env.example
git commit -m "feat: Projektgeruest mit pytest-Setup"
```

---

### Task 2: Lead-Modell und Kunden-Konfiguration

**Files:**
- Create: `pipeline/models.py`, `pipeline/config.py`, `kunden/demo-gmbh.yaml`, `tests/test_models.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `Lead` (dataclass: `first_name, last_name, email, company, title, website, source`; `email` wird normalisiert), `Kunde` (dataclass: `name, zielgruppe: dict, angebot: str, tonalitaet: str, absender: str, follow_up_tage: list[int], test_empfaenger: list[str]`), `load_kunde(path) -> Kunde` (wirft `ValueError` bei fehlenden Pflichtfeldern).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`tests/test_models.py`:
```python
from pipeline.models import Lead

def test_lead_normalisiert_email():
    lead = Lead(first_name="Anna", last_name="Muster", email="  Anna@Firma.DE ",
                company="Firma GmbH", title="CEO", website="https://firma.de", source="apollo")
    assert lead.email == "anna@firma.de"
```

`tests/test_config.py`:
```python
import pytest
from pipeline.config import load_kunde

GUELTIG = """
name: Demo GmbH
zielgruppe:
  titel: [CEO, "Head of Sales"]
  region: [Germany]
  firmengroesse: ["11-50"]
angebot: KI-Automatisierung fuer Vertriebsprozesse
tonalitaet: ruhig, erklaerend, keine Superlative
absender: Leonard von Digital Diamonds
follow_up_tage: [3, 7]
test_empfaenger:
  - test1@example.com
"""

def test_laedt_gueltige_konfig(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG, encoding="utf-8")
    kunde = load_kunde(p)
    assert kunde.name == "Demo GmbH"
    assert kunde.follow_up_tage == [3, 7]

def test_fehlendes_pflichtfeld_wirft_fehler(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text("name: Nur Name", encoding="utf-8")
    with pytest.raises(ValueError, match="angebot"):
        load_kunde(p)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `.venv/bin/python -m pytest tests/test_models.py tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implementieren**

`pipeline/models.py`:
```python
from dataclasses import dataclass, field

@dataclass
class Lead:
    first_name: str
    last_name: str
    email: str
    company: str
    title: str
    website: str
    source: str
    notizen: list = field(default_factory=list)

    def __post_init__(self):
        self.email = self.email.strip().lower()
```

`pipeline/config.py`:
```python
from dataclasses import dataclass, field
import yaml

PFLICHTFELDER = ["name", "zielgruppe", "angebot", "tonalitaet",
                 "absender", "follow_up_tage", "test_empfaenger"]

@dataclass
class Kunde:
    name: str
    zielgruppe: dict
    angebot: str
    tonalitaet: str
    absender: str
    follow_up_tage: list
    test_empfaenger: list
    sperrliste: list = field(default_factory=list)  # Domains, nie anschreiben

def load_kunde(path) -> Kunde:
    with open(path, encoding="utf-8") as f:
        daten = yaml.safe_load(f) or {}
    fehlend = [k for k in PFLICHTFELDER if k not in daten]
    if fehlend:
        raise ValueError(f"Pflichtfelder fehlen in {path}: {', '.join(fehlend)}")
    return Kunde(**{k: daten[k] for k in PFLICHTFELDER},
                 sperrliste=daten.get("sperrliste") or [])
```

Zusätzlicher Test in `tests/test_config.py` (Sperrliste ist optional):
```python
def test_sperrliste_ist_optional(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG, encoding="utf-8")
    assert load_kunde(p).sperrliste == []
```

`kunden/demo-gmbh.yaml`: exakt der Inhalt der Konstante `GUELTIG` aus dem Test (ohne die umschließenden Anführungszeichen).

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/models.py pipeline/config.py kunden/ tests/
git commit -m "feat: Lead-Modell und Kunden-Konfiguration"
```

---

### Task 3: Laufordner mit Wiederaufnahme

**Files:**
- Create: `pipeline/run_store.py`, `tests/test_run_store.py`

**Interfaces:**
- Produces: `RunStore(basis_dir, kunde_name)` mit `run_dir: Path`, `save_step(name: str, daten: list|dict)`, `load_step(name) -> list|dict`, `step_done(name) -> bool`, Klassenmethode `resume(run_dir) -> RunStore`. Schritte liegen als `<name>.json` im Laufordner `laeufe/<kunde-slug>/<zeitstempel>/`.

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`tests/test_run_store.py`:
```python
from pipeline.run_store import RunStore

def test_speichert_und_laedt_schritt(tmp_path):
    store = RunStore(tmp_path, "Demo GmbH")
    assert not store.step_done("leads")
    store.save_step("leads", [{"email": "a@b.de"}])
    assert store.step_done("leads")
    assert store.load_step("leads") == [{"email": "a@b.de"}]

def test_resume_findet_alte_schritte(tmp_path):
    store = RunStore(tmp_path, "Demo GmbH")
    store.save_step("leads", [1, 2])
    wieder = RunStore.resume(store.run_dir)
    assert wieder.step_done("leads")
```

- [ ] **Step 2: Test fehlschlagen sehen** — Run: `.venv/bin/python -m pytest tests/test_run_store.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren**

`pipeline/run_store.py`:
```python
import json, re
from datetime import datetime
from pathlib import Path

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

class RunStore:
    def __init__(self, basis_dir, kunde_name, _existing: Path | None = None):
        if _existing is not None:
            self.run_dir = Path(_existing)
        else:
            stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.run_dir = Path(basis_dir) / _slug(kunde_name) / stempel
            self.run_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resume(cls, run_dir) -> "RunStore":
        return cls(None, None, _existing=run_dir)

    def _pfad(self, name: str) -> Path:
        return self.run_dir / f"{name}.json"

    def step_done(self, name: str) -> bool:
        return self._pfad(name).exists()

    def save_step(self, name: str, daten):
        self._pfad(name).write_text(
            json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_step(self, name: str):
        return json.loads(self._pfad(name).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/run_store.py tests/test_run_store.py
git commit -m "feat: Laufordner mit Wiederaufnahme"
```

---

### Task 4: Apollo als Lead-Quelle

**Files:**
- Create: `pipeline/sources/__init__.py`, `pipeline/sources/apollo.py`, `tests/test_apollo.py`

**Interfaces:**
- Consumes: `Lead` aus Task 2.
- Produces: `ApolloSource(api_key, session=None)` mit `search(zielgruppe: dict, limit: int) -> list[Lead]`. Wiederholt bei HTTP 429/5xx bis zu 3-mal mit wachsender Wartezeit. Leads ohne E-Mail werden übersprungen.

**Nachtrag (Erkenntnis aus der Live-Doku, 16.07.2026):** Die People-Search-Antwort von Apollo enthält keine E-Mail-Adressen (und der Suchpfad heißt `mixed_people/api_search`). `search()` reichert die Treffer deshalb in einem zweiten Schritt über den Enrichment-Endpoint (`POST /api/v1/people/bulk_match`, bis zu 10 Personen je Aufruf, verbraucht die eingeplanten Export-Credits) an und mappt erst danach auf `Lead`. Personen, für die auch das Enrichment keine E-Mail liefert, werden wie gehabt übersprungen und im Bericht gezählt.

- [ ] **Step 1: Live-Doku prüfen**

Die aktuelle Endpoint-Beschreibung von https://docs.apollo.io (People-Search) laden und Feldnamen im folgenden Code daran anpassen (Endpoint, Header `X-Api-Key`, Antwortstruktur `people[]`). Abweichungen im Commit-Text nennen.

- [ ] **Step 2: Fehlschlagenden Test schreiben (HTTP wird gefaked)**

`tests/test_apollo.py`:
```python
from pipeline.sources.apollo import ApolloSource

class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code, self._payload = status_code, payload
    def json(self):
        return self._payload

class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.aufrufe = list(antworten), []
    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append(json)
        return self.antworten.pop(0)

PERSON = {"first_name": "Anna", "last_name": "Muster", "email": "anna@firma.de",
          "title": "CEO", "organization": {"name": "Firma GmbH", "website_url": "https://firma.de"}}

def test_mappt_personen_auf_leads():
    session = FakeSession([FakeResponse(200, {"people": [PERSON]})])
    leads = ApolloSource("key", session=session).search({"titel": ["CEO"]}, limit=10)
    assert leads[0].company == "Firma GmbH" and leads[0].source == "apollo"

def test_wiederholt_bei_429():
    session = FakeSession([FakeResponse(429, {}), FakeResponse(200, {"people": [PERSON]})])
    leads = ApolloSource("key", session=session, wartezeit=0).search({}, limit=10)
    assert len(leads) == 1 and len(session.aufrufe) == 2

def test_ueberspringt_leads_ohne_email():
    ohne = dict(PERSON, email=None)
    session = FakeSession([FakeResponse(200, {"people": [ohne]})])
    assert ApolloSource("key", session=session).search({}, limit=10) == []
```

- [ ] **Step 3: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_apollo.py -v` — Expected: FAIL

- [ ] **Step 4: Implementieren**

`pipeline/sources/apollo.py`:
```python
import time
import requests
from pipeline.models import Lead

URL = "https://api.apollo.io/api/v1/mixed_people/search"

class ApolloSource:
    def __init__(self, api_key, session=None, wartezeit=5):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit

    def search(self, zielgruppe: dict, limit: int):
        body = {
            "person_titles": zielgruppe.get("titel", []),
            "person_locations": zielgruppe.get("region", []),
            "organization_num_employees_ranges": zielgruppe.get("firmengroesse", []),
            "per_page": min(limit, 100), "page": 1,
        }
        antwort = self._post_mit_wiederholung(body)
        leads = []
        for p in antwort.json().get("people", [])[:limit]:
            if not p.get("email"):
                continue
            org = p.get("organization") or {}
            leads.append(Lead(
                first_name=p.get("first_name", ""), last_name=p.get("last_name", ""),
                email=p["email"], company=org.get("name", ""), title=p.get("title", ""),
                website=org.get("website_url", ""), source="apollo"))
        return leads

    def _post_mit_wiederholung(self, body):
        for versuch in range(3):
            antwort = self.session.post(
                URL, json=body, timeout=30,
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"})
            if antwort.status_code < 400:
                return antwort
            time.sleep(self.wartezeit * (versuch + 1))
        raise RuntimeError(f"Apollo antwortet dauerhaft mit {antwort.status_code}")
```

- [ ] **Step 5: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/sources tests/test_apollo.py
git commit -m "feat: Apollo-Quelle mit Wiederholungslogik"
```

---

### Task 5: Dubletten aussortieren und Sperrliste

**Files:**
- Create: `pipeline/dedupe.py`, `tests/test_dedupe.py`

**Interfaces:**
- Consumes: `list[Lead]`, Kundenordner `laeufe/<kunde-slug>/` mit früheren Läufen (deren `leads.json`), `kunde.sperrliste`.
- Produces: `dedupe(leads, kunde_laeufe_dir, sperrliste=()) -> tuple[list[Lead], list[dict]]` — Prüf-Reihenfolge: (1) Domain auf Sperrliste (E-Mail-Domain und Webseiten-Domain, Wildcard `*.beispiel.de` erlaubt — Vorbild: die Wholix-Sperrliste des Teams mit eigener Agentur, Partnern, `*.bund.de`), (2) Duplikate innerhalb der Liste (per E-Mail), (3) gegen alle `leads.json` früherer Läufe. Zweiter Rückgabewert: verworfene als `{"email": ..., "grund": ...}` für den Bericht. Hier sitzt auch der markierte Erweiterungspunkt für externe Verifizierung (Kommentar im Code genügt, kein Bau in v1).

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`tests/test_dedupe.py`:
```python
import json
from pipeline.dedupe import dedupe
from pipeline.models import Lead

def _lead(email):
    return Lead(first_name="A", last_name="B", email=email, company="C",
                title="T", website="", source="apollo")

def test_entfernt_doppelte_in_liste(tmp_path):
    behalten, verworfen = dedupe([_lead("a@x.de"), _lead("A@X.de")], tmp_path)
    assert len(behalten) == 1
    assert verworfen[0]["grund"] == "doppelt in dieser Liste"

def test_entfernt_bekannte_aus_frueheren_laeufen(tmp_path):
    alt = tmp_path / "20260101-000000"
    alt.mkdir()
    (alt / "leads.json").write_text(json.dumps([{"email": "a@x.de"}]), encoding="utf-8")
    behalten, verworfen = dedupe([_lead("a@x.de"), _lead("neu@x.de")], tmp_path)
    assert [l.email for l in behalten] == ["neu@x.de"]
    assert verworfen[0]["grund"] == "bereits in frueherem Lauf angeschrieben"

def test_sperrliste_blockt_domains_auch_mit_wildcard(tmp_path):
    leads = [_lead("chef@digitaldiamonds.agency"), _lead("amt@stadt.bund.de"),
             _lead("ok@neu.de")]
    behalten, verworfen = dedupe(leads, tmp_path,
                                 sperrliste=["digitaldiamonds.agency", "*.bund.de"])
    assert [l.email for l in behalten] == ["ok@neu.de"]
    assert all(v["grund"] == "Domain auf Sperrliste" for v in verworfen)
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_dedupe.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren**

`pipeline/dedupe.py`:
```python
import json
from pathlib import Path
from urllib.parse import urlparse

# Erweiterungspunkt: Hier koennte nach dem Dedupe eine externe
# E-Mail-Verifizierung (z.B. MillionVerifier) haengen. v1 nutzt die
# eingebaute Pruefung von Instantly beim Import.

def _bekannte_emails(kunde_laeufe_dir) -> set:
    bekannte = set()
    for datei in Path(kunde_laeufe_dir).glob("*/leads.json"):
        for eintrag in json.loads(datei.read_text(encoding="utf-8")):
            bekannte.add(eintrag["email"].strip().lower())
    return bekannte

def _gesperrt(lead, sperrliste) -> bool:
    domains = {lead.email.split("@", 1)[-1]}
    if lead.website:
        netloc = urlparse(lead.website).netloc.lower()
        domains.add(netloc[4:] if netloc.startswith("www.") else netloc)
    for muster in sperrliste:
        muster = muster.strip().lower()
        for domain in domains:
            if muster.startswith("*.") and domain.endswith(muster[1:]):
                return True
            if domain == muster:
                return True
    return False

def dedupe(leads, kunde_laeufe_dir, sperrliste=()):
    bekannte = _bekannte_emails(kunde_laeufe_dir)
    gesehen, behalten, verworfen = set(), [], []
    for lead in leads:
        if _gesperrt(lead, sperrliste):
            verworfen.append({"email": lead.email, "grund": "Domain auf Sperrliste"})
        elif lead.email in gesehen:
            verworfen.append({"email": lead.email, "grund": "doppelt in dieser Liste"})
        elif lead.email in bekannte:
            verworfen.append({"email": lead.email,
                              "grund": "bereits in frueherem Lauf angeschrieben"})
        else:
            gesehen.add(lead.email)
            behalten.append(lead)
    return behalten, verworfen
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/dedupe.py tests/test_dedupe.py
git commit -m "feat: Dubletten-Aussortierung inkl. frueherer Laeufe"
```

---

### Task 6: Webseiten-Text, KI-Anbindung und Personalisierung

**Files:**
- Create: `pipeline/website.py`, `pipeline/ki.py`, `pipeline/personalize.py`, `prompts/anschreiben.md`, `tests/test_website.py`, `tests/test_personalize.py`

**Interfaces:**
- Consumes: `Lead`, `Kunde`.
- Produces: `fetch_text(url) -> str` (Sichtbarer Text der Seite, max. 5000 Zeichen, `""` bei Fehler); `KI(model=None)` mit `frage(system: str, prompt: str) -> str` (liest `ANTHROPIC_API_KEY` und `KI_MODELL` aus der Umgebung); `personalize(lead, kunde, ki) -> dict` mit Schlüsseln `betreff, mail_1, follow_up_1, follow_up_2` (wirft `ValueError` bei unvollständiger KI-Antwort — der Aufrufer sortiert den Lead dann in die Nacharbeit).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`tests/test_website.py`:
```python
from pipeline.website import _sichtbarer_text

def test_extrahiert_sichtbaren_text():
    html = "<html><head><script>x=1</script></head><body><h1>Wir sind Firma</h1><p>Wir bauen Rohre.</p></body></html>"
    text = _sichtbarer_text(html)
    assert "Wir bauen Rohre." in text and "x=1" not in text
```

`tests/test_personalize.py`:
```python
import json, pytest
from pipeline.personalize import personalize
from pipeline.models import Lead
from pipeline.config import Kunde

KUNDE = Kunde(name="Demo GmbH", zielgruppe={}, angebot="KI-Automatisierung",
              tonalitaet="ruhig", absender="Leonard", follow_up_tage=[3, 7],
              test_empfaenger=["t@example.com"])
LEAD = Lead(first_name="Anna", last_name="Muster", email="anna@firma.de",
            company="Firma GmbH", title="CEO", website="", source="apollo")

class FakeKI:
    def __init__(self, antwort):
        self.antwort, self.prompts = antwort, []
    def frage(self, system, prompt):
        self.prompts.append(prompt)
        return self.antwort

def test_liefert_alle_textteile():
    ki = FakeKI(json.dumps({"betreff": "B", "mail_1": "M", "follow_up_1": "F1", "follow_up_2": "F2"}))
    texte = personalize(LEAD, KUNDE, ki, webseiten_text="Wir bauen Rohre.")
    assert texte["betreff"] == "B"
    assert "Firma GmbH" in ki.prompts[0] and "Wir bauen Rohre." in ki.prompts[0]

def test_unvollstaendige_antwort_wirft_fehler():
    ki = FakeKI(json.dumps({"betreff": "B"}))
    with pytest.raises(ValueError):
        personalize(LEAD, KUNDE, ki, webseiten_text="")
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_website.py tests/test_personalize.py -v` — Expected: FAIL

- [ ] **Step 3: Prompt-Datei schreiben**

`prompts/anschreiben.md`:
```markdown
Du schreibst Kalt-E-Mails für {absender}, im Auftrag von {kunde_name}.
Angebot: {angebot}
Tonalität: {tonalitaet}. Keine Superlative, keine Ausrufezeichen,
kein Werbedeutsch, keine Floskeln wie "ich hoffe, es geht Ihnen gut".

Empfänger: {anrede_name}, {titel} bei {firma}.
Was über die Firma bekannt ist (von ihrer Webseite):
---
{webseiten_text}
---

Schreibe auf Deutsch (Sie-Form):
1. betreff: konkret, unter 8 Wörter, kein Clickbait.
2. mail_1: 60–120 Wörter. Beginnt mit einem konkreten Bezug auf DIESE
   Firma (aus dem Webseiten-Text), dann eine Brücke zum Angebot, dann
   eine leichte Frage als Abschluss. Keine Links, keine Anhänge.
3. follow_up_1: 40–80 Wörter, freundlich kurz nachgefasst, neuer Blickwinkel.
4. follow_up_2: 30–60 Wörter, letzter kurzer Anstoß, respektvoller Abschluss.

Wenn der Webseiten-Text leer oder unbrauchbar ist, nutze nur Titel und
Branche — erfinde nichts über die Firma.

Antworte NUR mit JSON: {{"betreff": ..., "mail_1": ..., "follow_up_1": ..., "follow_up_2": ...}}
```

- [ ] **Step 4: Implementieren**

`pipeline/website.py`:
```python
import re
import requests

def _sichtbarer_text(html: str) -> str:
    html = re.sub(r"(?s)<(script|style|noscript).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()

def fetch_text(url: str, max_zeichen: int = 5000) -> str:
    if not url:
        return ""
    try:
        antwort = requests.get(url, timeout=15,
                               headers={"User-Agent": "Mozilla/5.0 (Recherche)"})
        antwort.raise_for_status()
        return _sichtbarer_text(antwort.text)[:max_zeichen]
    except requests.RequestException:
        return ""
```

`pipeline/ki.py`:
```python
import os
import anthropic

class KI:
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("KI_MODELL", "claude-sonnet-5")
        self.client = anthropic.Anthropic()  # liest ANTHROPIC_API_KEY

    def frage(self, system: str, prompt: str) -> str:
        antwort = self.client.messages.create(
            model=self.model, max_tokens=1500, system=system,
            messages=[{"role": "user", "content": prompt}])
        return antwort.content[0].text
```

`pipeline/personalize.py`:
```python
import json, re
from pathlib import Path

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "anschreiben.md"
PFLICHT = ["betreff", "mail_1", "follow_up_1", "follow_up_2"]
SYSTEM = "Du bist ein praeziser Texter fuer B2B-Kaltakquise. Antworte nur mit JSON."

def personalize(lead, kunde, ki, webseiten_text: str) -> dict:
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        absender=kunde.absender, kunde_name=kunde.name, angebot=kunde.angebot,
        tonalitaet=kunde.tonalitaet, anrede_name=f"{lead.first_name} {lead.last_name}",
        titel=lead.title, firma=lead.company, webseiten_text=webseiten_text or "(leer)")
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    daten = json.loads(treffer.group(0)) if treffer else {}
    if any(not daten.get(k) for k in PFLICHT):
        raise ValueError(f"KI-Antwort unvollstaendig fuer {lead.email}")
    return {k: daten[k] for k in PFLICHT}
```

- [ ] **Step 5: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/website.py pipeline/ki.py pipeline/personalize.py prompts/ tests/
git commit -m "feat: Webseiten-Text, KI-Anbindung und Personalisierung"
```

---

### Task 6b: Angebots-Analyse der eigenen Webseite

Hintergrund (interne Notiz 16.07.2026): Das System soll neben der Lead-Webseite auch "das eigene Angebot" analysieren. Dieser Baustein liest die Webseite des Auftraggebers und füllt die Felder `angebot` und `tonalitaet` der Kunden-Konfiguration als Entwurf vor — aber nur, wenn sie leer sind; Handgeschriebenes wird nie überschrieben.

**Files:**
- Create: `pipeline/offer.py`, `prompts/angebot.md`, `tests/test_offer.py`

**Interfaces:**
- Consumes: `fetch_text` und `KI` aus Task 6.
- Produces: `draft_offer(website_text: str, ki) -> dict` (Schlüssel `angebot`, `tonalitaet`; wirft `ValueError` bei unvollständiger KI-Antwort); `uebernehmen(kunde_pfad, entwurf)` (füllt nur leere Felder der YAML). Eigener Runner: `python -m pipeline.offer <url> <kunde.yaml>` — unabhängig vom Haupt-CLI aus Task 10.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`tests/test_offer.py`:
```python
import json, yaml
from pipeline.offer import draft_offer, uebernehmen
from tests.test_personalize import FakeKI

def test_entwurf_liefert_beide_felder():
    ki = FakeKI(json.dumps({"angebot": "A", "tonalitaet": "T"}))
    assert draft_offer("Wir bauen KI-Automationen.", ki) == {"angebot": "A", "tonalitaet": "T"}

def test_uebernehmen_fuellt_nur_leere_felder(tmp_path):
    p = tmp_path / "k.yaml"
    p.write_text("name: X\nangebot:\ntonalitaet: bestehend\n", encoding="utf-8")
    uebernehmen(p, {"angebot": "Neu", "tonalitaet": "Anders"})
    daten = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert daten["angebot"] == "Neu" and daten["tonalitaet"] == "bestehend"
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_offer.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren**

`prompts/angebot.md`:
```markdown
Hier ist der Text einer Firmen-Webseite:
---
{webseiten_text}
---
Leite daraus ab:
1. angebot: 2–4 Sätze — was bietet diese Firma wem an, mit welchem
   Nutzen? Nüchtern, konkret, keine Werbesprache. Erfinde nichts.
2. tonalitaet: 3–6 Stichworte, wie diese Firma klingen sollte.
Antworte NUR mit JSON: {{"angebot": ..., "tonalitaet": ...}}
```

`pipeline/offer.py`:
```python
import json, re, sys
from pathlib import Path
import yaml
from pipeline.website import fetch_text
from pipeline.ki import KI

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "angebot.md"
SYSTEM = ("Du analysierst Firmen-Webseiten und formulierst "
          "Angebots-Beschreibungen. Antworte nur mit JSON.")
FELDER = ["angebot", "tonalitaet"]

def draft_offer(website_text: str, ki) -> dict:
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        webseiten_text=website_text or "(leer)")
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    daten = json.loads(treffer.group(0)) if treffer else {}
    if any(not daten.get(k) for k in FELDER):
        raise ValueError("KI-Entwurf unvollstaendig")
    return {k: daten[k] for k in FELDER}

def uebernehmen(kunde_pfad, entwurf: dict):
    pfad = Path(kunde_pfad)
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    for feld in FELDER:
        if not daten.get(feld):
            daten[feld] = entwurf[feld]
    pfad.write_text(yaml.safe_dump(daten, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")

def main():
    url, kunde_pfad = sys.argv[1], sys.argv[2]
    entwurf = draft_offer(fetch_text(url), KI())
    uebernehmen(kunde_pfad, entwurf)
    print("Entwurf eingetragen (nur leere Felder):",
          json.dumps(entwurf, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/offer.py prompts/angebot.md tests/test_offer.py
git commit -m "feat: Angebots-Analyse der eigenen Webseite als Konfig-Entwurf"
```

---

### Task 7: Qualitätsprüfung mit Nacharbeit-Liste

**Files:**
- Create: `pipeline/quality.py`, `prompts/pruefer.md`, `tests/test_quality.py`

**Interfaces:**
- Consumes: `dict` aus `personalize`, `Kunde`, `KI`.
- Produces: `check(texte: dict, lead, kunde, ki) -> tuple[bool, str]` — erst Regeln (keine übrig gebliebenen Platzhalter `{`/`[`, Betreff ≤ 60 Zeichen, `mail_1` 40–160 Wörter), dann KI-Urteil. Rückgabe `(ok, begruendung)`.

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`tests/test_quality.py`:
```python
from pipeline.quality import check
from tests.test_personalize import KUNDE, LEAD, FakeKI

GUT = {"betreff": "Rohrbau und Angebotsprozesse", "mail_1": " ".join(["Wort"] * 80),
       "follow_up_1": "Kurz nachgefasst.", "follow_up_2": "Letzter Anstoss."}

def test_regeln_fangen_platzhalter():
    kaputt = dict(GUT, mail_1="Hallo {anrede_name}, " + " ".join(["Wort"] * 60))
    ok, grund = check(kaputt, LEAD, KUNDE, FakeKI("JA"))
    assert not ok and "Platzhalter" in grund

def test_ki_urteil_nein_faellt_durch():
    ok, grund = check(GUT, LEAD, KUNDE, FakeKI("NEIN: klingt nach Massenmail"))
    assert not ok

def test_alles_gut_besteht():
    ok, _ = check(GUT, LEAD, KUNDE, FakeKI("JA"))
    assert ok
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_quality.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren**

`prompts/pruefer.md`:
```markdown
Prüfe diese Kalt-E-Mail streng. Empfänger: {titel} bei {firma}.
Tonalität laut Auftrag: {tonalitaet}.

Betreff: {betreff}
Text: {mail_1}

Durchgefallen, wenn: klingt nach Massenmail; kein konkreter Bezug zur
Firma; Werbedeutsch/Superlative; erfundene Behauptungen über die Firma;
falsche Anrede. Antworte NUR mit "JA" (besteht) oder "NEIN: <Grund>".
```

`pipeline/quality.py`:
```python
from pathlib import Path

PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "pruefer.md"
SYSTEM = "Du bist ein strenger Pruefer fuer B2B-Kaltakquise-Texte."

def _regeln(texte: dict) -> str:
    alle = " ".join(texte.values())
    if "{" in alle or "[" in alle:
        return "Platzhalter im Text uebrig"
    if len(texte["betreff"]) > 60:
        return "Betreff laenger als 60 Zeichen"
    woerter = len(texte["mail_1"].split())
    if not 40 <= woerter <= 160:
        return f"mail_1 hat {woerter} Woerter (erlaubt 40-160)"
    return ""

def check(texte, lead, kunde, ki):
    fehler = _regeln(texte)
    if fehler:
        return False, fehler
    prompt = PROMPT_DATEI.read_text(encoding="utf-8").format(
        titel=lead.title, firma=lead.company, tonalitaet=kunde.tonalitaet,
        betreff=texte["betreff"], mail_1=texte["mail_1"])
    urteil = ki.frage(SYSTEM, prompt).strip()
    if urteil.upper().startswith("JA"):
        return True, "bestanden"
    return False, f"KI-Pruefer: {urteil}"
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/quality.py prompts/pruefer.md tests/test_quality.py
git commit -m "feat: Qualitaetspruefung mit Regeln und KI-Urteil"
```

---

### Task 8: Freigabe-Schritt

**Files:**
- Create: `pipeline/approval.py`, `tests/test_approval.py`

**Interfaces:**
- Consumes: `RunStore` (Task 3).
- Produces: `write_preview(store, texte_pro_lead: list[dict], nacharbeit: list[dict])` — schreibt `freigabe-vorschau.md` (Zahlen + die ersten 3 kompletten Anschreiben) in den Laufordner; `is_approved(store) -> bool` — wahr nur, wenn `FREIGABE.txt` im Laufordner existiert; `approve(store)` — legt `FREIGABE.txt` mit Zeitstempel an (wird nur vom Menschen per CLI-Befehl ausgelöst, Task 10).

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`tests/test_approval.py`:
```python
from pipeline.run_store import RunStore
from pipeline.approval import write_preview, is_approved, approve

def test_ohne_freigabe_nicht_freigegeben(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_preview(store, [{"email": "a@b.de", "betreff": "B", "mail_1": "M",
                           "follow_up_1": "F1", "follow_up_2": "F2"}], [])
    assert not is_approved(store)
    assert (store.run_dir / "freigabe-vorschau.md").exists()

def test_freigabe_setzt_datei(tmp_path):
    store = RunStore(tmp_path, "Demo")
    approve(store)
    assert is_approved(store)
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_approval.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren**

`pipeline/approval.py`:
```python
from datetime import datetime

def write_preview(store, texte_pro_lead, nacharbeit):
    zeilen = [f"# Freigabe-Vorschau",
              f"Fertig personalisiert: {len(texte_pro_lead)} | Nacharbeit: {len(nacharbeit)}", ""]
    for eintrag in texte_pro_lead[:3]:
        zeilen += [f"## {eintrag['email']}", f"Betreff: {eintrag['betreff']}", "",
                   eintrag["mail_1"], "", f"Follow-up 1: {eintrag['follow_up_1']}",
                   f"Follow-up 2: {eintrag['follow_up_2']}", "", "---", ""]
    zeilen.append("Freigeben mit: python -m pipeline freigeben <laufordner>")
    (store.run_dir / "freigabe-vorschau.md").write_text("\n".join(zeilen), encoding="utf-8")

def is_approved(store) -> bool:
    return (store.run_dir / "FREIGABE.txt").exists()

def approve(store):
    (store.run_dir / "FREIGABE.txt").write_text(
        f"Freigegeben am {datetime.now().isoformat()}\n", encoding="utf-8")
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/approval.py tests/test_approval.py
git commit -m "feat: Freigabe-Schritt mit Vorschau"
```

---

### Task 9: Instantly-Anbindung

**Files:**
- Create: `pipeline/senders/__init__.py`, `pipeline/senders/instantly.py`, `tests/test_instantly.py`

**Interfaces:**
- Consumes: `Kunde`, Textpakete `{email, betreff, mail_1, follow_up_1, follow_up_2}`.
- Produces: `InstantlySender(api_key, session=None)` mit `create_campaign(kunde, texte_pro_lead) -> str` (Kampagnen-ID). Die Kampagne wird **pausiert** angelegt und NIE per Code aktiviert — aktiviert wird von Hand in der Instantly-Oberfläche. Personalisierte Texte laufen als Custom-Variablen pro Lead (`betreff`, `mail_1`, …), die Sequenz-Vorlagen referenzieren sie mit `{{mail_1}}` usw.; Follow-up-Abstände kommen aus `kunde.follow_up_tage`. Schutz-Voreinstellungen wie bei Wholix beobachtet: **max. 20 Mails/Tag pro Postfach, Versandfenster Mo–Fr 08–19 Uhr Europe/Berlin** — exakte Feldnamen dafür laut Live-Doku (Step 0) ergänzen.

- [ ] **Step 0: Vorprüfungen (blockierend)**

1. Bei Leonard klären, wer den API-Schlüssel des Team-Kontos hat, und Bescheid geben, bevor das erste Mal ins Team-Konto geschrieben wird (eigener Workspace/erkennbares Namensschema `[TEST] …` für alles, was dieser Code anlegt).
2. https://developer.instantly.ai lesen: enthält der Team-Tarif API v2? Exakte Payloads für `POST /api/v2/campaigns` und Lead-Import übernehmen und den Code unten anpassen. Prüfen, ob die eingebaute Verifizierung im Tarif enthalten ist (Risiko 3).

- [ ] **Step 1: Fehlschlagenden Test schreiben (HTTP gefaked, wie Task 4)**

`tests/test_instantly.py`:
```python
from pipeline.senders.instantly import InstantlySender
from tests.test_apollo import FakeSession, FakeResponse
from tests.test_personalize import KUNDE

TEXTE = [{"email": "t@example.com", "betreff": "B", "mail_1": "M",
          "follow_up_1": "F1", "follow_up_2": "F2"}]

def test_legt_pausierte_kampagne_an_und_importiert_leads():
    session = FakeSession([FakeResponse(200, {"id": "camp-1"}),
                           FakeResponse(200, {})])
    sender = InstantlySender("key", session=session)
    campaign_id = sender.create_campaign(KUNDE, TEXTE)
    assert campaign_id == "camp-1"
    kampagne, leads = session.aufrufe
    assert "aktiv" not in str(kampagne).lower() and "{{mail_1}}" in str(kampagne)
    assert leads["leads"][0]["email"] == "t@example.com"

def test_weigert_sich_ohne_texte():
    sender = InstantlySender("key", session=FakeSession([]))
    try:
        sender.create_campaign(KUNDE, [])
        assert False, "haette ValueError werfen muessen"
    except ValueError:
        pass
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_instantly.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren (Payload-Details laut Step 0 an Live-Doku angepasst)**

`pipeline/senders/instantly.py`:
```python
import requests

BASIS = "https://api.instantly.ai/api/v2"

class InstantlySender:
    def __init__(self, api_key, session=None):
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"}

    def create_campaign(self, kunde, texte_pro_lead) -> str:
        if not texte_pro_lead:
            raise ValueError("Keine freigegebenen Texte - keine Kampagne.")
        tage = kunde.follow_up_tage
        sequenz = [
            {"subject": "{{betreff}}", "body": "{{mail_1}}", "delay_days": 0},
            {"subject": "", "body": "{{follow_up_1}}", "delay_days": tage[0]},
            {"subject": "", "body": "{{follow_up_2}}", "delay_days": tage[1]},
        ]
        antwort = self.session.post(f"{BASIS}/campaigns", headers=self.headers, timeout=30,
                                    json={"name": f"[TEST] {kunde.name}",
                                          "status": "paused", "sequence_steps": sequenz})
        campaign_id = antwort.json()["id"]
        leads = [{"email": t["email"],
                  "custom_variables": {k: t[k] for k in
                                       ("betreff", "mail_1", "follow_up_1", "follow_up_2")}}
                 for t in texte_pro_lead]
        self.session.post(f"{BASIS}/leads/import", headers=self.headers, timeout=60,
                          json={"campaign_id": campaign_id, "leads": leads})
        return campaign_id
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/senders tests/test_instantly.py
git commit -m "feat: Instantly-Anbindung (Kampagne pausiert, Leads mit Variablen)"
```

---

### Task 10: Bericht und CLI-Verdrahtung

**Files:**
- Create: `pipeline/report.py`, `pipeline/__main__.py`, `tests/test_report.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: alle bisherigen Bausteine.
- Produces: `write_report(store, zahlen: dict)` → `bericht.md` im Laufordner. CLI: `python -m pipeline lauf kunden/demo-gmbh.yaml [--limit 10]` (Schritte: leads → dedupe → personalisierung → pruefung → Vorschau, dann Stopp), `python -m pipeline freigeben <laufordner>`, `python -m pipeline senden <laufordner>` (verweigert ohne `FREIGABE.txt`; filtert hart auf `kunde.test_empfaenger`). `lauf` überspringt via `RunStore.resume` bereits fertige Schritte, wenn `--fortsetzen <laufordner>` übergeben wird.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`tests/test_report.py`:
```python
from pipeline.run_store import RunStore
from pipeline.report import write_report

def test_bericht_enthaelt_alle_zahlen(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": ["doppelt: 3"]})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    for wert in ("10", "3", "6", "1", "doppelt"):
        assert wert in text
```

`tests/test_cli.py`:
```python
import pytest
from pipeline.__main__ import senden
from pipeline.run_store import RunStore

def test_senden_verweigert_ohne_freigabe(tmp_path):
    store = RunStore(tmp_path, "Demo")
    store.save_step("pruefung_ok", [])
    with pytest.raises(SystemExit, match="Freigabe"):
        senden(store.run_dir)

def test_senden_verweigert_fremde_empfaenger(tmp_path, monkeypatch):
    # Aufbau: freigegebener Lauf, aber ein Empfaenger fehlt in test_empfaenger
    from pipeline.approval import approve
    store = RunStore(tmp_path, "Demo")
    store.save_step("kunde_pfad", {"pfad": "kunden/demo-gmbh.yaml"})
    store.save_step("pruefung_ok", [{"email": "fremd@echt.de", "betreff": "B",
                                     "mail_1": "M", "follow_up_1": "F", "follow_up_2": "F"}])
    approve(store)
    with pytest.raises(SystemExit, match="Test-Empfaenger"):
        senden(store.run_dir)
```

- [ ] **Step 2: Fehlschlag sehen** — Run: `.venv/bin/python -m pytest tests/test_report.py tests/test_cli.py -v` — Expected: FAIL

- [ ] **Step 3: Implementieren**

`pipeline/report.py`:
```python
def write_report(store, zahlen: dict):
    zeilen = ["# Lauf-Bericht", "",
              f"- Gefunden: {zahlen['gefunden']}",
              f"- Verworfen: {zahlen['verworfen']} ({'; '.join(zahlen['gruende_verworfen']) or 'keine'})",
              f"- Personalisiert: {zahlen['personalisiert']}",
              f"- Nacharbeit: {zahlen['nacharbeit']}"]
    (store.run_dir / "bericht.md").write_text("\n".join(zeilen), encoding="utf-8")
```

`pipeline/__main__.py`:
```python
import argparse, os, sys
from collections import Counter
from pathlib import Path
from pipeline.config import load_kunde
from pipeline.run_store import RunStore
from pipeline.sources.apollo import ApolloSource
from pipeline.dedupe import dedupe as dedupe_leads
from pipeline.website import fetch_text
from pipeline.ki import KI
from pipeline.personalize import personalize
from pipeline.quality import check
from pipeline.approval import write_preview, is_approved, approve
from pipeline.report import write_report
from pipeline.senders.instantly import InstantlySender
from pipeline.models import Lead

LAEUFE = Path("laeufe")

def lauf(kunde_pfad: str, limit: int, fortsetzen: str | None):
    kunde = load_kunde(kunde_pfad)
    store = RunStore.resume(fortsetzen) if fortsetzen else RunStore(LAEUFE, kunde.name)
    store.save_step("kunde_pfad", {"pfad": str(kunde_pfad)})
    print(f"Laufordner: {store.run_dir}")

    if not store.step_done("leads"):
        quelle = ApolloSource(os.environ["APOLLO_API_KEY"])
        leads = quelle.search(kunde.zielgruppe, limit)
        store.save_step("leads", [l.__dict__ for l in leads])
    leads = [Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                        "company", "title", "website", "source")})
             for d in store.load_step("leads")]

    if not store.step_done("dedupe"):
        behalten, verworfen = dedupe_leads(leads, store.run_dir.parent, kunde.sperrliste)
        store.save_step("dedupe", {"behalten": [l.__dict__ for l in behalten],
                                   "verworfen": verworfen})
    stand = store.load_step("dedupe")

    if not store.step_done("personalisierung"):
        ki, fertig, nacharbeit = KI(), [], []
        for d in stand["behalten"]:
            lead = Lead(**{k: d[k] for k in ("first_name", "last_name", "email",
                                              "company", "title", "website", "source")})
            try:
                texte = personalize(lead, kunde, ki, fetch_text(lead.website))
                ok, grund = check(texte, lead, kunde, ki)
            except ValueError as fehler:
                ok, grund, texte = False, str(fehler), {}
            if ok:
                fertig.append({"email": lead.email, **texte})
            else:
                nacharbeit.append({"email": lead.email, "grund": grund})
        store.save_step("personalisierung", {"fertig": fertig, "nacharbeit": nacharbeit})
    ergebnis = store.load_step("personalisierung")
    store.save_step("pruefung_ok", ergebnis["fertig"])

    write_preview(store, ergebnis["fertig"], ergebnis["nacharbeit"])
    gruende = [f"{g}: {n}" for g, n in
               Counter(v["grund"] for v in stand["verworfen"]).items()]
    write_report(store, {"gefunden": len(leads), "verworfen": len(stand["verworfen"]),
                         "personalisiert": len(ergebnis["fertig"]),
                         "nacharbeit": len(ergebnis["nacharbeit"]),
                         "gruende_verworfen": gruende})
    print(f"Vorschau: {store.run_dir / 'freigabe-vorschau.md'}")
    print("Naechster Schritt: pruefen, dann 'python -m pipeline freigeben <laufordner>'")

def freigeben(laufordner: str):
    approve(RunStore.resume(laufordner))
    print("Freigegeben. Senden mit: python -m pipeline senden", laufordner)

def senden(laufordner: str):
    store = RunStore.resume(laufordner)
    if not is_approved(store):
        sys.exit("Keine Freigabe fuer diesen Lauf (FREIGABE.txt fehlt).")
    kunde = load_kunde(store.load_step("kunde_pfad")["pfad"])
    texte = store.load_step("pruefung_ok")
    erlaubt = {e.strip().lower() for e in kunde.test_empfaenger}
    fremde = [t["email"] for t in texte if t["email"] not in erlaubt]
    if fremde:
        sys.exit(f"Abbruch: Empfaenger nicht in Test-Empfaenger-Liste: {fremde}")
    sender = InstantlySender(os.environ["INSTANTLY_API_KEY"])
    campaign_id = sender.create_campaign(kunde, texte)
    store.save_step("versand", {"campaign_id": campaign_id})
    print(f"Kampagne {campaign_id} pausiert angelegt - Aktivierung von Hand in Instantly.")

def main():
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="befehl", required=True)
    p_lauf = sub.add_parser("lauf")
    p_lauf.add_argument("kunde")
    p_lauf.add_argument("--limit", type=int, default=10)
    p_lauf.add_argument("--fortsetzen", default=None)
    for name in ("freigeben", "senden"):
        p = sub.add_parser(name)
        p.add_argument("laufordner")
    args = parser.parse_args()
    if args.befehl == "lauf":
        lauf(args.kunde, args.limit, args.fortsetzen)
    elif args.befehl == "freigeben":
        freigeben(args.laufordner)
    else:
        senden(args.laufordner)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Tests bestehen sehen** — Run: `.venv/bin/python -m pytest -v` — Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/report.py pipeline/__main__.py tests/
git commit -m "feat: Bericht und CLI mit Freigabe-Sperre"
```

---

### Task 11: Echter End-zu-End-Nachweis (mit Leonard)

Kein Code — das ist der Beweis aus dem Design. **Vorab-Okay von Leonard nötig** für: Kauf der Test-Domain (~10–15 €/Jahr), Anlegen der Test-Postfächer, Schreibzugriff aufs Team-Instantly.

- [ ] **Step 1: Test-Empfänger anlegen** — je ein Gmail-, ein Outlook- und ein Eigene-Domain-Postfach; Adressen in `kunden/demo-gmbh.yaml` unter `test_empfaenger` eintragen.
- [ ] **Step 2: Versand-Seite einrichten** — Test-Domain kaufen, in Instantly ein Test-Postfach dieser Domain verbinden, Warmup einschalten (Anwärmzeit einplanen; Details laut Instantly-Doku).
- [ ] **Step 3: Lauf fahren** — `python -m pipeline lauf kunden/demo-gmbh.yaml --limit 5`; da die Demo-Zielgruppe echte Apollo-Treffer liefert, die Test-Lead-Liste danach im Laufordner von Hand auf die Test-Empfänger umbiegen (dokumentierter v1-Kniff: `leads.json` editieren, `--fortsetzen` nutzen) — so wird mit echten Apollo-Daten personalisiert, aber nur an Test-Postfächer gesendet.
- [ ] **Step 4: Vorschau prüfen und freigeben** — Leonard liest `freigabe-vorschau.md`, dann `freigeben`, dann `senden`, dann Kampagne in Instantly von Hand aktivieren.
- [ ] **Step 5: Beweis sammeln** — Screenshots: Mail im Posteingang (nicht Spam) aller drei Test-Postfächer, Follow-up nach dem konfigurierten Abstand, `bericht.md` deckt sich mit der Realität. Ergebnis in `project-context.md` festhalten, Jira AP-195 auf erledigt setzen.

---

## Selbst-Review (nach dem Schreiben geprüft)

- Spec-Abdeckung: Lead-Quelle (T4), Mehrquellen-Format (T2/T4-Schnittstelle), Dedupe+Sperrliste+Verifizierungs-Erweiterungspunkt (T5, Sperrliste aus Wholix-Analyse nachgezogen), Personalisierung+Prompts (T6), Angebots-Analyse der eigenen Webseite (T6b, aus interner Notiz nachgezogen), Prüfung+Nacharbeit (T7), Freigabe (T8), Versand+Follow-ups mit Schutz-Voreinstellungen (T9), Bericht+Wiederaufnahme (T3/T10), Testnachweis (T11). Keine Lücke gefunden.
- Typ-Konsistenz: `RunStore`-Methoden, `Lead`-Felder und Textpaket-Schlüssel (`betreff, mail_1, follow_up_1, follow_up_2`) sind in T3–T10 einheitlich benannt.
- Bekannte bewusste Abkürzung: Der Test-Lauf biegt die Lead-Liste von Hand auf Test-Empfänger um (T11 Step 3) — akzeptiert für v1, die harte Sperre in `senden` schützt unabhängig davon.

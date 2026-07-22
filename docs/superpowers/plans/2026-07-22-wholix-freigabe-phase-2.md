# Wholix-Freigabe Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Wholix-ähnliche Prüftabelle bestätigt jeden der drei Texte pro Empfänger einzeln, übergibt nur vollständig bestätigte Runden und zeigt danach belegbare Instantly-Daten; die Sperrliste erhält Grund, Kommentar und sichere Platzhalter-Regeln.

**Architecture:** Ein neuer `FreigabeStatusStore` hält stabile Empfängerkennungen, Inhalts-Hashes, Bestätigungen und einzelne Text-Neuerzeugungen atomar im Laufordner. Die bestehenden FastAPI-Routen bleiben die Sicherheitsgrenze und nutzen weiterhin den vorhandenen Instantly-Übergabeweg; ein kleiner reiner Übersetzer bereitet paginierte Instantly-Leads und -E-Mails für die Anzeige auf. Die Sperrliste liest alte Zeichenketten und neue strukturierte Einträge, während die Pipeline weiterhin nur Domain-Muster erhält.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, requests, PyYAML, pytest, vorhandenes CSS und kleines JavaScript ohne neue Laufzeit-Abhängigkeit.

## Global Constraints

- Zuverlässigkeit hat Vorrang vor Schnelligkeit und Sparsamkeit.
- Eine Prüftabelle zeigt immer genau eine E-Mail-Runde beziehungsweise Zielgruppe.
- Jede Runde enthält pro Empfänger genau `mail_1`, `follow_up_1` und `follow_up_2`.
- Die endgültige Instantly-Übergabe bleibt eine unteilbare Aktion für die komplette Runde.
- Ein unbekannter externer Wert bleibt `None` und erscheint als `—`; er wird weder als Null noch aus anderen Daten abgeleitet.
- Nach der Übergabe sind Texte und Bestätigungen schreibgeschützt.
- Echte Empfänger, echte Sendungen und verändernde Prüfungen am echten Instantly-Konto sind ausgeschlossen.
- Automatische Prüfungen verwenden Testdaten und nachgebildete externe Antworten.
- Jede Fachänderung beginnt mit einem sichtbar fehlschlagenden Test.
- Nach jeder Aufgabe werden die betroffenen Tests ausgeführt und die Änderung einzeln festgehalten.
- Bildschirmfotos werden nur mit einem eigens angelegten lokalen Test-Datenordner erzeugt.

---

### Task 1: Dauerhafter Freigabezustand je Empfänger und Schritt

**Files:**

- Create: `web/freigabe_status.py`
- Create: `tests/web/test_freigabe_status.py`

**Interfaces:**

- Consumes: `lauf_dir: Path`, die Liste aus `pruefung_ok.json` und optional die frühere Gesamtfreigabe aus `FREIGABE.txt`.
- Produces: `FreigabeStatusStore.ansicht(texte, alte_freigabe=None)`, `bestaetigungen_setzen(...)`, `override_setzen(..., qa_cleared=False, qa_reason=None)`, `materialisieren(texte)` und `alles_bestaetigt(texte)`.
- Produces: `VeralteterStand`, damit jede Route einen überholten Seitenstand ohne Mutation abweisen kann.

- [ ] **Step 1: Tests für Initialisierung, Hash-Abgleich und Rückwärtsübernahme schreiben**

```python
from datetime import datetime

import pytest

from web.freigabe_status import FreigabeStatusStore, VeralteterStand


TEXTE = [{
    "email": "anna@firma.de",
    "betreff": "Kurze Frage",
    "mail_1": "Hallo Anna",
    "follow_up_1": "Kurze Erinnerung",
    "follow_up_2": "Letzte Nachricht",
}]


def test_initialisiert_feste_id_und_drei_offene_schritte(tmp_path):
    store = FreigabeStatusStore(
        tmp_path, jetzt=lambda: datetime(2026, 7, 22, 10, 0),
        id_factory=lambda: "empf-1",
    )
    ansicht = store.ansicht(TEXTE)

    assert ansicht["recipients"][0]["id"] == "empf-1"
    assert ansicht["recipients"][0]["steps"] == {
        "mail_1": {"approved": False, "approved_at": None, "approved_by": None},
        "follow_up_1": {"approved": False, "approved_at": None, "approved_by": None},
        "follow_up_2": {"approved": False, "approved_at": None, "approved_by": None},
    }
    assert (tmp_path / "freigabe-status.json").is_file()


def test_alte_gesamtfreigabe_wird_einmalig_als_bestaetigt_uebernommen(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    ansicht = store.ansicht(
        TEXTE,
        alte_freigabe={"von": "Lena Hartmann", "am": "22.07.2026, 10:00"},
    )

    assert all(s["approved"] for s in ansicht["recipients"][0]["steps"].values())
    assert ansicht["recipients"][0]["steps"]["mail_1"]["approved_by"] == "Lena Hartmann"
```

- [ ] **Step 2: Tests ausführen und den erwarteten Importfehler sehen**

Run:

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe_status.py -q
```

Expected: `FAIL` mit `ModuleNotFoundError: No module named 'web.freigabe_status'`.

- [ ] **Step 3: Statusdatei, stabile Kennungen und kanonische Hashes bauen**

`web/freigabe_status.py` erhält diese öffentliche Form:

```python
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path

SCHRITTE = ("mail_1", "follow_up_1", "follow_up_2")
DATEINAME = "freigabe-status.json"
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class VeralteterStand(ValueError):
    pass


def _inhalt(texte: dict, schritt: str) -> dict[str, str]:
    if schritt == "mail_1":
        return {"betreff": texte.get("betreff", ""), "text": texte.get("mail_1", "")}
    return {"text": texte.get(schritt, "")}


def inhalts_hash(texte: dict, schritt: str) -> str:
    roh = json.dumps(_inhalt(texte, schritt), ensure_ascii=False,
                     sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(roh.encode("utf-8")).hexdigest()


def _atomar_speichern(pfad: Path, daten: dict) -> None:
    with tempfile.NamedTemporaryFile(
        "w", dir=pfad.parent, prefix=f".{pfad.name}-", suffix=".tmp",
        delete=False, encoding="utf-8",
    ) as tmp:
        json.dump(daten, tmp, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_pfad = Path(tmp.name)
    os.replace(temp_pfad, pfad)


def _lock_fuer(lauf_dir: Path) -> threading.RLock:
    key = str(lauf_dir.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class FreigabeStatusStore:
    def __init__(self, lauf_dir: Path, *, jetzt=None, id_factory=None):
        self.lauf_dir = Path(lauf_dir)
        self.pfad = self.lauf_dir / DATEINAME
        self._jetzt = jetzt or datetime.now
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))
        self.lock = _lock_fuer(self.lauf_dir)
```

Die privaten Helfer `_laden()`, `_abgleichen(texte, alte_freigabe)` und `_revision(daten, texte)` halten folgende Regeln vollständig ein:

```python
def _leerer_schritt() -> dict:
    return {
        "approved": False,
        "approved_at": None,
        "approved_by": None,
        "content_hash": None,
        "override": None,
    }


def _revision(daten: dict, texte: list[dict]) -> str:
    roh = json.dumps({"status": daten, "texte": texte}, ensure_ascii=False,
                     sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()
```

`_abgleichen` sucht einen vorhandenen Empfänger über das gespeicherte Feld `email_key`, erzeugt nur beim ersten Auftreten eine zufällige `id` und speichert die Empfänger unter dieser ID. Ein nicht mehr vorhandener Empfänger bleibt in der Datei als historischer Eintrag, erscheint aber nicht in `ansicht()`. Bei einem Hash-Unterschied setzt `_abgleichen` nur den betroffenen Schritt auf unbestätigt. `override` wird vor dem Hash auf den Grundtext gelegt. Existiert die Datei noch nicht und `alte_freigabe` ist gesetzt, werden alle vorhandenen Schritte mit Name/Zeit der alten Freigabe bestätigt.

- [ ] **Step 4: Mutations- und Materialisierungs-Tests ergänzen**

```python
def test_textaenderung_macht_nur_einen_schritt_offen(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    start = store.ansicht(TEXTE)
    store.bestaetigungen_setzen(
        TEXTE, ["empf-1"], actor="Lena", approved=True,
        revision=start["revision"], step=None,
    )
    geaendert = [{**TEXTE[0], "follow_up_1": "Neue Erinnerung"}]

    ansicht = store.ansicht(geaendert)
    steps = ansicht["recipients"][0]["steps"]
    assert steps["mail_1"]["approved"] is True
    assert steps["follow_up_1"]["approved"] is False
    assert steps["follow_up_2"]["approved"] is True


def test_veraltete_revision_veraendert_nichts(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    start = store.ansicht(TEXTE)
    store.bestaetigungen_setzen(TEXTE, ["empf-1"], actor="Lena", approved=True,
                                revision=start["revision"], step="mail_1")

    with pytest.raises(VeralteterStand):
        store.bestaetigungen_setzen(TEXTE, ["empf-1"], actor="Lena", approved=True,
                                    revision=start["revision"], step="follow_up_1")


def test_override_ersetzt_nur_gewaehlten_schritt(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    start = store.ansicht(TEXTE)
    store.override_setzen(
        TEXTE, "empf-1", "mail_1",
        {"betreff": "Neu", "text": "Neuer Erstkontakt"}, start["revision"],
    )

    materialisiert = store.materialisieren(TEXTE)
    assert materialisiert[0] == {
        **TEXTE[0], "betreff": "Neu", "mail_1": "Neuer Erstkontakt",
    }
```

- [ ] **Step 5: Öffentliche Methoden vollständig ergänzen und Tests grün machen**

`bestaetigungen_setzen` arbeitet unter `self.lock`, gleicht den aktuellen Inhalt ab, vergleicht die Revision und ändert entweder einen angegebenen Schritt oder alle drei Schritte der ausgewählten Empfänger. `approved=True` speichert Name, ISO-Zeit und aktuellen Hash; `approved=False` leert diese drei Werte. `override_setzen` akzeptiert für `mail_1` genau `betreff` und `text`, für Follow-ups genau `text`, setzt nur dort `override` und hebt nur dort die Bestätigung auf. `materialisieren` gibt die ursprüngliche Reihenfolge und die unveränderte E-Mail-Adresse zurück. Alle schreibenden Methoden verwenden `_atomar_speichern`.

Ein Grundtext darf zusätzlich die internen Felder `_qa_blocked=True` und `_qa_reason` tragen. Der Store übernimmt daraus beim ersten Abgleich `qa_blocked` und `qa_reason`, lässt für einen blockierten Empfänger keine Bestätigung zu und liefert `alles_bestaetigt=False`. Nur `override_setzen(..., qa_cleared=True)` setzt `qa_blocked=False`; dieser Parameter darf ausschließlich nach einer erfolgreichen Prüfung der vollständigen Kandidaten-Sequenz verwendet werden. Bei `qa_cleared=False` bleibt oder wird der Empfänger blockiert und `qa_reason` wird sichtbar gespeichert. Die internen `_qa_*`-Felder erscheinen nie in `materialisieren()` und werden nie an Instantly übergeben.

```python
def test_qa_blockierter_empfaenger_kann_nicht_bestaetigt_werden(tmp_path):
    store = FreigabeStatusStore(tmp_path, id_factory=lambda: "empf-1")
    blockiert = [{**TEXTE[0], "_qa_blocked": True, "_qa_reason": "Betreff zu lang"}]
    start = store.ansicht(blockiert)

    with pytest.raises(ValueError, match="Nacharbeit"):
        store.bestaetigungen_setzen(
            blockiert, ["empf-1"], actor="Lena", approved=True,
            revision=start["revision"], step=None,
        )

    assert store.alles_bestaetigt(blockiert) is False
```

Run:

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe_status.py -q
```

Expected: alle Tests in der Datei bestehen.

- [ ] **Step 6: Aufgabe festhalten**

```bash
git add web/freigabe_status.py tests/web/test_freigabe_status.py
git commit -m "feat: persist per-step approval state"
```

---

### Task 2: Rundenübersicht und serverseitige Prüftabellen-Daten

**Files:**

- Modify: `web/wartende.py:52-81`
- Modify: `web/routen/freigabe.py:127-237`
- Modify: `tests/web/test_freigabe.py:114-247`

**Interfaces:**

- Consumes: `FreigabeStatusStore`, `Laufmanager.status()`, `pruefung_ok.json` und bestehende Kundendaten.
- Produces: `pruefbare_laeufe(daten_dir) -> {"offen": list, "uebergeben": list}`.
- Produces: `_lese_kontext()` mit `empfaenger[*].id`, `steps`, `status`, `revision`, `fortschritt`, `schreibgeschuetzt` und `uebergabe_bereit`; auch vorhandene Nacharbeits-Empfänger stehen in derselben Runde.

- [ ] **Step 1: Fehlende Übersichts- und Kontexttests schreiben**

```python
def test_liste_trennt_offene_und_uebergebene_runden(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, ts="20260717-090000")
    _lauf_anlegen(
        daten_dir, ts="20260718-090000", freigegeben=True,
        versand_komplett={"campaign_id": "camp-1"},
    )

    antwort = angemeldeter_client.get("/pruefen")

    assert antwort.status_code == 200
    assert "Offen" in antwort.text
    assert "Übergeben" in antwort.text
    assert "/pruefen/test-gmbh/20260717-090000" in antwort.text
    assert "/pruefen/test-gmbh/20260718-090000" in antwort.text


def test_lese_kontext_zeigt_drei_schritte_und_stabile_empfaenger_id(
    angemeldeter_client, daten_dir
):
    _lauf_anlegen(daten_dir)

    erste = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    zweite = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")

    assert erste.status_code == 200
    assert 'data-recipient-id="' in erste.text
    assert "E-Mail 1" in erste.text
    assert "Follow-up 1" in erste.text
    assert "Follow-up 2" in erste.text
    assert erste.text.split('data-recipient-id="', 1)[1].split('"', 1)[0] == (
        zweite.text.split('data-recipient-id="', 1)[1].split('"', 1)[0]
    )
```

- [ ] **Step 2: Tests ausführen und die erwarteten fehlenden Bereiche sehen**

Run:

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe.py -q
```

Expected: die neuen Tests schlagen wegen fehlender Bereiche und Tabellenmerkmale fehl; bestehende Tests bleiben grün.

- [ ] **Step 3: `pruefbare_laeufe` als gemeinsame Aggregation ergänzen**

`web/wartende.py` behält `wartende_laeufe()` für Dashboard und Badge unverändert. Die neue Funktion scannt dieselben sicheren Laufpfade und ordnet Zustände so zu:

```python
def pruefbare_laeufe(daten_dir) -> dict[str, list[dict]]:
    gruppen = {"offen": [], "uebergeben": []}
    manager = Laufmanager(daten_dir)
    wurzel = Path(daten_dir) / "laeufe"
    if not wurzel.is_dir():
        return gruppen
    for kunden_ordner in sorted((p for p in wurzel.iterdir() if p.is_dir()), reverse=True):
        for lauf_dir in sorted((p for p in kunden_ordner.iterdir() if p.is_dir()), reverse=True):
            stand = manager.status(lauf_dir)
            if stand["zustand"] not in {"wartet_auf_freigabe", "freigegeben", "uebergeben"}:
                continue
            gruppe = "uebergeben" if stand["zustand"] == "uebergeben" else "offen"
            # Kunde, Texte und FreigabeStatusStore defensiv laden; beschädigte
            # Daten ergeben einen sichtbaren Warnungs-Eintrag statt eines 500ers.
            gruppen[gruppe].append(eintrag)
    return gruppen
```

Jeder `eintrag` enthält `slug`, `ts`, `kunde_name`, `empfaenger`, `bestaetigt`, `offen`, `nacharbeit`, `zustand`, `geaendert_text` und `warnung`. Für alte bereits freigegebene Runden wird `freigabe_info(store)` an `FreigabeStatusStore.ansicht()` gegeben.

- [ ] **Step 4: `_lese_kontext` auf wirksame Texte und Schrittmodelle umstellen**

Die bestehende `_empfaenger_liste` erhält zusätzlich `status_ansicht` und baut je Empfänger:

```python
{
    "id": status_empfaenger["id"],
    "email": text["email"],
    "name": name or text["email"],
    "firma": info.get("company", ""),
    "rolle": info.get("title", ""),
    "status": "fertig" if alle_bestaetigt else "offen",
    "steps": [
        {"key": "mail_1", "label": "E-Mail 1", "betreff": text["betreff"],
         "text": text["mail_1"], **status_steps["mail_1"]},
        {"key": "follow_up_1", "label": "Follow-up 1", "betreff": "",
         "text": text["follow_up_1"], **status_steps["follow_up_1"]},
        {"key": "follow_up_2", "label": "Follow-up 2", "betreff": "",
         "text": text["follow_up_2"], **status_steps["follow_up_2"]},
    ],
}
```

`_grundtexte(lauf_dir)` führt `pruefung_ok` und `personalisierung.nacharbeit` anhand der normalisierten E-Mail-Adresse zu genau einer Liste zusammen. Fertige Einträge bleiben unverändert; Nacharbeits-Einträge erhalten intern `_qa_blocked=True` und `_qa_reason=<grund>`. Ein doppelter Empfänger oder ein Nacharbeits-Eintrag ohne vollständige Sequenz erzeugt einen sichtbaren Datenfehler und blockiert die Übergabe.

`_lese_kontext` lädt diese Grundtexte, ruft `status_store.ansicht(...)` auf, materialisiert danach wirksame Texte und gibt Revision/Fortschritt mit. Zeilen haben `status="fertig"`, `status="offen"` oder `status="nacharbeit"`. Eine fehlende E-Mail, ein leerer Pflichttext oder ein ungelöster QA-Block setzt `uebergabe_bereit=False` und erzeugt eine deutsche Warnung.

- [ ] **Step 5: Betroffene Tests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe.py tests/web/test_freigabe_status.py tests/web/test_dashboard.py -q
```

Expected: alle genannten Tests bestehen.

- [ ] **Step 6: Aufgabe festhalten**

```bash
git add web/wartende.py web/routen/freigabe.py tests/web/test_freigabe.py
git commit -m "feat: prepare round-based approval table data"
```

---

### Task 3: Einzel- und Mehrfachbestätigung mit harter Übergabesperre

**Files:**

- Modify: `web/routen/freigabe.py:296-387`
- Modify: `tests/web/test_freigabe.py:252-445`

**Interfaces:**

- Consumes: `FreigabeStatusStore.bestaetigungen_setzen`, Formularfelder `revision`, `recipient_ids`, `step` und `action`.
- Produces: `POST /pruefen/{slug}/{ts}/bestaetigen` für einen Schritt.
- Produces: `POST /pruefen/{slug}/{ts}/mehrfach` für alle Schritte ausgewählter Empfänger.
- Preserves: `_versand_ausfuehren`, Test-Empfänger-Schranke, `FREIGABE.txt`, Audit-Trail und Doppelklick-Sperre.

- [ ] **Step 1: Tests für Einzelaktion, Mehrfachaktion und veraltete Seite schreiben**

```python
def _revision_aus(antwort) -> str:
    return antwort.text.split('name="revision" value="', 1)[1].split('"', 1)[0]


def _erste_empfaenger_id(antwort) -> str:
    return antwort.text.split('data-recipient-id="', 1)[1].split('"', 1)[0]


def test_einzelner_schritt_bleibt_nach_neuladen_bestaetigt(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir)
    seite = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/bestaetigen",
        data={"revision": _revision_aus(seite), "recipient_id": _erste_empfaenger_id(seite),
              "step": "mail_1", "approved": "1"},
        follow_redirects=False,
    )

    assert antwort.status_code == 303
    neu = angemeldeter_client.get(antwort.headers["location"])
    assert 'data-step="mail_1" data-approved="true"' in neu.text


def test_veraltete_mehrfachaktion_wird_ohne_mutation_abgewiesen(
    angemeldeter_client, daten_dir
):
    _lauf_anlegen(daten_dir)
    alt = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    rid = _erste_empfaenger_id(alt)
    angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/bestaetigen",
        data={"revision": _revision_aus(alt), "recipient_id": rid,
              "step": "mail_1", "approved": "1"},
    )

    konflikt = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/mehrfach",
        data={"revision": _revision_aus(alt), "recipient_ids": rid, "action": "approve"},
    )

    assert konflikt.status_code == 409
    assert "neu geladen" in konflikt.text
```

- [ ] **Step 2: Tests ausführen und 404 für die neuen Routen sehen**

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe.py -q
```

Expected: die neuen Mutations-Tests schlagen fehl, weil die Routen noch fehlen.

- [ ] **Step 3: Mutationsrouten mit Zustandswächter ergänzen**

Beide Routen prüfen vor der Änderung `zustand == "wartet_auf_freigabe"`. `step` darf nur in `SCHRITTE` liegen, `action` nur in `{"approve", "clear"}`. Unbekannte Empfängerkennungen liefern 400. `VeralteterStand` liefert dieselbe Seite mit Status 409 und dem Text „Die E-Mail-Runde wurde inzwischen geändert. Die Seite wurde neu geladen; bitte prüfe deine Auswahl noch einmal.“

```python
@router.post("/pruefen/{slug}/{ts}/bestaetigen")
def schritt_bestaetigen(request: Request, slug: str, ts: str,
                         revision: str = Form(...), recipient_id: str = Form(...),
                         step: str = Form(...), approved: str = Form("1")):
    lauf_dir = _lauf_dir_oder_404(request.app.state.daten_dir, slug, ts)
    _schreibzustand_pruefen(request, lauf_dir)
    texte = _grundtexte(lauf_dir)
    FreigabeStatusStore(lauf_dir).bestaetigungen_setzen(
        texte, [recipient_id], actor=auth.aktueller_nutzer(request),
        approved=approved == "1", revision=revision, step=step,
    )
    return RedirectResponse(f"/pruefen/{slug}/{ts}", status_code=303)
```

Die Mehrfachroute ruft dieselbe Store-Methode mit allen `recipient_ids` und `step=None` auf. Leere Auswahl liefert 400 und verändert nichts.

- [ ] **Step 4: Die alte Checkliste durch den serverseitigen Vollständigkeitsnachweis ersetzen**

Der bisherige Formularparameter `checkliste` und `CHECKLISTE_FEHLER` entfallen. `freigabe_absenden` führt unter `status_store.lock` und danach unter der bestehenden Versand-Sperre aus:

```python
status_store = FreigabeStatusStore(lauf_dir)
with status_store.lock:
    zustand = _manager(request).status(lauf_dir)["zustand"]
    if zustand not in ZUSTAND_ERLAUBT_FREIGEBEN:
        return _fehlerseite(request, slug, ts, _zustand_fehler("Freigeben", zustand), 400)
    if is_approved(store):
        return _bereits_freigegeben_antwort(request, slug, ts, store)
    grundtexte = _grundtexte(lauf_dir)
    if not status_store.alles_bestaetigt(grundtexte):
        return _fehlerseite(request, slug, ts,
                            "Noch nicht alle E-Mails sind bestätigt oder eine Nacharbeit ist offen.", 400)
    wirksame_texte = status_store.materialisieren(grundtexte)
    _pflichttexte_pruefen(wirksame_texte)
    store.save_step("pruefung_ok", wirksame_texte)
    approve(store, name=auth.aktueller_nutzer(request))
    return _versand_antwort(request, slug, ts)
```

Zustands- und Audit-Wächter liegen damit innerhalb derselben Status-Sperre wie Prüfung und Freigabe. Zwei gleichzeitige Abschlussanfragen können den Audit-Trail nicht überschreiben; die zweite sieht nach der ersten zuverlässig `is_approved=True`. `_pflichttexte_pruefen` verlangt pro Empfänger eine E-Mail-Adresse und alle vier Versandfelder einschließlich Betreff. `alles_bestaetigt` verlangt zusätzlich, dass kein Empfänger mehr `qa_blocked=True` hat. Bei einem Fehler wird weder `pruefung_ok` überschrieben noch `approve()` oder Instantly aufgerufen.

- [ ] **Step 5: Bestehende Versandtests auf die neue echte Voraussetzung umstellen**

Der Testhelfer `_alle_bestaetigen(client, slug, ts)` lädt die Seite, sammelt alle `data-recipient-id` und sendet genau eine Mehrfachaktion. Tests, die den erfolgreichen Versand erwarten, rufen diesen Helfer vorher auf. Der bisherige „ohne alle Haken“-Test wird zu:

```python
def test_unvollstaendig_bestaetigte_runde_sendet_auch_bei_direktem_post_nichts(
    angemeldeter_client, daten_dir, app
):
    _lauf_anlegen(daten_dir)
    fake = FakeInstantly()
    app.state.instantly = fake

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben"
    )

    assert antwort.status_code == 400
    assert "Noch nicht alle E-Mails" in antwort.text
    assert fake.aufrufe == []
    assert not (daten_dir / "laeufe" / KUNDE_SLUG / "20260717-090000" / "FREIGABE.txt").exists()
```

Der vorhandene Doppelklick-Test wird außerdem um zwei gleichzeitige erste `POST /freigeben` erweitert. Erwartet werden genau ein `create_campaign`-Aufruf und genau der Name/Zeitpunkt der ersten Freigabe in `FREIGABE.txt`; die zweite Antwort darf den Audit-Trail nicht überschreiben.

- [ ] **Step 6: Sicherheitskritische Tests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe.py tests/test_cli.py -q
```

Expected: Einzel-/Mehrfachaktionen, direkte unvollständige Anfrage, Audit-Trail, Test-Empfänger-Schranke und Doppelklick-Schutz bestehen.

- [ ] **Step 7: Aufgabe festhalten**

```bash
git add web/routen/freigabe.py tests/web/test_freigabe.py
git commit -m "feat: gate handoff on per-step approvals"
```

---

### Task 4: Genau einen Text sicher neu erzeugen

**Files:**

- Create: `prompts/einzelnen-schritt-neu.md`
- Modify: `pipeline/personalize.py:1-31`
- Modify: `tests/test_personalize.py`
- Modify: `web/routen/freigabe.py`
- Modify: `tests/web/test_freigabe.py`

**Interfaces:**

- Produces: `regenerate_step(lead, kunde, ki, webseiten_text, aktuelle_texte, schritt) -> dict`.
- Produces: `POST /pruefen/{slug}/{ts}/neu-erzeugen` mit `revision`, `recipient_id` und `step`.
- Preserves: Bei Erzeugungs-, Webseiten- oder Speicherausfall bleiben alter Text und Bestätigung unverändert. Ein erfolgreich erzeugter, aber noch nicht qualitätsfreier Text wird gespeichert und bleibt sichtbar als Nacharbeit blockiert.

- [ ] **Step 1: Pipeline-Tests für die schrittgenaue KI-Antwort schreiben**

```python
def test_regenerate_step_erwartet_beim_ersten_text_betreff_und_text():
    ki = FakeKI('{"betreff": "Neue Frage", "text": "Neuer Text"}')

    ergebnis = regenerate_step(
        LEAD, KUNDE, ki, "Wir bauen Rohre.",
        {"betreff": "Alt", "mail_1": "Alt", "follow_up_1": "F1", "follow_up_2": "F2"},
        "mail_1",
    )

    assert ergebnis == {"betreff": "Neue Frage", "text": "Neuer Text"}
    assert "Ändere ausschließlich E-Mail 1" in ki.prompt


def test_regenerate_step_lehnt_unvollstaendige_antwort_ab():
    with pytest.raises(ValueError, match="KI-Antwort unvollständig"):
        regenerate_step(LEAD, KUNDE, FakeKI('{"text": "ohne Betreff"}'), "", TEXTE, "mail_1")
```

- [ ] **Step 2: Tests ausführen und den fehlenden Import sehen**

```bash
'.venv/bin/python' -m pytest tests/test_personalize.py -q
```

Expected: `FAIL`, weil `regenerate_step` noch fehlt.

- [ ] **Step 3: Festen Einzel-Schritt-Prompt und Parser ergänzen**

`prompts/einzelnen-schritt-neu.md` enthält alle vorhandenen Angebots-, Zielgruppen-, Empfänger- und Webseitenfelder sowie die komplette aktuelle Sequenz. Die Anweisung benennt den gewählten Schritt ausgeschrieben, verbietet Änderungen an den anderen Schritten und verlangt ausschließlich JSON.

```python
EINZEL_PROMPT_DATEI = Path(__file__).parent.parent / "prompts" / "einzelnen-schritt-neu.md"
SCHRITT_LABELS = {
    "mail_1": "E-Mail 1",
    "follow_up_1": "Follow-up 1",
    "follow_up_2": "Follow-up 2",
}


def regenerate_step(lead, kunde, ki, webseiten_text: str,
                    aktuelle_texte: dict, schritt: str) -> dict:
    if schritt not in SCHRITT_LABELS:
        raise ValueError("Unbekannter E-Mail-Schritt.")
    prompt = EINZEL_PROMPT_DATEI.read_text(encoding="utf-8").format(
        schritt=SCHRITT_LABELS[schritt], absender=kunde.absender,
        kunde_name=kunde.name, angebot=kunde.angebot, tonalitaet=kunde.tonalitaet,
        anrede_name=f"{lead.first_name} {lead.last_name}", titel=lead.title,
        firma=lead.company, webseiten_text=webseiten_text or "(leer)",
        aktuelle_texte=json.dumps(aktuelle_texte, ensure_ascii=False),
    )
    roh = ki.frage(SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", roh, re.DOTALL)
    try:
        daten = json.loads(treffer.group(0)) if treffer else {}
    except ValueError:
        daten = {}
    pflicht = ("betreff", "text") if schritt == "mail_1" else ("text",)
    if any(not isinstance(daten.get(k), str) or not daten[k].strip() for k in pflicht):
        raise ValueError(f"KI-Antwort unvollständig für {lead.email}")
    return {k: daten[k].strip() for k in pflicht}
```

- [ ] **Step 4: Routentests für Erfolg und alle unveränderten Fehlerwege schreiben**

```python
def test_neu_erzeugen_ersetzt_nur_den_gewaehlten_schritt_und_hebt_nur_dessen_haken_auf(
    angemeldeter_client, daten_dir, app
):
    _lauf_anlegen(daten_dir)
    app.state.ki = FakeKI('{"text": "Neue Erinnerung"}')
    app.state.webseiten_leser = lambda url: "Test-Webseite"
    seite = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    rid = _erste_empfaenger_id(seite)
    _empfaenger_bestaetigen(angemeldeter_client, seite, rid)
    frisch = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/neu-erzeugen",
        data={"revision": _revision_aus(frisch), "recipient_id": rid,
              "step": "follow_up_1"},
        follow_redirects=False,
    )

    assert antwort.status_code == 303
    neu = angemeldeter_client.get(antwort.headers["location"])
    assert "Neue Erinnerung" in neu.text
    assert 'data-step="mail_1" data-approved="true"' in neu.text
    assert 'data-step="follow_up_1" data-approved="false"' in neu.text
    assert "Nachfass zwei an Anna" in neu.text
```

Ein zweiter Test lässt `ki.frage` `RuntimeError` werfen. Er vergleicht `freigabe-status.json` vor/nach der Anfrage bytegenau und prüft, dass der alte Text weiterhin erscheint. Ein dritter Test liefert eine vom Qualitätsprüfer abgelehnte Gesamtsequenz: Der erfolgreich erzeugte Schritt bleibt sichtbar gespeichert, seine Bestätigung ist offen, die Zeile trägt weiter `status="nacharbeit"`, der neue Prüfgrund ist sichtbar und die Übergabe bleibt gesperrt. So können bei einer anfangs unvollständigen Sequenz mehrere fehlende Schritte nacheinander erzeugt werden.

- [ ] **Step 5: Route mit Zwei-Phasen-Prüfung bauen**

Die Route ist wie der bestehende Versand eine normale synchrone `def`-Route, damit Webseiten- und KI-Aufruf nicht den FastAPI-Ereignisablauf blockieren. Sie prüft zuerst Zustand und Revision, liest dann Empfänger/Kunde außerhalb der Dateisperre und ruft den externen Webseitenleser und die KI auf. Der neue Schritt wird in eine vollständige Kandidaten-Sequenz eingesetzt. Ist die Sequenz vollständig, wird sie mit `pipeline.quality.check` geprüft; bei noch fehlenden Schritten lautet der neue QA-Grund „Weitere E-Mail-Schritte fehlen“. Danach wird unter `status_store.lock` die Revision erneut geprüft und `override_setzen` genau einmal aufgerufen: bei erfolgreicher Gesamtprüfung mit `qa_cleared=True`, sonst mit `qa_cleared=False, qa_reason=<grund>`. Dadurch wird ein vorhandener Nacharbeits-Block nur dann aufgehoben, wenn die komplette neue Sequenz die Qualitätsprüfung besteht. Hat sich der Stand während des externen Aufrufs geändert, wird die KI-Antwort verworfen und Status 409 gezeigt.

```python
def _hole_ki(request: Request):
    ki = getattr(request.app.state, "ki", None)
    if ki is not None:
        return ki
    from pipeline.ki import KI
    return KI()


def _hole_webseiten_leser(request: Request):
    leser = getattr(request.app.state, "webseiten_leser", None)
    if leser is not None:
        return leser
    from pipeline.website import fetch_text
    return fetch_text
```

Gefangen werden nur erwartete `ValueError`, `RuntimeError`, `requests.RequestException` und `OSError`. Programmierfehler laufen wie beim Versand weiter und werden nicht als KI-Ausfall versteckt.

- [ ] **Step 6: Pipeline- und Routenprüfungen ausführen**

```bash
'.venv/bin/python' -m pytest tests/test_personalize.py tests/web/test_freigabe.py -q
```

Expected: neue Erzeugung, abgelehnte Erzeugung, Ausfall, Revision und unveränderte übrige Schritte bestehen.

- [ ] **Step 7: Aufgabe festhalten**

```bash
git add prompts/einzelnen-schritt-neu.md pipeline/personalize.py tests/test_personalize.py web/routen/freigabe.py tests/web/test_freigabe.py
git commit -m "feat: regenerate one approved email step safely"
```

---

### Task 5: Belegbare Versand- und Antwortdaten aus Instantly

**Files:**

- Create: `web/instantly_freigabe.py`
- Create: `tests/web/test_instantly_freigabe.py`
- Modify: `web/instantly_leser.py:318-556`
- Modify: `tests/web/test_instantly_leser.py`
- Modify: `web/routen/freigabe.py`
- Modify: `tests/web/test_freigabe.py`

**Interfaces:**

- Produces: `hole_alle_seiten(abruf, *, max_seiten=100) -> list[dict]` mit Duplikat- und Cursor-Schutz.
- Produces: `freigabe_anzeige(leads, emails) -> dict[str, dict]`, Schlüssel ist die normalisierte Empfängeradresse.
- Produces: `InstantlyLeser.freigabe_stand(campaign_ids) -> dict[str, dict]` mit 60-Sekunden-Zwischenspeicher und dem bestehenden Ausfallmuster.

- [ ] **Step 1: Reine Tests für Seiten, Duplikate und Schrittzuordnung schreiben**

```python
def test_hole_alle_seiten_folgt_cursor_und_entfernt_doppelte_ids():
    antworten = iter([
        {"items": [{"id": "a"}, {"id": "b"}], "next_starting_after": "seite-2"},
        {"items": [{"id": "b"}, {"id": "c"}], "next_starting_after": None},
    ])
    aufrufe = []

    items = hole_alle_seiten(
        lambda cursor: aufrufe.append(cursor) or next(antworten)
    )

    assert [i["id"] for i in items] == ["a", "b", "c"]
    assert aufrufe == [None, "seite-2"]


def test_hole_alle_seiten_lehnt_wiederholten_cursor_ab():
    with pytest.raises(RuntimeError, match="Seitenzeiger wiederholt"):
        hole_alle_seiten(lambda cursor: {
            "items": [{"id": str(cursor)}], "next_starting_after": "gleich",
        })


def test_antwort_gehoert_nur_bei_einem_einzigen_ausgang_im_thread_zum_schritt():
    emails = [
        {"id": "out-1", "lead": "anna@firma.de", "lead_id": "lead-1",
         "thread_id": "thread-1", "ue_type": 1, "step": 1,
         "timestamp_email": "2026-07-22T08:00:00Z"},
        {"id": "in-1", "lead": "anna@firma.de", "lead_id": "lead-1",
         "thread_id": "thread-1", "ue_type": 2,
         "timestamp_email": "2026-07-22T09:00:00Z"},
    ]

    stand = freigabe_anzeige([{"id": "lead-1", "email": "anna@firma.de", "status": 1}], emails)

    assert stand["anna@firma.de"]["steps"]["mail_1"] == {
        "sent_at": "2026-07-22T08:00:00Z", "replied": True,
    }
```

Ein weiterer Test legt zwei ausgehende E-Mails in denselben Thread. Erwartet wird `replied=None` für beide Schritte und `overall.replied=True`. Status `-1`, `-2`, `-3` wird nur als `bounced`, `unsubscribed`, `skipped` auf Empfängerebene übersetzt.

- [ ] **Step 2: Reine Tests ausführen und fehlendes Modul sehen**

```bash
'.venv/bin/python' -m pytest tests/web/test_instantly_freigabe.py -q
```

Expected: `FAIL` wegen des fehlenden Moduls.

- [ ] **Step 3: Begrenzte Seitennavigation und konservative Übersetzung bauen**

`hole_alle_seiten` ruft höchstens 100 Seiten ab, akzeptiert nur Listen unter `items`, entfernt Duplikate nur bei vorhandener stabiler `id` und wirft bei wiederholtem Cursor oder erreichter Obergrenze `RuntimeError`. `freigabe_anzeige` verwendet diese feste Schrittübersetzung:

```python
SCHRITT_VON_API = {1: "mail_1", 2: "follow_up_1", 3: "follow_up_2"}
GESENDET_TYPEN = {1, 3}
EMPFANGEN_TYPEN = {2}
LEAD_FEHLER = {-1: "bounced", -2: "unsubscribed", -3: "skipped"}
```

Eine Versandzeit zählt nur bei Kampagnen-/Lead-Zuordnung, bekannter Schrittnummer und gültigem Zeitstempel. Eine Schrittantwort zählt nur, wenn der Thread exakt eine zuordenbare ausgehende E-Mail enthält. Alle anderen Werte bleiben `None`.

- [ ] **Step 4: `InstantlyLeser` um POST, Abruf und getrennten Cache ergänzen**

```python
def _post(self, pfad: str, json_daten: dict):
    antwort = self.session.post(f"{BASIS}{pfad}", headers=self.headers,
                                 json=json_daten, timeout=20)
    if antwort.status_code >= 400:
        raise RuntimeError(f"Instantly antwortet mit {antwort.status_code} auf {pfad}")
    return antwort.json()
```

`_freigabe_hole_frisch(campaign_id)` verwendet:

```python
leads = hole_alle_seiten(lambda cursor: self._post("/leads/list", {
    "campaign_id": campaign_id, "limit": 100, **({"starting_after": cursor} if cursor else {}),
}))
emails = hole_alle_seiten(lambda cursor: self._get("/emails", {
    "campaign_id": campaign_id, "limit": 100, **({"starting_after": cursor} if cursor else {}),
}))
return freigabe_anzeige(leads, emails)
```

`freigabe_stand()` hat einen eigenen `_freigabe_cache`. Bei einem Fehler liefert es den letzten erfolgreichen Datensatz mit `erreichbar=False`; ohne früheren Erfolg liefert es `recipients={}`, `erreichbar=False`, `stand=None`. Bestehende Kampagnen-, E-Mail- und Postfach-Caches bleiben unverändert.

- [ ] **Step 5: HTTP- und Cache-Tests ergänzen**

`tests/web/test_instantly_leser.py` ergänzt eine Fake-Session mit `post`. Geprüft werden exakte Pfade/Körper, zweite Seiten, Cache innerhalb 60 Sekunden, neuer Abruf danach und letzter bekannter Stand bei HTTP 500. Kein Test verwendet einen echten Schlüssel.

- [ ] **Step 6: Übergebene Runde im Lesekontext verbinden**

Nur wenn `campaign_id` vorhanden ist, ruft `_lese_kontext` `geteilten_leser(request.app).freigabe_stand([campaign_id])` auf. Es verbindet Empfänger über normalisierte E-Mail-Adresse, ergänzt Schrittwerte `sent_at` und `replied` sowie `overall`, `live_erreichbar` und `live_stand`. Fehlt ein Empfänger im Live-Datensatz, bleiben genau dessen externe Werte `None` und die Seite zeigt eine Warnung zur unvollständigen Instantly-Liste.

- [ ] **Step 7: Alle Instantly-Leseprüfungen ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_instantly_freigabe.py tests/web/test_instantly_leser.py tests/web/test_freigabe.py -q
```

Expected: Seitenbegrenzung, unbekannte Werte, alter Cache, unvollständige Liste und eindeutige Antwortzuordnung bestehen.

- [ ] **Step 8: Aufgabe festhalten**

```bash
git add web/instantly_freigabe.py tests/web/test_instantly_freigabe.py web/instantly_leser.py tests/web/test_instantly_leser.py web/routen/freigabe.py tests/web/test_freigabe.py
git commit -m "feat: show proven per-recipient Instantly status"
```

---

### Task 6: Wholix-Prüftabelle, Seitenbereich und schmale Ansicht

**Files:**

- Modify: `web/templates/freigabe_liste.html`
- Replace: `web/templates/freigabe_lesen.html`
- Modify: `web/static/stil.css`
- Modify: `tests/web/test_freigabe.py`

**Interfaces:**

- Consumes: vollständig vorbereiteten Jinja-Kontext; im Browser werden keine externen Daten nachgeladen.
- Produces: zugängliche Tabelle, Suche, Filter, Zeilenauswahl, Schritt-Dialoge und feste Aktionsleiste.
- Preserves: alle Mutationen bleiben normale POST-Formulare und werden serverseitig erneut geprüft.

- [ ] **Step 1: HTML-Vertrag mit Rendering-Tests festhalten**

```python
def test_prueftabelle_hat_suche_filter_auswahl_und_drei_schrittgruppen(
    angemeldeter_client, daten_dir
):
    _lauf_anlegen(daten_dir)
    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")

    assert 'id="freigabe-suche"' in antwort.text
    assert 'id="freigabe-filter"' in antwort.text
    assert 'id="alle-sichtbaren"' in antwort.text
    assert antwort.text.count('scope="colgroup"') == 3
    assert "Ausgewählte bestätigen" in antwort.text
    assert "Bestätigungen aufheben" in antwort.text
    assert 'class="freigabe-tabelle-scroll"' in antwort.text


def test_uebergebene_runde_ist_schreibgeschuetzt(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, freigegeben=True,
                  versand_komplett={"campaign_id": "camp-1"})
    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")

    assert "Schreibgeschützt" in antwort.text
    assert "/mehrfach" not in antwort.text
    assert "/neu-erzeugen" not in antwort.text
```

- [ ] **Step 2: Tests ausführen und fehlenden Tabellenvertrag sehen**

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe.py -q
```

Expected: die neuen Darstellungs-Tests schlagen fehl.

- [ ] **Step 3: Übersicht in offene und übergebene Wholix-Karten gliedern**

`freigabe_liste.html` rendert beide Gruppen immer mit eigener Überschrift. Leere Gruppen erhalten je einen klaren Leerzustand. Jede Karte zeigt Name, Zielgruppe, Empfängerzahl, Fortschritt, Nacharbeit/Warnung, letzten Zeitpunkt und einen eindeutigen Link. Es gibt keine gemeinsame Empfängertabelle über mehrere Runden.

- [ ] **Step 4: Semantische breite Tabelle und Seitenbereich bauen**

Über der Tabelle stehen genau vier Kennzahlenkarten: Empfänger insgesamt, vollständig geprüft, offen und Nacharbeit nötig. Darunter folgen Suche, Statusfilter und sichtbare Auswahlzahl. Bei einem Instantly-Ausfall steht dort außerdem entweder „Live-Stand gerade nicht erreichbar — Stand von …“ oder „Noch kein Live-Stand verfügbar“.

Die Tabelle verwendet ein echtes `<table>`, `<thead>`, `<tbody>`, `scope="col"` und drei `scope="colgroup"`. Die ersten Empfängerspalten erhalten `position: sticky`. Jede Schrittzelle enthält kurze Vorschau, Zustand, Lesen-Schaltfläche, Versandzeit und Antwortwert. Ist nur eine Antwort auf Empfängerebene belegt, erscheint neben dem Empfänger „Antwort erhalten“, während die drei Schrittwerte `—` bleiben. Für jeden Schritt gibt es ein `<dialog class="freigabe-dialog">` mit vollem Text und den gültigen Einzelaktionen.

Die feste Aktionsleiste enthält ein einziges Mehrfachformular. Die Zeilen-Auswahlfelder tragen `name="recipient_ids"` und `form="mehrfach-form"`; die Revision steht einmal im Formular. Der Übergabeknopf ist zusätzlich zur Serversperre nur dann aktiv, wenn `uebergabe_bereit` wahr ist.

- [ ] **Step 5: Kleines JavaScript nur für Anzeigeverhalten ergänzen**

Das Skript im Template:

```javascript
const rows = [...document.querySelectorAll('[data-approval-row]')];
const search = document.querySelector('#freigabe-suche');
const filter = document.querySelector('#freigabe-filter');
const selectVisible = document.querySelector('#alle-sichtbaren');

function applyFilters() {
  const q = search.value.trim().toLocaleLowerCase('de');
  rows.forEach((row) => {
    const matchesText = row.dataset.search.includes(q);
    const matchesState = filter.value === 'all' || row.dataset.status === filter.value;
    row.hidden = !(matchesText && matchesState);
  });
}

search.addEventListener('input', applyFilters);
filter.addEventListener('change', applyFilters);
selectVisible.addEventListener('change', () => {
  rows.filter((row) => !row.hidden).forEach((row) => {
    row.querySelector('[name="recipient_ids"]').checked = selectVisible.checked;
  });
});

document.querySelectorAll('[data-dialog-open]').forEach((button) => {
  button.addEventListener('click', () => document.getElementById(button.dataset.dialogOpen).showModal());
});
document.querySelectorAll('[data-dialog-close]').forEach((button) => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
```

Der Server funktioniert auch ohne dieses Skript: alle Daten und Formulare bleiben im HTML vorhanden.

- [ ] **Step 6: Wholix-Stil und 390-Pixel-Regeln ergänzen**

`stil.css` erhält ausschließlich auf `.freigabe-*` begrenzte Regeln: ruhige helle Fläche, orange Zustandsmarken, kompakte Kennzahlen, breite Tabellenköpfe, angeheftete Empfängerspalten, rechter Dialog als Seitenbereich und feste Aktionsleiste. Unter `700px` bleiben Kopf, Filter und Karten einspaltig; nur `.freigabe-tabelle-scroll` erhält `overflow-x:auto`, während `.inhalt`, `.seite` und Dialog maximal `100%` breit bleiben. Fokusrahmen sind sichtbar und `prefers-reduced-motion` schaltet Bewegungen aus.

- [ ] **Step 7: Webtests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_freigabe.py tests/web/test_dashboard.py -q
```

Expected: alle Darstellungs-, Sicherheits- und bestehenden Dashboardtests bestehen.

- [ ] **Step 8: Aufgabe festhalten**

```bash
git add web/templates/freigabe_liste.html web/templates/freigabe_lesen.html web/static/stil.css tests/web/test_freigabe.py
git commit -m "feat: add Wholix approval table interface"
```

---

### Task 7: Strukturierte Sperrliste mit alten Einträgen und Platzhalter-Schutz

**Files:**

- Modify: `pipeline/config.py:79-93`
- Modify: `tests/test_config.py`
- Modify: `web/routen/sperrliste.py`
- Modify: `tests/web/test_sperrliste.py`
- Modify: `tests/web/test_laufmanager.py`
- Verify: `tests/test_dedupe.py`

**Interfaces:**

- Produces: `lade_globale_sperrlisten_eintraege(daten_dir) -> list[dict]`.
- Preserves: `lade_globale_sperrliste(daten_dir) -> list[str]` für Pipeline und Deduplizierung.
- Produces: `normalisiere_domain_muster`, `muster_deckt_domain` und strukturierte atomare Speicherung.

- [ ] **Step 1: Rückwärtsverträgliche Konfigurations-Tests schreiben**

```python
def test_lade_globale_sperrliste_versteht_alte_und_neue_eintraege(tmp_path):
    (tmp_path / "sperrliste-global.yaml").write_text(
        '- "alt.de"\n- domain: "*.bund.de"\n  reason: "Kunde"\n  comment: "Vertrag"\n',
        encoding="utf-8",
    )

    assert lade_globale_sperrliste(tmp_path) == ["alt.de", "*.bund.de"]
    assert lade_globale_sperrlisten_eintraege(tmp_path) == [
        {"domain": "alt.de", "reason": "", "comment": "", "legacy": True},
        {"domain": "*.bund.de", "reason": "Kunde", "comment": "Vertrag", "legacy": False},
    ]
```

- [ ] **Step 2: Test ausführen und fehlende Lesefunktion sehen**

```bash
'.venv/bin/python' -m pytest tests/test_config.py -q
```

Expected: `FAIL`, weil `lade_globale_sperrlisten_eintraege` fehlt.

- [ ] **Step 3: Alten und neuen YAML-Aufbau streng lesen**

```python
def lade_globale_sperrlisten_eintraege(daten_dir) -> list[dict]:
    pfad = Path(daten_dir) / "sperrliste-global.yaml"
    if not pfad.exists():
        return []
    inhalt = yaml.safe_load(pfad.read_text(encoding="utf-8")) or []
    if not isinstance(inhalt, list):
        raise ValueError("sperrliste-global.yaml muss eine Liste sein.")
    ergebnis = []
    for eintrag in inhalt:
        if isinstance(eintrag, str):
            ergebnis.append({"domain": eintrag, "reason": "", "comment": "", "legacy": True})
        elif isinstance(eintrag, dict) and isinstance(eintrag.get("domain"), str):
            ergebnis.append({
                "domain": eintrag["domain"],
                "reason": eintrag.get("reason") or "",
                "comment": eintrag.get("comment") or "",
                "legacy": False,
            })
        else:
            raise ValueError("Ein Sperrlisten-Eintrag ist falsch aufgebaut.")
    return ergebnis


def lade_globale_sperrliste(daten_dir) -> list:
    return [e["domain"] for e in lade_globale_sperrlisten_eintraege(daten_dir)]
```

- [ ] **Step 4: Validierungs- und Konflikttests schreiben**

```python
@pytest.mark.parametrize("domain", ["https://firma.de", "firma.de/pfad", "*firma.de", "firma", "fi rma.de"])
def test_ungueltiges_domain_muster_wird_abgewiesen(angemeldeter_client, domain):
    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": domain, "grund": "Kunde", "kommentar": ""},
    )
    assert antwort.status_code == 400
    assert "gültige Domain" in antwort.text


def test_einzelne_domain_wird_abgewiesen_wenn_wildcard_sie_schon_abdeckt(
    angemeldeter_client, daten_dir
):
    (daten_dir / "sperrliste-global.yaml").write_text('- "*.bund.de"\n', encoding="utf-8")

    antwort = angemeldeter_client.post(
        "/domains/hinzufuegen",
        data={"domain": "amt.bund.de", "grund": "Kunde", "kommentar": ""},
    )

    assert antwort.status_code == 400
    assert "*.bund.de" in antwort.text
```

Zusätzliche Tests prüfen doppelten Eintrag, einen neuen Platzhalter, der vorhandene Einzel-Domains abdecken würde, erlaubte Gründe, freien Kommentar, Bearbeiten eines alten Eintrags und unveränderte Datei bei jedem Konflikt.

- [ ] **Step 5: Normalisierung, Konfliktprüfung und strukturierte Routen bauen**

`normalisiere_domain_muster` trimmt, schreibt klein, vereinheitlicht internationale Domains über IDNA, entfernt abschließende Punkte und akzeptiert nur einen optionalen Platzhalter plus mindestens zwei gültige Domain-Bestandteile. Grund ist genau einer von `Kunde`, `Partner`, `Konkurrent`, `Sonstiges`. Kommentare werden getrimmt und auf 1000 Zeichen begrenzt.

```python
GRUENDE = ("Kunde", "Partner", "Konkurrent", "Sonstiges")
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def normalisiere_domain_muster(roh: str) -> str:
    wert = roh.strip().lower()
    wildcard = wert.startswith("*.")
    kern = wert[2:] if wildcard else wert
    if not kern or "://" in kern or "/" in kern or " " in kern or "*" in kern:
        raise ValueError("Bitte eine gültige Domain oder ein Muster wie *.bund.de eintragen.")
    try:
        kern = kern.rstrip(".").encode("idna").decode("ascii")
    except UnicodeError as fehler:
        raise ValueError("Bitte eine gültige Domain eintragen.") from fehler
    if not DOMAIN_RE.fullmatch(kern):
        raise ValueError("Bitte eine gültige Domain oder ein Muster wie *.bund.de eintragen.")
    return f"*.{kern}" if wildcard else kern


def muster_deckt_domain(muster: str, domain: str) -> bool:
    if muster.startswith("*."):
        suffix = muster[1:]
        return domain.endswith(suffix) and domain != muster[2:]
    return muster == domain
```

`POST /domains/hinzufuegen` schreibt neue Einträge als Dict. Alte Einträge bleiben beim bloßen Hinzufügen als einfache Zeichenketten im gemischten YAML. `POST /domains/bearbeiten` identifiziert über `urspruengliche_domain`, validiert den neuen Stand und wandelt nur diesen Eintrag in ein Dict um. `POST /domains/entfernen` bleibt vorhanden. Alle drei Wege verwenden die bestehende temporäre Datei plus `os.replace`, jetzt für `list[str | dict]`.

- [ ] **Step 6: Pipeline-Verträglichkeit und atomare Speicherung prüfen**

```bash
'.venv/bin/python' -m pytest tests/test_config.py tests/test_dedupe.py tests/web/test_sperrliste.py tests/web/test_laufmanager.py -q
```

Expected: alte und neue Einträge blockieren dieselben Domains; ungültige/überdeckte Einträge ändern nichts; keine temporäre Datei bleibt liegen.

- [ ] **Step 7: Aufgabe festhalten**

```bash
git add pipeline/config.py tests/test_config.py web/routen/sperrliste.py tests/web/test_sperrliste.py tests/web/test_laufmanager.py
git commit -m "feat: add structured reliable domain blacklist"
```

---

### Task 8: Wholix-Sperrlistentabelle

**Files:**

- Replace: `web/templates/sperrliste.html`
- Modify: `web/static/stil.css`
- Modify: `tests/web/test_sperrliste.py`

**Interfaces:**

- Consumes: `domains` als strukturierte Anzeigeeinträge und `gruende` aus der Route.
- Produces: Tabelle mit Domain, Grund, Kommentar, Bearbeiten und Entfernen sowie ein verständliches Hinzufügen-Formular.

- [ ] **Step 1: Darstellungs-Tests schreiben**

```python
def test_sperrliste_zeigt_wholix_spalten_und_strukturierte_werte(
    angemeldeter_client, daten_dir
):
    (daten_dir / "sperrliste-global.yaml").write_text(
        '- domain: "*.bund.de"\n  reason: "Kunde"\n  comment: "Rahmenvertrag"\n',
        encoding="utf-8",
    )

    antwort = angemeldeter_client.get("/domains")

    assert antwort.status_code == 200
    for text in ("Domain", "Grund", "Kommentar", "Aktionen", "*.bund.de",
                 "Kunde", "Rahmenvertrag"):
        assert text in antwort.text
    assert "/domains/bearbeiten" in antwort.text
    assert "/domains/entfernen" in antwort.text
```

- [ ] **Step 2: Test ausführen und fehlende Tabelle sehen**

```bash
'.venv/bin/python' -m pytest tests/web/test_sperrliste.py -q
```

Expected: der neue Test schlägt fehl, weil die bisherige Chip-Liste keine Spalten hat.

- [ ] **Step 3: Tabelle und Formulare bauen**

`sperrliste.html` behält Einleitung und Hinweis zur kundenbezogenen Liste. Darunter folgen das Hinzufügen-Formular mit Domain, Grund und Kommentar sowie eine semantische Tabelle. Alte Einträge zeigen beim Grund `—` und beim Kommentar „Alter Eintrag“. Bearbeiten öffnet ein zugängliches `<dialog>` mit vorausgefüllten Werten; Entfernen bleibt ein eigenes POST-Formular mit eindeutigem `aria-label`.

- [ ] **Step 4: Begrenzte Sperrlisten-Stile ergänzen**

Die neuen `.sperrliste-*`-Regeln folgen denselben Wholix-Farben, Abständen und Fokusrahmen wie die Freigabetabelle. Unter `700px` wird nur der Tabellenbehälter waagerecht scrollbar; Formularfelder stehen untereinander und überschreiten die Seitenbreite nicht.

- [ ] **Step 5: Sperrlisten- und Webtests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_sperrliste.py tests/web/test_freigabe.py -q
```

Expected: beide Oberflächen und ihre Formulare bestehen gemeinsam ohne CSS-/Template-Rückschritt.

- [ ] **Step 6: Aufgabe festhalten**

```bash
git add web/templates/sperrliste.html web/static/stil.css tests/web/test_sperrliste.py
git commit -m "feat: add Wholix blacklist table interface"
```

---

### Task 9: Vollprüfung, sichtbarer Nachweis und Projektübergabe

**Files:**

- Modify: `docs/wholix-nachbau-roadmap.md`
- Modify: `project-context.md`
- Create: Bildschirmfotos unter `.superpowers/phase-2/` (durch `.gitignore` nicht festhalten)
- Update or create: Jira Task in Projekt `AP` über `jira-pp-cli`

**Interfaces:**

- Consumes: fertige lokale Anwendung mit Testdaten und nachgebildetem Instantly-Leser.
- Produces: vollständiger Testnachweis, Desktop-/390-Pixel-Bilder, aktualisierter Fahrplan, fortsetzbarer Projektkontext und Jira-Abschlussnotiz.

- [ ] **Step 1: Erst die komplette Testsammlung ausführen**

```bash
'.venv/bin/python' -m pytest -q
```

Expected: 0 Fehler. Die genaue Zahl und bekannte Warnungen werden im Projektkontext festgehalten.

- [ ] **Step 2: Lokalen Test-Datenordner mit allen sichtbaren Zuständen anlegen**

Die Testdaten enthalten mindestens zwei offene Runden, eine vollständig bestätigte Runde, eine übergebene Runde, belegte und unbekannte Instantly-Werte, eine Nacharbeitswarnung sowie alte/neue/Platzhalter-Sperrlisteneinträge. Der lokale Fake-Leser beantwortet alle Instantly-Abfragen aus Dateien; `INSTANTLY_API_KEY` bleibt für diesen Nachweis ungesetzt.

- [ ] **Step 3: Anwendung nur lokal starten und Hauptablauf prüfen**

Geprüft wird: Login, offene/übergebene Übersicht, Suche, jeder Filter, Auswahl sichtbarer Zeilen, Einzelbestätigung, Mehrfachbestätigung, Aufheben, fehlgeschlagene Neuerzeugung, erfolgreiche Neuerzeugung, gesperrte unvollständige Übergabe, schreibgeschützte übergebene Runde und Sperrlisten-Konflikt. Es wird keine echte Kampagne erzeugt oder aktiviert.

- [ ] **Step 4: Bildschirmfotos erstellen und gegen die Wholix-Vorlagen ansehen**

Erzeugt werden:

- `.superpowers/phase-2/freigabe-uebersicht-desktop.png`
- `.superpowers/phase-2/freigabe-tabelle-desktop.png`
- `.superpowers/phase-2/freigabe-dialog-desktop.png`
- `.superpowers/phase-2/freigabe-uebergeben-desktop.png`
- `.superpowers/phase-2/sperrliste-desktop.png`
- `.superpowers/phase-2/freigabe-390px.png`
- `.superpowers/phase-2/sperrliste-390px.png`

Bei 390 Pixel wird ausdrücklich geprüft, dass das Dokument nicht waagerecht rollt und nur der jeweilige Tabellenbehälter waagerecht bewegt werden kann. Zusätzlich werden Tab-Reihenfolge, Fokusrahmen, Dialog schließen und Formularbeschriftungen geprüft.

- [ ] **Step 5: Fahrplan und Projektkontext aktualisieren**

Die Roadmap markiert nur tatsächlich bewiesene Phase-2-Punkte als abgeschlossen. `project-context.md` behält exakt die vier Abschnitte „Worum es geht“, „Aktueller Stand“, „Entscheidungen“ und „Nächste Schritte“ und nennt Tests, Bildnachweise, bekannte Einschränkungen und die nächste noch offene Phase.

- [ ] **Step 6: Jira-Aufgabe suchen und nachvollziehbar abschließen**

Zuerst wird nach einer bestehenden passenden Aufgabe gesucht:

```bash
jira-pp-cli search 'Wholix approval Phase 2' --project AP --data-source live --agent --limit 20
```

Existiert eine passende Aufgabe, wird sie verwendet. Andernfalls wird eine Task mit englischem Titel `Build Wholix-style approval and blacklist interface` erstellt. Beschreibung und Abschlusskommentar nennen nur sichtbare Ergebnisse: per-step approval, full-round gate, read-only Instantly status, structured blacklist, full automated test result and local screenshot proof.

- [ ] **Step 7: Schlussprüfung und Dokumentations-Commit**

```bash
git diff --check
git status --short
git add docs/wholix-nachbau-roadmap.md project-context.md
git commit -m "docs: record Wholix approval phase 2 result"
```

Expected: nur beabsichtigte Projektdateien sind festgehalten; `.superpowers/phase-2/` bleibt ignoriert; der Arbeitsbaum ist danach sauber.

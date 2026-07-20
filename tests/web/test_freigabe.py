"""Tests fuer den Bereich "Pruefen & Freigeben" (Task 5): Liste der
wartenden Auftraege, Lese-/Freigabe-Ansicht (Checkliste als Freigabe-Geste,
eingefroren in docs/design/Poleposition-v4.dc.html), Freigeben (ruft die
bestehende Pipeline-Sendelogik ueber einen gefakten InstantlySender) und
Ablehnen. Kein echter Instantly-Aufruf: app.state.instantly wird gefaked,
exakt wie web.routen.kunden app.state.ki fuer die KI faked (siehe
tests/web/test_kunden.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from pipeline.approval import approve
from pipeline.run_store import RunStore
from web.app import create_app
from web.laufmanager import Laufmanager

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

KUNDE_NAME = "Test GmbH"
KUNDE_SLUG = "test-gmbh"
ABSENDER = "Jonas Wilde"

KUNDE_YAML = f"""
name: {KUNDE_NAME}
zielgruppe:
  titel: [CEO]
angebot: Testangebot
tonalitaet: ruhig
absender: {ABSENDER}
follow_up_tage: [4, 9]
test_empfaenger:
  - anna@firma.de
  - bob@firma.de
sperrliste: []
"""

_TEXT_ANNA = {"email": "anna@firma.de", "betreff": "Kurze Frage an Anna",
              "mail_1": "Hallo Anna, ...", "follow_up_1": "Nachfass eins an Anna",
              "follow_up_2": "Nachfass zwei an Anna"}
_TEXT_BOB = {"email": "bob@firma.de", "betreff": "Kurze Frage an Bob",
             "mail_1": "Hallo Bob, ...", "follow_up_1": "Nachfass eins an Bob",
             "follow_up_2": "Nachfass zwei an Bob"}

_DEDUPE_BEHALTEN = [
    {"first_name": "Anna", "last_name": "Muster", "email": "anna@firma.de",
     "company": "Firma GmbH", "title": "CEO", "website": "", "source": "apollo"},
    {"first_name": "Bob", "last_name": "Beispiel", "email": "bob@firma.de",
     "company": "Firma GmbH", "title": "CTO", "website": "", "source": "apollo"},
]

_NACHARBEIT = [{"email": "carla@firma.de", "grund": "Betreff länger als 60 Zeichen",
                "betreff": "X" * 61, "mail_1": "Text der nicht rausgeht",
                "follow_up_1": "F1", "follow_up_2": "F2"}]


class FakeInstantly:
    """Ersetzt InstantlySender: zeichnet Aufrufe auf statt echte HTTP-Requests
    zu machen. `fehler_bei` faket einen fehlschlagenden HTTP-Aufruf (wie
    pipeline.senders.instantly.InstantlySender._post ihn per RuntimeError
    meldet), um den 3-teiligen Fehlertext-Pfad zu pruefen."""

    def __init__(self, fehler_bei: str | None = None):
        self.campaigns_erstellt = []
        self.leads_importiert = []
        self.fehler_bei = fehler_bei

    def create_campaign(self, kunde) -> str:
        if self.fehler_bei == "create_campaign":
            raise RuntimeError("Instantly antwortet mit 500 auf /campaigns: Server-Fehler")
        self.campaigns_erstellt.append(kunde.name)
        return "camp-123"

    def import_leads(self, campaign_id, texte_pro_lead):
        if self.fehler_bei == "import_leads":
            raise RuntimeError("Instantly antwortet mit 500 auf /leads/add: Server-Fehler")
        self.leads_importiert.append((campaign_id, texte_pro_lead))


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    (tmp_path / "kunden").mkdir()
    (tmp_path / "kunden" / "test-kunde.yaml").write_text(KUNDE_YAML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def app(daten_dir):
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    return client


def _lauf_anlegen(daten_dir: Path, *, ts: str = "20260717-090000",
                   pruefung_ok=None, nacharbeit=None, dedupe_behalten=None,
                   freigegeben: bool = False, abgelehnt: dict | None = None,
                   versand_komplett: dict | None = None) -> Path:
    lauf_dir = daten_dir / "laeufe" / KUNDE_SLUG / ts
    lauf_dir.mkdir(parents=True)
    store = RunStore.resume(lauf_dir)
    store.save_step("kunde_pfad", {"pfad": "kunden/test-kunde.yaml"})
    store.save_step("dedupe", {"behalten": dedupe_behalten or [], "verworfen": []})
    fertig = pruefung_ok if pruefung_ok is not None else [_TEXT_ANNA, _TEXT_BOB]
    store.save_step("personalisierung", {"fertig": fertig, "nacharbeit": nacharbeit or []})
    store.save_step("pruefung_ok", fertig)
    if freigegeben or versand_komplett is not None:
        approve(store, name="Fruehere Freigabe")
    if versand_komplett is not None:
        store.save_step("versand_komplett", versand_komplett)
    if abgelehnt is not None:
        (lauf_dir / "abgelehnt.json").write_text(json.dumps(abgelehnt), encoding="utf-8")
    return lauf_dir


# Anmeldung ------------------------------------------------------------------

def test_liste_verlangt_anmeldung(client):
    antwort = client.get("/pruefen", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


# Liste ------------------------------------------------------------------

def test_liste_leer_zeigt_hinweis(angemeldeter_client):
    # Woertlich aus v4 (docs/design/Poleposition-v4.dc.html, Zeile ~193):
    # v4 ist die eingefrorene Quelle fuer Texte, deshalb hier verbatim statt
    # einer eigenen Formulierung (Review-Fund Task 5).
    antwort = angemeldeter_client.get("/pruefen")
    assert antwort.status_code == 200
    assert "Nichts wartet auf dich" in antwort.text
    assert "Sobald neue Anschreiben fertig sind, erscheinen sie hier zum Lesen und Freigeben." in antwort.text


def test_liste_zeigt_nur_wartende_laeufe(angemeldeter_client, daten_dir):
    wartend = _lauf_anlegen(daten_dir, ts="20260717-090000",
                             dedupe_behalten=_DEDUPE_BEHALTEN)
    _lauf_anlegen(daten_dir, ts="20260717-100000",
                  dedupe_behalten=_DEDUPE_BEHALTEN, freigegeben=True)
    _lauf_anlegen(daten_dir, ts="20260717-110000",
                  dedupe_behalten=_DEDUPE_BEHALTEN,
                  abgelehnt={"von": "Lena", "am": "17.07.2026", "begruendung": "x"})

    antwort = angemeldeter_client.get("/pruefen")
    assert antwort.status_code == 200
    assert KUNDE_NAME in antwort.text
    assert f"/pruefen/{KUNDE_SLUG}/20260717-090000" in antwort.text
    assert f"/pruefen/{KUNDE_SLUG}/20260717-100000" not in antwort.text
    assert f"/pruefen/{KUNDE_SLUG}/20260717-110000" not in antwort.text
    assert "Nichts wartet auf dich" not in antwort.text


# Lese-Ansicht ------------------------------------------------------------

def test_lese_ansicht_zeigt_texte_email_und_echte_tage(angemeldeter_client, daten_dir):
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN,
                              nacharbeit=_NACHARBEIT)
    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    assert antwort.status_code == 200
    text = antwort.text

    assert ABSENDER in text
    assert "anna@firma.de" in text and "bob@firma.de" in text
    assert "Kurze Frage an Anna" in text
    assert "Hallo Anna, ..." in text
    assert "Nachfass eins an Anna" in text
    assert "Nachfass eins an Bob" in text
    assert "Nachfass zwei an Anna" in text
    # follow_up_tage: [4, 9] -> Nachfass 1 nach 4 Tagen, Nachfass 2 nach 9 Tagen
    assert "nach 4 Tagen" in text
    assert "nach 9 Tagen" in text
    # dedupe-Info (Name/Firma) fuer die Empfaengerliste
    assert "Anna Muster" in text or "Anna" in text
    assert "Firma GmbH" in text


def test_lese_ansicht_zeigt_aussortierte_texte_aufklappbar(angemeldeter_client, daten_dir):
    _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN, nacharbeit=_NACHARBEIT)
    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    assert antwort.status_code == 200
    text = antwort.text
    assert "carla@firma.de" in text
    assert "Betreff länger als 60 Zeichen" in text
    assert "Text der nicht rausgeht" in text
    assert "<details" in text and "<summary" in text


def test_lese_ansicht_verlangt_anmeldung(client, daten_dir):
    _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)
    antwort = client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000", follow_redirects=False)
    assert antwort.status_code == 303


def test_lese_ansicht_unbekannter_lauf_404(angemeldeter_client):
    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/nicht-da")
    assert antwort.status_code == 404


def test_lese_ansicht_kaputte_abgelehnt_json_zeigt_seite_statt_absturz(
        angemeldeter_client, daten_dir):
    # E-Fix 4: abgelehnt.json wird ueber das sichere JSON-Lade-Muster
    # gelesen (web.laufmanager._lade_json_sicher) - eine kaputte/nicht
    # gueltige abgelehnt.json (z.B. Unterprozess mitten im Schreiben
    # abgebrochen) darf die Lese-Ansicht nicht mit einem 500er abstuerzen
    # lassen. status()/_ist_wartend_reine_dateipruefung pruefen ohnehin nur
    # Datei-EXISTENZ (nicht den Inhalt), der Zustand ist hier also
    # "abgelehnt" - das Template zeigt den Abgelehnt-Kasten nur, wenn der
    # geparste Wert vorhanden ist (siehe freigabe_lesen.html), sonst bleibt
    # er einfach weg statt abzustuerzen.
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)
    (lauf_dir / "abgelehnt.json").write_text("{das ist kein gueltiges JSON", encoding="utf-8")

    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    assert antwort.status_code == 200


def test_lese_ansicht_kaputte_kunden_datei_zeigt_freundlichen_fehler_statt_absturz(
        angemeldeter_client, daten_dir):
    # Review-Fund (Task 5): _lese_kontext muss denselben defensiven
    # OSError/ValueError/KeyError-Umgang wie _wartende_laeufe haben, statt
    # mit einem 500er abzustuerzen, wenn die Kunden-Datei kaputt ist (hier:
    # Pflichtfelder fehlen, load_kunde wirft ValueError).
    (daten_dir / "kunden" / "test-kunde.yaml").write_text("name: Test GmbH\n", encoding="utf-8")
    _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)
    antwort = angemeldeter_client.get(f"/pruefen/{KUNDE_SLUG}/20260717-090000")
    assert antwort.status_code == 200
    assert "nicht lesbar" in antwort.text or "beschädigt" in antwort.text


# Freigeben ----------------------------------------------------------------

def test_freigeben_ohne_alle_haken_gibt_fehler_und_sendet_nichts(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2"]},
    )
    assert antwort.status_code == 400
    assert not (lauf_dir / "FREIGABE.txt").exists()
    assert fake.campaigns_erstellt == []
    assert fake.leads_importiert == []


def test_freigeben_vollstaendig_setzt_freigabe_und_sendet(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
        follow_redirects=True,
    )
    assert antwort.status_code == 200

    freigabe_inhalt = (lauf_dir / "FREIGABE.txt").read_text(encoding="utf-8")
    assert "Lena Hartmann" in freigabe_inhalt

    assert fake.campaigns_erstellt == [KUNDE_NAME]
    assert len(fake.leads_importiert) == 1
    campaign_id, texte = fake.leads_importiert[0]
    assert campaign_id == "camp-123"
    assert {t["email"] for t in texte} == {"anna@firma.de", "bob@firma.de"}

    assert Laufmanager(daten_dir).status(lauf_dir)["zustand"] == "uebergeben"
    assert "pausiert" in antwort.text
    assert "Lena Hartmann" in antwort.text
    assert "app.instantly.ai/app/campaign/camp-123" in antwort.text


def test_freigeben_fremder_empfaenger_zeigt_fehler_ohne_versand(angemeldeter_client, daten_dir):
    # Die Test-Empfaenger-Sperre der Pipeline (pipeline.__main__.
    # _versand_ausfuehren) muss auch ueber die Web-Route greifen - hier ein
    # Fake-Lead mit einer Adresse ausserhalb kunde.test_empfaenger.
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    fremder_text = {**_TEXT_ANNA, "email": "fremd@echt-firma.de"}
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN,
                              pruefung_ok=[fremder_text])

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
    )
    assert antwort.status_code == 200 or antwort.status_code == 400
    assert "fremd@echt-firma.de" in antwort.text or "Test-Adressen" in antwort.text
    assert fake.campaigns_erstellt == []


def test_freigeben_instantly_fehler_zeigt_dreiteiligen_text(angemeldeter_client, daten_dir):
    app = angemeldeter_client.app
    fake = FakeInstantly(fehler_bei="create_campaign")
    app.state.instantly = fake
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
    )
    assert antwort.status_code == 200
    # Freigabe bleibt trotz Instantly-Fehler bestehen (erneutes Senden moeglich).
    assert (lauf_dir / "FREIGABE.txt").exists()
    assert "Instantly" in antwort.text


def test_freigeben_auf_abgelehntem_lauf_wird_verweigert(angemeldeter_client, daten_dir):
    # Review-Fund (Task 5): ohne Zustands-Waechter wuerde freigeben() hier
    # trotzdem eine Kampagne anlegen, obwohl die Ablehnen-Ansicht "Nichts
    # wurde versendet" verspricht.
    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    lauf_dir = _lauf_anlegen(
        daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN,
        abgelehnt={"von": "Lena", "am": "17.07.2026", "begruendung": "x"})

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
    )
    assert antwort.status_code == 400
    assert not (lauf_dir / "FREIGABE.txt").exists()
    assert fake.campaigns_erstellt == []
    assert fake.leads_importiert == []


def test_freigeben_bereits_freigegeben_ueberschreibt_audit_trail_nicht(angemeldeter_client, daten_dir):
    # Review-Fund (Task 5): ein zweites POST /freigeben (z.B. Doppelklick,
    # oder ein Retry-Versuch nach einem fehlgeschlagenen Versand) darf
    # FREIGABE.txt NICHT neu schreiben - der Versand-Retry laeuft ueber
    # /senden-erneut, nicht ueber ein zweites freigeben().
    app = angemeldeter_client.app
    fake = FakeInstantly(fehler_bei="create_campaign")
    app.state.instantly = fake
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)

    erste = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
    )
    assert erste.status_code == 200
    erster_inhalt = (lauf_dir / "FREIGABE.txt").read_text(encoding="utf-8")
    assert "Lena Hartmann" in erster_inhalt
    assert Laufmanager(daten_dir).status(lauf_dir)["zustand"] == "freigegeben"

    zweite = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
    )
    assert zweite.status_code == 400
    assert "bereits freigegeben" in zweite.text
    assert "Lena Hartmann" in zweite.text

    zweiter_inhalt = (lauf_dir / "FREIGABE.txt").read_text(encoding="utf-8")
    assert zweiter_inhalt == erster_inhalt
    # Kein zweiter Versand-Versuch ueber freigeben() ausgeloest - der
    # Versand-Retry bleibt der eigene /senden-erneut-Weg vorbehalten.
    assert fake.campaigns_erstellt == []


def test_freigeben_laesst_programmierfehler_durch_statt_ihn_zu_verschlucken(
        angemeldeter_client, daten_dir):
    # E-Fix 5: _versand_antwort hatte `except Exception` - das wuerde auch
    # echte Programmierfehler (z.B. ein TypeError im Sender/eigenen Code)
    # leise verschlucken und als "Instantly hat gerade nicht geantwortet"
    # anzeigen. Jetzt sind nur noch die konkret erwarteten Ausnahmen
    # gefangen (SendenFehler, RuntimeError, ValueError, requests.
    # RequestException, plus OSError/KeyError fuer _kunde_fuer) - ein
    # TypeError muss sichtbar bleiben.
    class KaputterSenderProgrammierfehler:
        def create_campaign(self, kunde):
            raise TypeError("das ist ein Programmierfehler, kein erwarteter Instantly-Fehler")

    app = angemeldeter_client.app
    app.state.instantly = KaputterSenderProgrammierfehler()
    _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)

    with pytest.raises(TypeError):
        angemeldeter_client.post(
            f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
            data={"checkliste": ["1", "2", "3"]},
        )


def test_senden_erneut_doppelklick_legt_nur_eine_kampagne_an(angemeldeter_client, daten_dir):
    # E-Fix 6: Doppelklick-Schutz - zwei (hier sequentielle, siehe
    # Aufgabenbrief: eine echte Nebenlaeufigkeits-Pruefung waere flaky)
    # POSTs auf /senden-erneut duerfen nicht beide eine Kampagne anlegen.
    # Die Versand-Ausfuehrung wird ueber einen Lock JE Laufordner
    # abgesichert (web.routen.freigabe._versand_lock_fuer).
    from web.routen import freigabe as freigabe_modul
    assert hasattr(freigabe_modul, "_versand_lock_fuer")  # Lock-Infrastruktur existiert

    app = angemeldeter_client.app
    fake = FakeInstantly()
    app.state.instantly = fake
    _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN, freigegeben=True)

    erste = angemeldeter_client.post(f"/pruefen/{KUNDE_SLUG}/20260717-090000/senden-erneut")
    assert erste.status_code == 200
    assert fake.campaigns_erstellt == [KUNDE_NAME]

    zweite = angemeldeter_client.post(f"/pruefen/{KUNDE_SLUG}/20260717-090000/senden-erneut")
    assert zweite.status_code == 200
    # Zweiter Klick nimmt den "bereits angelegt"-Pfad (versand_komplett ist
    # nach dem ersten Klick schon da) - keine zweite Kampagne.
    assert fake.campaigns_erstellt == [KUNDE_NAME]
    assert len(fake.leads_importiert) == 1
    assert "bereits angelegt" in zweite.text


def test_freigeben_verlangt_anmeldung(client, daten_dir):
    _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)
    antwort = client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/freigeben",
        data={"checkliste": ["1", "2", "3"]},
        follow_redirects=False,
    )
    assert antwort.status_code == 303


# Ablehnen -------------------------------------------------------------------

def test_ablehnen_ohne_begruendung_gibt_fehler(angemeldeter_client, daten_dir):
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)
    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/ablehnen", data={"begruendung": ""})
    assert antwort.status_code == 400
    assert not (lauf_dir / "abgelehnt.json").exists()


def test_ablehnen_auf_uebergebenem_lauf_wird_verweigert(angemeldeter_client, daten_dir):
    lauf_dir = _lauf_anlegen(
        daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN,
        versand_komplett={"campaign_id": "camp-alt"})

    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/ablehnen",
        data={"begruendung": "zu spaet"},
    )
    assert antwort.status_code == 400
    assert not (lauf_dir / "abgelehnt.json").exists()
    assert Laufmanager(daten_dir).status(lauf_dir)["zustand"] == "uebergeben"


def test_ablehnen_mit_begruendung_speichert_und_verschwindet_aus_liste(angemeldeter_client, daten_dir):
    lauf_dir = _lauf_anlegen(daten_dir, dedupe_behalten=_DEDUPE_BEHALTEN)
    antwort = angemeldeter_client.post(
        f"/pruefen/{KUNDE_SLUG}/20260717-090000/ablehnen",
        data={"begruendung": "Ton passt nicht zur Zielgruppe"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303

    inhalt = json.loads((lauf_dir / "abgelehnt.json").read_text(encoding="utf-8"))
    assert inhalt["von"] == "Lena Hartmann"
    assert inhalt["begruendung"] == "Ton passt nicht zur Zielgruppe"
    assert inhalt["am"]

    liste = angemeldeter_client.get("/pruefen")
    assert f"/pruefen/{KUNDE_SLUG}/20260717-090000" not in liste.text

    assert Laufmanager(daten_dir).status(lauf_dir)["zustand"] == "abgelehnt"

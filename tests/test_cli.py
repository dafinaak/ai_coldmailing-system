import json, os
from datetime import datetime, timedelta
import pytest
import pipeline.__main__ as cli
import pipeline.run_store as run_store_modul
from pipeline.__main__ import senden
from pipeline.models import Lead
from pipeline.run_store import RunStore

def test_senden_verweigert_ohne_freigabe(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    store = RunStore(tmp_path, "Demo")
    store.save_step("pruefung_ok", [])
    with pytest.raises(SystemExit, match="Freigabe"):
        senden(store.run_dir)

def test_senden_verweigert_fremde_empfaenger(tmp_path, monkeypatch):
    # Aufbau: freigegebener Lauf, aber ein Empfaenger fehlt in test_empfaenger
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    from pipeline.approval import approve
    store = RunStore(tmp_path, "Demo")
    store.save_step("kunde_pfad", {"pfad": "kunden/demo-gmbh.yaml"})
    store.save_step("pruefung_ok", [{"email": "fremd@echt.de", "betreff": "B",
                                     "mail_1": "M", "follow_up_1": "F", "follow_up_2": "F"}])
    approve(store)
    with pytest.raises(SystemExit, match="Test-Empfaenger"):
        senden(store.run_dir)

def test_laedt_dotenv_ohne_vorhandene_variablen_zu_ueberschreiben(tmp_path, monkeypatch):
    monkeypatch.delenv("MEINE_TEST_VAR", raising=False)
    monkeypatch.setenv("SCHON_GESETZT", "alt")
    env_datei = tmp_path / ".env"
    env_datei.write_text(
        "# Kommentar\n\nMEINE_TEST_VAR=neu\nSCHON_GESETZT=ueberschrieben\n", encoding="utf-8")
    cli.lade_dotenv(env_datei)
    assert os.environ["MEINE_TEST_VAR"] == "neu"
    assert os.environ["SCHON_GESETZT"] == "alt"

def test_lade_dotenv_ohne_datei_tut_nichts(tmp_path):
    cli.lade_dotenv(tmp_path / "gibts-nicht.env")  # darf nicht werfen

def test_lauf_bricht_ohne_apollo_key_ab(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(SystemExit, match="APOLLO_API_KEY"):
        cli.lauf("kunden/demo-gmbh.yaml", 10, None)

def test_lauf_bricht_ohne_anthropic_key_ab(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        cli.lauf("kunden/demo-gmbh.yaml", 10, None)

def test_senden_bricht_ohne_instantly_key_ab(tmp_path, monkeypatch):
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    store = RunStore(tmp_path, "Demo")
    with pytest.raises(SystemExit, match="INSTANTLY_API_KEY"):
        senden(store.run_dir)

class _FakeApolloSource:
    """Ersetzt ApolloSource: liefert 2 feste Leads statt echter API-Aufrufe."""
    def __init__(self, api_key):
        pass
    def search(self, zielgruppe, limit):
        return [
            Lead(first_name="Anna", last_name="Muster", email="anna@firma.de",
                 company="Firma GmbH", title="CEO", website="", source="apollo"),
            Lead(first_name="Bob", last_name="Beispiel", email="bob@firma.de",
                 company="Firma GmbH", title="CTO", website="", source="apollo"),
        ]

class _FakeKI:
    """Ersetzt KI: liefert gueltiges JSON fuer personalize() (System-Prompt
    erwaehnt 'JSON') und 'JA' fuer den Qualitaets-Pruefer (jeder andere
    Aufruf)."""
    def frage(self, system, prompt):
        if "JSON" in system:
            return json.dumps({"betreff": "Kurze Anfrage",
                                "mail_1": " ".join(["Wort"] * 50),
                                "follow_up_1": "F1", "follow_up_2": "F2"})
        return "JA"

class _FakeDatetime:
    """Ersetzt datetime in pipeline.run_store: jeder now()-Aufruf springt um
    1 Sekunde weiter, damit zwei lauf()-Aufrufe im selben Test garantiert in
    verschiedenen Laufordnern landen (RunStore-Zeitstempel hat nur
    Sekunden-Aufloesung)."""
    _zeit = datetime(2026, 1, 1, 0, 0, 0)

    @classmethod
    def now(cls):
        aktuelle = cls._zeit
        cls._zeit += timedelta(seconds=1)
        return aktuelle

def test_lauf_personalisiert_end_zu_ende_und_dedupe_greift_erst_im_naechsten_lauf(
        tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "ApolloSource", _FakeApolloSource)
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setattr(cli, "LAEUFE", tmp_path)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cli.lauf("kunden/demo-gmbh.yaml", 10, None)

    laeufe = sorted((tmp_path / "demo-gmbh").glob("*"))
    assert len(laeufe) == 1
    erster_lauf = laeufe[0]
    personalisierung = json.loads(
        (erster_lauf / "personalisierung.json").read_text(encoding="utf-8"))
    assert len(personalisierung["fertig"]) == 2
    erster_dedupe = json.loads((erster_lauf / "dedupe.json").read_text(encoding="utf-8"))
    assert erster_dedupe["verworfen"] == []
    assert (erster_lauf / "freigabe-vorschau.md").exists()

    # Zweiter, frischer Lauf: jetzt muessen beide Leads aus dem ersten Lauf
    # als "bereits in frueherem Lauf angeschrieben" verworfen werden - das
    # beweist, dass Dedupe ueber Laeufe hinweg weiterhin greift.
    cli.lauf("kunden/demo-gmbh.yaml", 10, None)

    laeufe = sorted((tmp_path / "demo-gmbh").glob("*"))
    assert len(laeufe) == 2
    zweiter_dedupe = json.loads((laeufe[1] / "dedupe.json").read_text(encoding="utf-8"))
    assert len(zweiter_dedupe["verworfen"]) == 2
    assert all(v["grund"] == "bereits in frueherem Lauf angeschrieben"
               for v in zweiter_dedupe["verworfen"])

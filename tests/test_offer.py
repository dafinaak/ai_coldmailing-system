import json, sys, yaml, pytest
from pipeline.offer import draft_offer, uebernehmen, main
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

def test_kaputtes_json_wirft_valueerror():
    ki = FakeKI('{"angebot": kaputt}')
    with pytest.raises(ValueError, match="unvollständig"):
        draft_offer("Text", ki)

def test_main_ohne_genug_argumente_bricht_kontrolliert_ab(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["offer.py"])
    with pytest.raises(SystemExit) as fehler:
        main()
    assert fehler.value.code == 1
    ausgabe = capsys.readouterr().out
    assert "Aufruf: python -m pipeline.offer <url> <kunde.yaml>" in ausgabe

def test_main_bricht_ohne_ki_schluessel_ab(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # keine .env-Datei im Testverzeichnis
    # Beide moeglichen KI-Schluessel entfernen: eine fruehere main()-Ausfuehrung
    # in diesem Modul kann OPENROUTER_API_KEY schon real (nicht ueber
    # monkeypatch) aus der echten .env-Datei des Projekts in os.environ
    # gesetzt haben (lade_dotenv() ueberschreibt bereits gesetzte Variablen
    # nicht, mutiert aber echt) - das muss hier separat entfernt werden.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["offer.py", "http://example.com", "kunde.yaml"])
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        main()

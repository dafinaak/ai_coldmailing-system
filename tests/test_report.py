from pipeline.run_store import RunStore
from pipeline.report import write_report

def test_bericht_enthaelt_alle_zahlen(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": ["doppelt: 3"],
                         "ohne_email": 4})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    for wert in ("10", "3", "6", "1", "doppelt", "4"):
        assert wert in text

def test_bericht_enthaelt_ohne_email_zeile(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": [], "ohne_email": 4})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    assert "Ohne E-Mail übersprungen: 4" in text

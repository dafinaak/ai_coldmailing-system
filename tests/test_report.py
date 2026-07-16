from pipeline.run_store import RunStore
from pipeline.report import write_report

def test_bericht_enthaelt_alle_zahlen(tmp_path):
    store = RunStore(tmp_path, "Demo")
    write_report(store, {"gefunden": 10, "verworfen": 3, "personalisiert": 6,
                         "nacharbeit": 1, "gruende_verworfen": ["doppelt: 3"]})
    text = (store.run_dir / "bericht.md").read_text(encoding="utf-8")
    for wert in ("10", "3", "6", "1", "doppelt"):
        assert wert in text

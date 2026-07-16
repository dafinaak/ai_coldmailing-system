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

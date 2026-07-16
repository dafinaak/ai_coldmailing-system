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

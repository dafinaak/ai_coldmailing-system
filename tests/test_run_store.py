import pytest
from pipeline.run_store import RunStore

def test_resume_wirft_fehler_wenn_ordner_fehlt(tmp_path):
    fehlend = tmp_path / "gibts-nicht"
    with pytest.raises(ValueError, match="existiert nicht"):
        RunStore.resume(fehlend)

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

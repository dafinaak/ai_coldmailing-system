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

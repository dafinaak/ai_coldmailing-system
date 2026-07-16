import json
from pipeline.dedupe import dedupe
from pipeline.models import Lead

def _lead(email):
    return Lead(first_name="A", last_name="B", email=email, company="C",
                title="T", website="", source="apollo")

def test_entfernt_doppelte_in_liste(tmp_path):
    behalten, verworfen = dedupe([_lead("a@x.de"), _lead("A@X.de")], tmp_path)
    assert len(behalten) == 1
    assert verworfen[0]["grund"] == "doppelt in dieser Liste"

def test_entfernt_bekannte_aus_frueheren_laeufen(tmp_path):
    alt = tmp_path / "20260101-000000"
    alt.mkdir()
    (alt / "leads.json").write_text(json.dumps([{"email": "a@x.de"}]), encoding="utf-8")
    behalten, verworfen = dedupe([_lead("a@x.de"), _lead("neu@x.de")], tmp_path)
    assert [l.email for l in behalten] == ["neu@x.de"]
    assert verworfen[0]["grund"] == "bereits in frueherem Lauf angeschrieben"

def test_sperrliste_blockt_domains_auch_mit_wildcard(tmp_path):
    leads = [_lead("chef@digitaldiamonds.agency"), _lead("amt@stadt.bund.de"),
             _lead("ok@neu.de")]
    behalten, verworfen = dedupe(leads, tmp_path,
                                 sperrliste=["digitaldiamonds.agency", "*.bund.de"])
    assert [l.email for l in behalten] == ["ok@neu.de"]
    assert all(v["grund"] == "Domain auf Sperrliste" for v in verworfen)

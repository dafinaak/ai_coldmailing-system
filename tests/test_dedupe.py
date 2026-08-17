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
    # Seit 17.08.2026 zaehlt ein Lauf erst als "angeschrieben", wenn er auch
    # als Kampagne uebergeben wurde - sonst sperrt jeder Probelauf seine
    # Firmen fuer immer (siehe pipeline.dedupe._bekannte_emails).
    (alt / "versand_komplett.json").write_text(
        json.dumps({"campaign_id": "camp-1"}), encoding="utf-8")
    behalten, verworfen = dedupe([_lead("a@x.de"), _lead("neu@x.de")], tmp_path)
    assert [l.email for l in behalten] == ["neu@x.de"]
    assert verworfen[0]["grund"] == "bereits in früherem Lauf angeschrieben"


def test_nur_gefundene_aber_nie_versendete_laeufe_sperren_nicht(tmp_path):
    # Der Fund vom 17.08.2026: 23 Kontakte gefunden, 23 verworfen - alle
    # stammten aus frueheren PROBELAEUFEN, angeschrieben wurde nie jemand.
    alt = tmp_path / "20260101-000000"
    alt.mkdir()
    (alt / "leads.json").write_text(json.dumps([{"email": "a@x.de"}]), encoding="utf-8")

    behalten, verworfen = dedupe([_lead("a@x.de")], tmp_path)

    assert [l.email for l in behalten] == ["a@x.de"]
    assert verworfen == []

def test_sperrliste_blockt_domains_auch_mit_wildcard(tmp_path):
    leads = [_lead("chef@digitaldiamonds.agency"), _lead("amt@stadt.bund.de"),
             _lead("ok@neu.de")]
    behalten, verworfen = dedupe(leads, tmp_path,
                                 sperrliste=["digitaldiamonds.agency", "*.bund.de"])
    assert [l.email for l in behalten] == ["ok@neu.de"]
    assert all(v["grund"] == "Domain auf Sperrliste" for v in verworfen)

def test_sperrliste_greift_auch_ueber_webseiten_domain(tmp_path):
    lead = Lead(first_name="A", last_name="B", email="info@andere-mail.de", company="C",
                title="T", website="https://www.stadt.bund.de/kontakt", source="apollo")
    behalten, verworfen = dedupe([lead], tmp_path, sperrliste=["*.bund.de"])
    assert behalten == []
    assert verworfen[0]["grund"] == "Domain auf Sperrliste"

def test_sperrliste_greift_auch_ohne_schema(tmp_path):
    lead = Lead(first_name="A", last_name="B", email="info@andere-mail.de", company="C",
                title="T", website="www.stadt.bund.de", source="apollo")
    behalten, verworfen = dedupe([lead], tmp_path, sperrliste=["*.bund.de"])
    assert behalten == []
    assert verworfen[0]["grund"] == "Domain auf Sperrliste"

def test_eigener_lauf_zaehlt_nicht_als_frueherer_lauf(tmp_path):
    # Regression: CLI speichert leads.json im aktuellen Laufordner, BEVOR
    # dedupe laeuft. Ohne Ausnahme fuer den eigenen Lauf wuerde dedupe jeden
    # Lead als "bereits in früherem Lauf angeschrieben" verwerfen.
    aktueller_lauf = tmp_path / "20260101-000000"
    aktueller_lauf.mkdir()
    (aktueller_lauf / "leads.json").write_text(
        json.dumps([{"email": "a@x.de"}]), encoding="utf-8")
    behalten, verworfen = dedupe([_lead("a@x.de")], tmp_path, aktueller_lauf=aktueller_lauf)
    assert [l.email for l in behalten] == ["a@x.de"]
    assert verworfen == []

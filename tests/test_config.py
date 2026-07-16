import pytest
from pipeline.config import load_kunde

GUELTIG = """
name: Demo GmbH
zielgruppe:
  titel: [CEO, "Head of Sales"]
  region: [Germany]
  firmengroesse: ["11-50"]
angebot: KI-Automatisierung fuer Vertriebsprozesse
tonalitaet: ruhig, erklaerend, keine Superlative
absender: Leonard von Digital Diamonds
follow_up_tage: [3, 7]
test_empfaenger:
  - test1@example.com
"""

def test_laedt_gueltige_konfig(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG, encoding="utf-8")
    kunde = load_kunde(p)
    assert kunde.name == "Demo GmbH"
    assert kunde.follow_up_tage == [3, 7]

def test_fehlendes_pflichtfeld_wirft_fehler(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text("name: Nur Name", encoding="utf-8")
    with pytest.raises(ValueError, match="angebot"):
        load_kunde(p)

def test_sperrliste_ist_optional(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG, encoding="utf-8")
    assert load_kunde(p).sperrliste == []

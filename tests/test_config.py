import pytest
import yaml
from pipeline.config import load_kunde, lade_globale_sperrliste

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

def test_webseite_ist_optional_und_leer_per_default(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG, encoding="utf-8")
    assert load_kunde(p).webseite == ""

def test_webseite_wird_geladen_wenn_vorhanden(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG + "\nwebseite: https://digitaldiamonds.de\n", encoding="utf-8")
    assert load_kunde(p).webseite == "https://digitaldiamonds.de"

def test_demo_gmbh_laedt_weiterhin():
    assert load_kunde("kunden/demo-gmbh.yaml").name == "Demo GmbH"

def test_maps_suche_und_kontakt_rollen_sind_optional_und_leer_per_default(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG, encoding="utf-8")
    kunde = load_kunde(p)
    assert kunde.maps_suche == ""
    assert kunde.kontakt_rollen == []

def test_maps_suche_und_kontakt_rollen_werden_geladen_wenn_vorhanden(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG + "\nmaps_suche: IT-Dienstleister Hannover\n"
                          "kontakt_rollen: [Geschäftsführer, IT-Leiter]\n", encoding="utf-8")
    kunde = load_kunde(p)
    assert kunde.maps_suche == "IT-Dienstleister Hannover"
    assert kunde.kontakt_rollen == ["Geschäftsführer", "IT-Leiter"]

def test_demo_gmbh_hat_maps_suche_und_kontakt_rollen():
    kunde = load_kunde("kunden/demo-gmbh.yaml")
    assert kunde.maps_suche == "IT-Dienstleister Hannover"
    assert kunde.kontakt_rollen == ["Geschäftsführer", "IT-Leiter"]

def test_follow_up_tage_muss_liste_mit_mindestens_zwei_zahlen_sein(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG.replace("follow_up_tage: [3, 7]", "follow_up_tage: [3]"),
                encoding="utf-8")
    with pytest.raises(ValueError, match="follow_up_tage"):
        load_kunde(p)

def test_follow_up_tage_muss_zahlen_enthalten(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG.replace("follow_up_tage: [3, 7]", "follow_up_tage: [drei, sieben]"),
                encoding="utf-8")
    with pytest.raises(ValueError, match="follow_up_tage"):
        load_kunde(p)

def test_follow_up_tage_muss_aufsteigend_sein(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG.replace("follow_up_tage: [3, 7]", "follow_up_tage: [7, 3]"),
                encoding="utf-8")
    with pytest.raises(ValueError, match="follow_up_tage"):
        load_kunde(p)

def test_follow_up_tage_darf_nicht_gleich_sein(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG.replace("follow_up_tage: [3, 7]", "follow_up_tage: [3, 3]"),
                encoding="utf-8")
    with pytest.raises(ValueError, match="follow_up_tage"):
        load_kunde(p)

def test_test_empfaenger_darf_nicht_leer_sein(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG.replace("test_empfaenger:\n  - test1@example.com",
                                 "test_empfaenger: []"), encoding="utf-8")
    with pytest.raises(ValueError, match="test_empfaenger"):
        load_kunde(p)

def test_test_empfaenger_muss_strings_enthalten(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG.replace("test_empfaenger:\n  - test1@example.com",
                                 "test_empfaenger: [1, 2]"), encoding="utf-8")
    with pytest.raises(ValueError, match="test_empfaenger"):
        load_kunde(p)

def test_sperrliste_muss_liste_sein_wenn_vorhanden(tmp_path):
    p = tmp_path / "kunde.yaml"
    p.write_text(GUELTIG + "\nsperrliste: nicht-eine-liste\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sperrliste"):
        load_kunde(p)

def test_lade_globale_sperrliste_liest_datei(tmp_path):
    (tmp_path / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["*.bund.de", "digitaldiamonds.de"]), encoding="utf-8")
    assert lade_globale_sperrliste(tmp_path) == ["*.bund.de", "digitaldiamonds.de"]

def test_lade_globale_sperrliste_ohne_datei_gibt_leere_liste(tmp_path):
    assert lade_globale_sperrliste(tmp_path) == []

def test_lade_globale_sperrliste_wirft_bei_falschem_aufbau(tmp_path):
    (tmp_path / "sperrliste-global.yaml").write_text(
        yaml.safe_dump({"nicht": "eine-liste"}), encoding="utf-8")
    with pytest.raises(ValueError, match="sperrliste-global.yaml"):
        lade_globale_sperrliste(tmp_path)

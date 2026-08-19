"""PLZ und Ort als getrennte Felder (Olivers Vorgabe, 19.08.2026).

Vorher stand beides kombiniert als "30161 Hannover" in einer Spalte.
Jetzt gilt ueberall: eigene Spalte/eigenes Feld fuer die Postleitzahl,
eigenes fuer den Ortsnamen. Alte Datensaetze (leeres "ort"-Feld) muessen
weiter funktionieren - der Name kommt dann aus der Adresszeile.
"""
import json

from pipeline.firmen_filter import stadt
from pipeline.kontakte_excel import mappe_bauen
from pipeline.listen_fusion import fusionieren


def test_stadt_nimmt_das_ort_feld_wenn_gefuellt():
    assert stadt({"ort": "Hannover", "plz": "30161"}) == "Hannover"


def test_stadt_liest_alte_saetze_aus_der_adresszeile():
    firma = {"ort": "", "plz": "30161",
             "address": "Rolandstr. 2-3, 30161 Hannover (Vahrenwald)"}
    assert stadt(firma) == "Hannover"


def test_stadt_ohne_alles_bleibt_leer():
    assert stadt({"name": "A GmbH"}) == ""


def test_fusion_speichert_den_ort_aus_der_quelle():
    firmen, _ = fusionieren([[{"name": "A GmbH", "domain": "a.de",
                               "plz": "30161", "ort": "Hannover",
                               "quelle": "maps"}]], ("30",))
    assert firmen[0]["ort"] == "Hannover"


def test_fusion_liest_den_ort_einmal_aus_der_adresse():
    # Quellen ohne eigenes Ort-Feld: beim Speichern wird die Adresszeile
    # gelesen, damit der Bestand von Anfang an getrennte Felder traegt.
    firmen, _ = fusionieren([[{
        "name": "A GmbH", "domain": "a.de", "plz": "30161",
        "address": "Rolandstr. 2, 30161 Hannover", "quelle": "maps"}]],
        ("30",))
    assert firmen[0]["ort"] == "Hannover"


def test_fusion_ergaenzt_den_ort_aus_spaeterer_quelle():
    firmen, _ = fusionieren([
        [{"name": "A GmbH", "domain": "a.de", "plz": "30161",
          "quelle": "maps"}],
        [{"name": "A GmbH", "domain": "a.de", "plz": "30161",
          "ort": "Hannover", "quelle": "gelbe_seiten"}]], ("30",))
    assert firmen[0]["ort"] == "Hannover"


def test_excel_traegt_plz_und_ort_getrennt(tmp_path):
    (tmp_path / "leads.json").write_text(json.dumps({"leads": [
        {"first_name": "Tim", "last_name": "Cappelmann", "email": "t@a.de",
         "company": "A GmbH", "title": "Geschäftsführer",
         "website": "https://a.de", "source": "impressum", "notizen": []}]}),
        encoding="utf-8")
    (tmp_path / "firmen.json").write_text(json.dumps([
        {"name": "A GmbH", "domain": "a.de", "website": "https://a.de",
         "plz": "30161", "ort": "Hannover", "telefon": "0511 1",
         "ausgang": "mit_entscheider"}]), encoding="utf-8")
    (tmp_path / "personalisierung.json").write_text(
        json.dumps({"fertig": [], "nacharbeit": []}), encoding="utf-8")

    zeilen = [list(r) for r in
              mappe_bauen(tmp_path)["Kontakte"].iter_rows(values_only=True)]

    kopf = zeilen[0]
    assert "PLZ" in kopf and "Ort" in kopf
    assert zeilen[1][kopf.index("PLZ")] == "30161"
    assert zeilen[1][kopf.index("Ort")] == "Hannover"
    # Kombinierte Werte wie "30161 Hannover" duerfen nirgends mehr stehen.
    assert "30161 Hannover" not in [str(w) for w in zeilen[1]]

"""Der Ortsname gehört neben die Postleitzahl.

Die Quellen liefern die Adresse als EINE Zeile; das Feld "ort" ist bei
allen 1.481 gesammelten Firmen leer. In Schritt 4 und in der Excel-Mappe
stand deshalb nur "30161" - eine Zahl, die niemandem etwas sagt, am
wenigsten der Person, die mit der Anruf-Liste telefoniert (18.08.2026).
"""
import pytest

from pipeline.firmen_filter import ort_aus_adresse, ort_mit_plz


def test_ort_wird_aus_der_adresszeile_geholt():
    # Wörtlich eine Adresse aus dem echten Bestand.
    assert ort_aus_adresse("Rolandstr. 2-3, 30161 Hannover (Vahrenwald)",
                            "30161") == "Hannover"


def test_stadtteil_in_klammern_bleibt_draussen():
    assert "(" not in ort_aus_adresse(
        "Spielhagenstr. 25, 30171 Hannover (Südstadt)", "30171")


def test_zweiteiliger_ortsname_bleibt_ganz():
    assert ort_aus_adresse("Musterweg 1, 32105 Bad Salzuflen", "32105") == \
        "Bad Salzuflen"


def test_ohne_bekannte_plz_wird_die_erste_gefunden():
    assert ort_aus_adresse("Musterweg 1, 30159 Hannover") == "Hannover"


def test_falsche_plz_findet_trotzdem_etwas():
    # Die mitgegebene PLZ passt nicht zur Adresse - dann eben die aus der
    # Zeile, statt gar nichts zu liefern.
    assert ort_aus_adresse("Musterweg 1, 30159 Hannover", "99999") == "Hannover"


def test_ohne_adresse_kein_geratener_ort():
    assert ort_aus_adresse("", "30159") == ""
    assert ort_aus_adresse(None) == ""
    assert ort_aus_adresse("Nur ein Straßenname ohne Zahl") == ""


def test_anzeige_verbindet_plz_und_ort():
    firma = {"plz": "30161", "address": "Rolandstr. 2-3, 30161 Hannover"}

    assert ort_mit_plz(firma) == "30161 Hannover"


def test_gepflegtes_ort_feld_gewinnt():
    # Kommt eines Tages ein "ort" aus einer Quelle, gilt das - ohne Raten.
    firma = {"plz": "30161", "ort": "Hannover-Vahrenwald",
             "address": "Rolandstr. 2-3, 30161 Hannover"}

    assert ort_mit_plz(firma) == "30161 Hannover-Vahrenwald"


def test_nur_plz_bleibt_nur_plz():
    assert ort_mit_plz({"plz": "30161"}) == "30161"


def test_ganz_ohne_angaben_leer():
    assert ort_mit_plz({}) == ""

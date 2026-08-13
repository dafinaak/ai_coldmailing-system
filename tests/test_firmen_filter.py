"""Picking companies out of the pool.

The filter decides who gets written to, so the two ways it could quietly
lie are pinned here: dropping a company that should have been offered,
and hiding companies whose location we cannot judge.
"""
import pytest

from pipeline.firmen_filter import (
    dienste_vorschlagen, filtern, ist_gesperrt, passt_zum_dienst,
)


def firma(name, plz="30159", website="https://a.de", kategorien=("IT-Berater",)):
    return {"name": name, "plz": plz, "website": website,
            "domain": website.replace("https://", ""),
            "categories": list(kategorien)}


HANNOVER = firma("Hannover IT", plz="30159")
HILDESHEIM = firma("Hildesheim IT", plz="31134")          # ~30 km entfernt
MUENCHEN = firma("München IT", plz="80331")               # ~600 km entfernt
OHNE_PLZ = firma("Ort unbekannt", plz="")


def test_umkreis_nimmt_nahe_firmen_und_laesst_ferne_draussen():
    ergebnis = filtern([HANNOVER, HILDESHEIM, MUENCHEN],
                       ort="Hannover", radius_km=40)

    namen = [f["name"] for f in ergebnis["treffer"]]
    assert namen == ["Hannover IT", "Hildesheim IT"]
    assert ergebnis["zahlen"]["raus_umkreis"] == 1


def test_kleiner_umkreis_laesst_nur_die_stadt_uebrig():
    ergebnis = filtern([HANNOVER, HILDESHEIM], ort="30159", radius_km=10)

    assert [f["name"] for f in ergebnis["treffer"]] == ["Hannover IT"]


def test_treffer_sind_nach_naehe_sortiert():
    ergebnis = filtern([MUENCHEN, HILDESHEIM, HANNOVER],
                       ort="Hannover", radius_km=1000)

    entfernungen = [f["entfernung_km"] for f in ergebnis["treffer"]]
    assert entfernungen == sorted(entfernungen)
    assert ergebnis["treffer"][0]["name"] == "Hannover IT"


def test_firmen_ohne_ort_werden_getrennt_gezeigt_statt_verschwiegen():
    ergebnis = filtern([HANNOVER, OHNE_PLZ], ort="Hannover", radius_km=40)

    assert [f["name"] for f in ergebnis["treffer"]] == ["Hannover IT"]
    assert [f["name"] for f in ergebnis["ohne_ort"]] == ["Ort unbekannt"]
    assert ergebnis["zahlen"]["ohne_ort"] == 1


def test_ohne_umkreis_zaehlt_der_ort_nicht():
    ergebnis = filtern([HANNOVER, MUENCHEN, OHNE_PLZ], dienste=["IT-Berater"])

    assert len(ergebnis["treffer"]) == 3
    assert ergebnis["ohne_ort"] == []


def test_unbekannter_ort_sagt_es_deutlich_statt_leer_zu_liefern():
    with pytest.raises(ValueError, match="nicht gefunden"):
        filtern([HANNOVER], ort="Gibtsnichthausen", radius_km=10)


def test_dienst_trifft_kategorie_und_namen():
    systemhaus = firma("Meyer Systemhaus", kategorien=["Computerservice"])

    assert passt_zum_dienst(systemhaus, ["systemhaus"])      # ueber den Namen
    assert passt_zum_dienst(systemhaus, ["computerservice"])  # ueber Kategorie
    assert not passt_zum_dienst(systemhaus, ["webdesign"])


def test_mehrere_dienste_wirken_als_oder():
    ergebnis = filtern(
        [firma("A", kategorien=["Webdesigner"]),
         firma("B", kategorien=["IT-Berater"]),
         firma("C", kategorien=["Blumenladen"])],
        dienste=["webdesigner", "it-berater"])

    assert [f["name"] for f in ergebnis["treffer"]] == ["A", "B"]
    assert ergebnis["zahlen"]["raus_dienst"] == 1


def test_ohne_dienstangabe_kommen_alle_durch():
    ergebnis = filtern([firma("A", kategorien=["Blumenladen"])], dienste=[])

    assert len(ergebnis["treffer"]) == 1


def test_gesperrte_domains_fliegen_raus():
    ergebnis = filtern([firma("Gut", website="https://gut.de"),
                        firma("Boese", website="https://boese.de")],
                       gesperrte_domains=["boese.de"])

    assert [f["name"] for f in ergebnis["treffer"]] == ["Gut"]
    assert ergebnis["zahlen"]["raus_gesperrt"] == 1


def test_sperrmuster_mit_stern_trifft_unterdomains():
    behoerde = firma("Amt", website="https://stadt.bund.de")

    assert ist_gesperrt(behoerde, ["*.bund.de"])
    assert not ist_gesperrt(firma("Frei", website="https://frei.de"), ["*.bund.de"])


def test_firmen_ohne_webseite_fliegen_raus_denn_ohne_geht_nichts():
    # Ohne Webseite kann die KI kein Impressum lesen - die Firma waere
    # im naechsten Schritt ohnehin ein Fehlschlag.
    ergebnis = filtern([HANNOVER, firma("Keine Seite", website="")])

    assert [f["name"] for f in ergebnis["treffer"]] == ["Hannover IT"]
    assert ergebnis["zahlen"]["raus_ohne_webseite"] == 1


def test_zahlen_gehen_auf():
    firmen = [HANNOVER, HILDESHEIM, MUENCHEN, OHNE_PLZ,
              firma("Gesperrt", website="https://boese.de"),
              firma("Ohne Seite", website="")]
    ergebnis = filtern(firmen, ort="Hannover", radius_km=40,
                       gesperrte_domains=["boese.de"])
    z = ergebnis["zahlen"]

    assert z["gesamt"] == len(firmen)
    assert (z["treffer"] + z["ohne_ort"] + z["raus_umkreis"] + z["raus_dienst"]
            + z["raus_gesperrt"] + z["raus_ohne_webseite"]) == z["gesamt"]


def test_vorschlaege_kommen_aus_dem_echten_bestand():
    firmen = [firma("A", kategorien=["IT-Berater"]),
              firma("B", kategorien=["IT-Berater"]),
              firma("C", kategorien=["Webdesigner", "office=it"])]

    vorschlaege = dienste_vorschlagen(firmen)

    assert vorschlaege[0] == "IT-Berater"          # haeufigste zuerst
    assert "Webdesigner" in vorschlaege
    assert "office=it" not in vorschlaege          # Maschinen-Kram raus

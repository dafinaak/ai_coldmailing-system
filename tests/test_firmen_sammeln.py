"""Firmen fuer einen Umkreis frisch sammeln.

Der Bestand deckte nur die Postleitregionen 30 und 31 ab - fuer jede
andere Stadt lieferte Schritt 4 des Formulars null Firmen. Diese Bruecke
uebersetzt "Ort + Radius + Dienste" in das, was die Quellen brauchen.

Sammeln kostet Geld (rund sieben Dollar fuer zwei Postleitregionen am
29.07.2026), deshalb hier ausschliesslich mit gefakten Quellen.
"""
import json

import pytest

from pipeline.firmen_sammeln import (bounding_box, kreis_geojson, ordnername,
                                      plz_im_umkreis, sammeln, speichern)

# Zwei Orte, 100 km auseinander, plus ein Nachbar-Ort dicht daneben.
TABELLE = {
    "30159": {"ort": "Hannover", "lat": 52.3759, "lon": 9.7320},
    "30880": {"ort": "Laatzen", "lat": 52.3150, "lon": 9.7960},
    "80331": {"ort": "München", "lat": 48.1372, "lon": 11.5755},
}


class FakeMaps:
    def __init__(self, firmen=(), fehler=None):
        self.firmen, self.fehler, self.aufrufe = list(firmen), fehler, []

    def search_gebiet(self, suchbegriffe, gebiet_geojson, limit_pro_suche,
                      schlaf=None):
        self.aufrufe.append((tuple(suchbegriffe), gebiet_geojson))
        if self.fehler:
            raise RuntimeError(self.fehler)
        return self.firmen


class FakeGelbeSeiten:
    def __init__(self, firmen=()):
        self.firmen, self.aufrufe = list(firmen), []

    def search(self, suchbegriff, ort, max_seiten=1):
        self.aufrufe.append((suchbegriff, ort))
        return self.firmen


class FakeOverpass:
    def __init__(self, firmen=()):
        self.firmen, self.aufrufe = list(firmen), []

    def search(self, plz_praefixe, bbox, merkmale=None):
        self.aufrufe.append((plz_praefixe, bbox))
        return self.firmen


def _firma(name, domain, plz="30159", quelle="maps"):
    return {"name": name, "domain": domain, "website": f"https://{domain}",
            "plz": plz, "telefon": "", "categories": ["IT"], "quelle": quelle}


# --- Umkreis --------------------------------------------------------------

def test_umkreis_nimmt_nur_was_nah_genug_ist():
    nah = plz_im_umkreis("Hannover", 15, TABELLE)

    assert "30159" in nah and "30880" in nah
    assert "80331" not in nah, "München liegt nicht im Umkreis von Hannover"


def test_kleiner_radius_laesst_den_nachbarort_draussen():
    assert plz_im_umkreis("Hannover", 3, TABELLE) == ["30159"]


def test_postleitzahl_statt_ortsname_geht_auch():
    assert "30159" in plz_im_umkreis("30159", 15, TABELLE)


def test_unbekannter_ort_sagt_es_klar():
    with pytest.raises(ValueError, match="Timbuktu"):
        plz_im_umkreis("Timbuktu", 10, TABELLE)


# --- Geometrie ------------------------------------------------------------

def test_kreis_ist_ein_geschlossenes_vieleck():
    kreis = kreis_geojson((52.3759, 9.7320), 25)
    ring = kreis["coordinates"][0]

    assert kreis["type"] == "Polygon"
    assert ring[0] == ring[-1], "GeoJSON-Ringe muessen geschlossen sein"


def test_kreis_waechst_mit_dem_radius():
    klein = kreis_geojson((52.3759, 9.7320), 10)["coordinates"][0]
    gross = kreis_geojson((52.3759, 9.7320), 50)["coordinates"][0]

    assert max(p[1] for p in gross) > max(p[1] for p in klein)


def test_bounding_box_umschliesst_den_mittelpunkt():
    sued, west, nord, ost = bounding_box((52.3759, 9.7320), 25)

    assert sued < 52.3759 < nord
    assert west < 9.7320 < ost


# --- Sammeln --------------------------------------------------------------

def test_alle_quellen_werden_gefragt_und_zusammengefuehrt():
    maps = FakeMaps([_firma("Eins", "eins.de")])
    gs = FakeGelbeSeiten([_firma("Zwei", "zwei.de", quelle="gelbe_seiten")])
    op = FakeOverpass([_firma("Drei", "drei.de", quelle="overpass")])

    firmen, bericht = sammeln("Hannover", 15, ["Webdesigner"], maps=maps,
                              gelbe_seiten=gs, overpass=op, tabelle=TABELLE)

    assert {f["domain"] for f in firmen} == {"eins.de", "zwei.de", "drei.de"}
    assert maps.aufrufe and gs.aufrufe and op.aufrufe
    assert bericht["ort"] == "Hannover"


def test_dieselbe_firma_aus_zwei_quellen_steht_einmal_da():
    maps = FakeMaps([_firma("Eins", "eins.de")])
    gs = FakeGelbeSeiten([_firma("Eins GmbH", "eins.de", quelle="gelbe_seiten")])

    firmen, _ = sammeln("Hannover", 15, ["Webdesigner"], maps=maps,
                        gelbe_seiten=gs, tabelle=TABELLE)

    assert len(firmen) == 1


def test_eine_ausgefallene_quelle_stoppt_die_sammlung_nicht():
    # Bezahlt ist der Rest ohnehin - eine halbe Sammlung ist mehr wert
    # als gar keine.
    maps = FakeMaps(fehler="Apify antwortet mit 500")
    gs = FakeGelbeSeiten([_firma("Zwei", "zwei.de", quelle="gelbe_seiten")])

    firmen, bericht = sammeln("Hannover", 15, ["Webdesigner"], maps=maps,
                              gelbe_seiten=gs, tabelle=TABELLE)

    assert [f["domain"] for f in firmen] == ["zwei.de"]
    assert "maps" in bericht["quellen_fehler"]


def test_jeder_dienst_wird_bei_gelben_seiten_einzeln_gesucht():
    gs = FakeGelbeSeiten()

    sammeln("Hannover", 15, ["Webdesigner", "IT-Berater"], gelbe_seiten=gs,
            tabelle=TABELLE)

    assert [a[0] for a in gs.aufrufe] == ["Webdesigner", "IT-Berater"]


def test_ohne_suchbegriffe_wird_nichts_gesammelt():
    with pytest.raises(ValueError, match="Suchbegriffe"):
        sammeln("Hannover", 15, [], maps=FakeMaps(), tabelle=TABELLE)


def test_firmen_ausserhalb_der_region_fliegen_raus():
    maps = FakeMaps([_firma("Fern", "fern.de", plz="80331")])

    firmen, bericht = sammeln("Hannover", 15, ["Webdesigner"], maps=maps,
                              tabelle=TABELLE)

    assert firmen == []
    assert bericht["fremde_plz"] == 1


# --- Ablegen --------------------------------------------------------------

def test_sammlung_wird_als_eigener_ordner_abgelegt(tmp_path):
    ziel = speichern(tmp_path, [_firma("Eins", "eins.de")], {"ort": "Hannover"},
                     "hannover-25km-20260817")

    assert (ziel / "firmen.json").exists()
    assert (ziel / "sammelbericht.json").exists()
    assert json.loads((ziel / "firmen.json").read_text(encoding="utf-8"))


def test_aeltere_sammlung_bleibt_unberuehrt(tmp_path):
    alt = speichern(tmp_path, [_firma("Alt", "alt.de")], {}, "alt")
    speichern(tmp_path, [_firma("Neu", "neu.de")], {}, "neu")

    inhalt = json.loads((alt / "firmen.json").read_text(encoding="utf-8"))
    assert [f["domain"] for f in inhalt] == ["alt.de"]


def test_ordnername_ist_sprechend_und_dateisystem_tauglich():
    assert ordnername("Frankfurt am Main", 25, "20260817") == \
        "frankfurt-am-main-25km-20260817"

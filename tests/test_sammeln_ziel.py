"""Sammeln bis zum Ziel - und deutschlandweit (Olivers Vorgabe 19.08.2026).

"100 angefragt" soll so nah wie moeglich an 100 einzigartige Firmen
kommen: Gebiet fuer Gebiet, nach jedem wird fusioniert und gezaehlt.
Nichts wird erfunden, um das Ziel zu erreichen - reicht es nicht, nennt
der Bericht den Grund. Diese Tests fahren den Ablauf mit falschen
Quellen ab, Geld fliesst keins.
"""
import pytest

from pipeline.firmen_sammeln import regionen_deutschland, sammeln_bis_ziel
from web import sammelmanager

# Kleine Kunst-Tabelle: Region "10" (Berlin, 2 PLZ - die dichteste),
# Region "80" (Muenchen, 1 PLZ).
TABELLE = {
    "10115": {"ort": "Berlin", "lat": 52.53, "lon": 13.38},
    "10117": {"ort": "Berlin", "lat": 52.52, "lon": 13.39},
    "80331": {"ort": "München", "lat": 48.14, "lon": 11.57},
}


def firma(nr, plz="10115", ort="Berlin"):
    return {"name": f"Firma {nr}", "website": f"https://f{nr}.de",
            "domain": f"f{nr}.de", "plz": plz, "ort": ort,
            "categories": ["IT-Service"], "quelle": "maps"}


class GebietsMaps:
    """Liefert je Gebiets-Abruf die naechste vorbereitete Liste."""

    def __init__(self, lieferungen):
        self.lieferungen = list(lieferungen)
        self.abrufe = []

    def search_gebiet(self, suchbegriffe, gebiet_geojson, limit_pro_suche,
                      schlaf=None):
        self.abrufe.append({"begriffe": list(suchbegriffe),
                            "limit": limit_pro_suche})
        return self.lieferungen.pop(0) if self.lieferungen else []


def test_sammelt_ueber_regionen_bis_das_ziel_erreicht_ist():
    # Region 1 liefert 2 Firmen (eine doppelt), Region 2 die restlichen.
    maps = GebietsMaps([
        [firma(1), firma(1), firma(2)],
        [firma(3, plz="80331", ort="München"),
         firma(4, plz="80331", ort="München")],
    ])

    firmen, bericht = sammeln_bis_ziel(
        "", 0, ["IT-Service"], 4, maps=maps, tabelle=TABELLE)

    assert len(firmen) == 4
    assert bericht["grund_ende"] == "ziel_erreicht"
    assert bericht["deutschlandweit"] is True
    assert bericht["gebiete_durchsucht"] == 2
    assert [g["neu_einzigartig"] for g in bericht["je_gebiet"]] == [2, 2]
    # Dichteste Region (10, Berlin) kam zuerst.
    assert "10" in bericht["je_gebiet"][0]["gebiet"]


def test_hoert_auf_sobald_das_ziel_steht():
    maps = GebietsMaps([[firma(1), firma(2)], [firma(9)]])

    _, bericht = sammeln_bis_ziel("", 0, ["IT-Service"], 2,
                                  maps=maps, tabelle=TABELLE)

    assert bericht["gebiete_durchsucht"] == 1
    assert len(maps.abrufe) == 1          # Region 2 wurde nie bezahlt


def test_zu_wenig_wird_ehrlich_gemeldet_statt_aufgefuellt():
    maps = GebietsMaps([[firma(1)], []])

    firmen, bericht = sammeln_bis_ziel("", 0, ["IT-Service"], 5,
                                       maps=maps, tabelle=TABELLE)

    assert len(firmen) == 1
    assert bericht["angefragt"] == 5
    assert bericht["einzigartig"] == 1
    assert bericht["grund_ende"] == "quellen_erschoepft"


def test_dieselbe_firma_aus_zwei_regionen_zaehlt_einmal():
    maps = GebietsMaps([[firma(1)], [firma(1, plz="80331", ort="München")]])

    firmen, bericht = sammeln_bis_ziel("", 0, ["IT-Service"], 2,
                                       maps=maps, tabelle=TABELLE)

    assert len(firmen) == 1
    assert bericht["je_gebiet"][1]["neu_einzigartig"] == 0


def test_mit_ort_bleibt_es_ein_gebiet_mit_plz_filter():
    # Fremde PLZ fliegen raus wie bei der bestehenden Umkreis-Sammlung.
    maps = GebietsMaps([[firma(1), firma(2, plz="80331", ort="München")]])

    firmen, bericht = sammeln_bis_ziel("Berlin", 25, ["IT-Service"], 5,
                                       maps=maps, tabelle=TABELLE)

    assert [f["name"] for f in firmen] == ["Firma 1"]
    assert bericht["deutschlandweit"] is False
    assert bericht["grund_ende"] == "quellen_erschoepft"


def test_unbekannter_ort_ist_ein_klarer_fehler():
    with pytest.raises(ValueError):
        sammeln_bis_ziel("Atlantis", 25, ["IT"], 5, maps=GebietsMaps([]),
                         tabelle=TABELLE)


def test_familie_wird_zur_kurzen_suchliste():
    maps = GebietsMaps([[firma(1)]])

    sammeln_bis_ziel("", 0, ["Computer Services"], 1,
                     maps=maps, tabelle=TABELLE)

    begriffe = maps.abrufe[0]["begriffe"]
    assert "IT-Dienstleister" in begriffe
    assert len(begriffe) <= 10


def test_regionen_sind_nach_dichte_sortiert():
    regionen = regionen_deutschland(TABELLE)
    assert [r["praefix"] for r in regionen] == ["10", "80"]
    assert regionen[0]["label"] == "Berlin"
    assert regionen[0]["plz_anzahl"] == 2


def test_sammelmanager_baut_den_deutschland_befehl(tmp_path):
    job = sammelmanager.starte(
        tmp_path, "k1", "", 10, ["IT-Service"], befehl=["true"],
        ziel_anzahl=100, deutschlandweit=True)
    meta = (job / "meta.json").read_text(encoding="utf-8")
    assert '"ziel_anzahl": 100' in meta
    assert '"deutschlandweit": true' in meta


def test_sammelmanager_ohne_ort_und_ohne_flagge_bleibt_verboten(tmp_path):
    # Ein verlorener Formularwert darf keine Landessammlung ausloesen.
    with pytest.raises(sammelmanager.SammelFehler):
        sammelmanager.starte(tmp_path, "k1", "", 10, ["IT-Service"],
                             befehl=["true"])

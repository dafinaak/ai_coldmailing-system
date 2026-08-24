"""Sammeln bis zum Ziel - und deutschlandweit (Olivers Vorgabe 19.08.2026).

"100 angefragt" soll so nah wie moeglich an 100 einzigartige Firmen
kommen: Gebiet fuer Gebiet, nach jedem wird fusioniert und gezaehlt.
Nichts wird erfunden, um das Ziel zu erreichen - reicht es nicht, nennt
der Bericht den Grund. Diese Tests fahren den Ablauf mit falschen
Quellen ab, Geld fliesst keins.
"""
import pytest

from pipeline.firmen_sammeln import (plz_liste_lesen, regionen_deutschland,
                                      sammeln_bis_ziel)
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


class GelbeSeitenFake:
    """Merkt sich, mit welchem Ort das Verzeichnis befragt wurde."""

    def __init__(self):
        self.abrufe = []

    def search(self, begriff, ort, seiten=1):
        self.abrufe.append({"begriff": begriff, "ort": ort, "seiten": seiten})
        return []


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


def test_bericht_zaehlt_bekannt_und_neu_gegen_den_bestand(tmp_path):
    # Olivers Beispiel: von 2 Gefundenen ist 1 schon im Bestand - die
    # bleibt erhalten, nur die neue kommt dazu, nichts wird geloescht.
    bestand = tmp_path / "laeufe" / "leadquellen" / "alt"
    bestand.mkdir(parents=True)
    import json
    (bestand / "firmen.json").write_text(
        json.dumps([{"name": "Firma 1", "domain": "f1.de"}]),
        encoding="utf-8")
    maps = GebietsMaps([[firma(1), firma(2)]])

    _, bericht = sammeln_bis_ziel("", 0, ["IT-Service"], 2, maps=maps,
                                  tabelle=TABELLE, daten_dir=tmp_path)

    assert bericht["vorher_bekannt"] == 1
    assert bericht["neu"] == 1


# --- Feste PLZ-Liste (Olivers Gebiet 32-39, Auftrag 21.08.2026) ----------
# Ein Auftrag kann statt "Umkreis" oder "ganz Deutschland" eine feste
# Liste einzelner Postleitzahlen sein. Dann wird nur in den betroffenen
# Regionen gesucht, und behalten wird NUR, was genau auf einem dieser
# Codes sitzt - eine Nachbar-PLZ derselben Region ist nicht beauftragt.


def test_plz_liste_sucht_nur_diese_regionen_und_behaelt_nur_diese_codes():
    # Beauftragt ist allein 10115. 10117 liegt in derselben Region und
    # muss trotzdem rausfliegen; Region 80 wird gar nicht erst bezahlt.
    maps = GebietsMaps([[firma(1, plz="10115"), firma(2, plz="10117")]])

    firmen, bericht = sammeln_bis_ziel(
        "", 0, ["IT-Service"], 500, maps=maps, tabelle=TABELLE,
        plz_liste=["10115"])

    assert [f["name"] for f in firmen] == ["Firma 1"]
    assert len(maps.abrufe) == 1
    assert bericht["gebiete_durchsucht"] == 1
    assert bericht["deutschlandweit"] is False
    assert bericht["plz_liste_anzahl"] == 1
    assert bericht["fremde_plz"] == 1


def test_plz_liste_sucht_jede_betroffene_region():
    maps = GebietsMaps([[firma(1, plz="10115")],
                        [firma(2, plz="80331", ort="München")]])

    firmen, bericht = sammeln_bis_ziel(
        "", 0, ["IT-Service"], 500, maps=maps, tabelle=TABELLE,
        plz_liste=["10115", "80331"])

    assert sorted(f["name"] for f in firmen) == ["Firma 1", "Firma 2"]
    assert bericht["gebiete_durchsucht"] == 2
    assert bericht["grund_ende"] == "quellen_erschoepft"


def test_plz_liste_fragt_gelbe_seiten_je_region_mit_dem_regionsort():
    # Deutschlandweit stellt die Sammlung EINE "Deutschland"-Abfrage.
    # Bei einer PLZ-Liste waere das viel zu grob bezahlt - hier gehoert
    # je Region der Ortsname hin.
    gs = GelbeSeitenFake()
    maps = GebietsMaps([[], []])

    sammeln_bis_ziel("", 0, ["IT-Service"], 500, maps=maps,
                     gelbe_seiten=gs, tabelle=TABELLE,
                     plz_liste=["10115", "80331"])

    orte = {a["ort"] for a in gs.abrufe}
    assert orte == {"Berlin", "München"}
    assert "Deutschland" not in orte


def test_plz_liste_und_ort_zusammen_sind_ein_fehler():
    # Zwei Angaben, die dasselbe bestimmen - das muss auffallen, nicht
    # stillschweigend eine der beiden gewinnen.
    with pytest.raises(ValueError):
        sammeln_bis_ziel("Berlin", 25, ["IT-Service"], 5,
                         maps=GebietsMaps([]), tabelle=TABELLE,
                         plz_liste=["10115"])


def test_plz_liste_datei_wird_gelesen_kommentare_und_leerzeilen_raus(tmp_path):
    datei = tmp_path / "plz.txt"
    datei.write_text("# Olivers Gebiet\n32049\n\n33098\n32049\n",
                     encoding="utf-8")

    assert plz_liste_lesen(datei) == ["32049", "33098"]


def test_plz_liste_datei_ohne_codes_ist_ein_fehler(tmp_path):
    datei = tmp_path / "leer.txt"
    datei.write_text("# nur ein Kommentar\n\n", encoding="utf-8")

    with pytest.raises(ValueError):
        plz_liste_lesen(datei)


def test_krumme_zeile_in_der_plz_datei_ist_ein_fehler(tmp_path):
    # Eine unbemerkt verschluckte Zeile hiesse: ein Gebiet fehlt im Lauf,
    # ohne dass es jemand sieht.
    datei = tmp_path / "krumm.txt"
    datei.write_text("32049\n3205\n", encoding="utf-8")

    with pytest.raises(ValueError):
        plz_liste_lesen(datei)


def test_cli_bricht_ab_bei_plz_liste_und_ort_zusammen(tmp_path):
    # Die Abbrueche muessen greifen, BEVOR irgendeine bezahlte Quelle
    # angefasst wird - deshalb ohne APIFY_API_KEY geprueft.
    from pipeline.__main__ import sammeln_cli

    datei = tmp_path / "plz.txt"
    datei.write_text("32049\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        sammeln_cli("Berlin", 25, ["IT-Service"], 200,
                    plz_liste_datei=str(datei))


def test_cli_bricht_ab_bei_leerer_plz_datei(tmp_path):
    from pipeline.__main__ import sammeln_cli

    datei = tmp_path / "leer.txt"
    datei.write_text("\n\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        sammeln_cli("", 25, ["IT-Service"], 200, plz_liste_datei=str(datei))


def test_cli_bricht_ab_wenn_die_plz_datei_fehlt(tmp_path):
    from pipeline.__main__ import sammeln_cli

    with pytest.raises(SystemExit):
        sammeln_cli("", 25, ["IT-Service"], 200,
                    plz_liste_datei=str(tmp_path / "gibtsnicht.txt"))

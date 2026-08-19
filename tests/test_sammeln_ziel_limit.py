"""Kosto-Kontrolle des Ziel-Sammelns: Limits richten sich am Restbedarf.

Live-Fund 19.08.2026: das Maps-Limit gilt JE SUCHBEGRIFF - mit zehn
Familien-Begriffen holte "Ziel 100" 3.530 Firmen aus einer einzigen
Region. Seitdem wird der Restbedarf auf die Begriffe verteilt.
"""
from tests.test_sammeln_ziel import TABELLE, GebietsMaps, firma

from pipeline.firmen_sammeln import sammeln_bis_ziel


def test_maps_limit_wird_auf_die_suchbegriffe_verteilt():
    maps = GebietsMaps([[firma(1)]])

    sammeln_bis_ziel("", 0, ["Computer Services"], 100,
                     maps=maps, tabelle=TABELLE)

    # 10 Familien-Suchbegriffe, Ziel 100: rund 30 je Begriff (Untergrenze),
    # nicht 300 je Begriff.
    assert maps.abrufe[0]["limit"] == 30


def test_grosses_ziel_hebt_das_limit_aber_mit_deckel():
    maps = GebietsMaps([[firma(1)]])

    sammeln_bis_ziel("", 0, ["Computer Services"], 2000,
                     maps=maps, tabelle=TABELLE)

    # 2000 * 3 / 10 Begriffe = 600 -> Deckel 300 je Begriff.
    assert maps.abrufe[0]["limit"] == 300


def test_ein_einzelner_begriff_bekommt_den_vollen_bedarf():
    maps = GebietsMaps([[firma(1)]])

    sammeln_bis_ziel("", 0, ["Dachdecker"], 50, maps=maps, tabelle=TABELLE)

    assert maps.abrufe[0]["limit"] == 150      # 50 * 3 / 1 Begriff

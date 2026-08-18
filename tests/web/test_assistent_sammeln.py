"""Schritt 3: Bestand nutzen oder neu sammeln - und Schritt 4 wartet darauf.

Der Bestand deckt nur den Raum Hannover ab; für jede andere Stadt lieferte
Schritt 4 null Firmen. Seit 17.08.2026 kann man in Schritt 3 stattdessen
frisch sammeln lassen.

Sammeln kostet Geld. Deshalb ist der Bestand die Vorgabe, und nur das
genaue Wort "neu" löst eine Sammlung aus.
"""
from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from pipeline import assistent_entwurf as entwuerfe
from web.app import create_app
from web.routen import assistent as assi_routen

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


@pytest.fixture
def angemeldet(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(
        [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}],
        allow_unicode=True), encoding="utf-8")
    client = TestClient(create_app(tmp_path))
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client, tmp_path


@pytest.fixture
def gestartete_sammlungen(monkeypatch):
    """Merkt sich Sammel-Starts, statt wirklich Geld auszugeben."""
    starts = []

    def fake_starte(daten_dir, kennung, ort, radius_km, dienste, **rest):
        starts.append({"kennung": kennung, "ort": ort, "radius_km": radius_km,
                       "dienste": list(dienste)})
        return daten_dir

    monkeypatch.setattr("web.sammelmanager.starte", fake_starte)
    return starts


def _neuer_entwurf(client):
    antwort = client.get("/assistent", follow_redirects=False)
    return antwort.headers["location"].split("/")[2]


DATEN_3 = {"ort": "München", "radius_km": "25", "dienste": "Webdesigner"}


def test_schritt_3_zeigt_beide_moeglichkeiten(angemeldet):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)

    seite = client.get(f"/assistent/{kennung}/3").text

    assert 'name="firmen_quelle" value="bestand"' in seite
    assert 'name="firmen_quelle" value="neu"' in seite
    vor_neu = seite[:seite.index('value="neu"')]
    assert "checked" in vor_neu, "der Bestand muss vorausgewählt sein"


def test_ohne_wahl_wird_nicht_gesammelt(angemeldet, gestartete_sammlungen):
    client, daten_dir = angemeldet
    kennung = _neuer_entwurf(client)

    client.post(f"/assistent/{kennung}/3", data=DATEN_3, follow_redirects=False)

    assert gestartete_sammlungen == []
    assert entwuerfe.laden(daten_dir, kennung)["daten"]["firmen_quelle"] == "bestand"


def test_nur_das_wort_neu_gibt_geld_aus(angemeldet, gestartete_sammlungen):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)

    for wert in ("Neu", "NEU", "ja", "1", "sammeln"):
        client.post(f"/assistent/{kennung}/3",
                    data={**DATEN_3, "firmen_quelle": wert},
                    follow_redirects=False)

    assert gestartete_sammlungen == [], "ein verfremdeter Wert hat gesammelt"


def test_neu_startet_die_sammlung_mit_den_eingaben(angemeldet,
                                                    gestartete_sammlungen):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)

    client.post(f"/assistent/{kennung}/3",
                data={**DATEN_3, "firmen_quelle": "neu"}, follow_redirects=False)

    assert gestartete_sammlungen == [{"kennung": kennung, "ort": "München",
                                       "radius_km": 25,
                                       "dienste": ["Webdesigner"]}]


def test_ein_fehlstart_bleibt_in_schritt_3(angemeldet, monkeypatch):
    from web.sammelmanager import SammelFehler

    def kaputt(*a, **k):
        raise SammelFehler("Ohne Suchbegriffe kann nicht gesammelt werden.")

    monkeypatch.setattr("web.sammelmanager.starte", kaputt)
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)

    antwort = client.post(f"/assistent/{kennung}/3",
                          data={**DATEN_3, "firmen_quelle": "neu"})

    assert antwort.status_code == 400
    assert "Suchbegriffe" in antwort.text


# --- Schritt 4 -------------------------------------------------------------

def _stand(monkeypatch, zustand, meldung="", firmen=None):
    monkeypatch.setattr("web.sammelmanager.status",
                        lambda daten_dir, kennung: {
                            "zustand": zustand, "meldung": meldung,
                            "firmen": firmen, "ziel_ordner": "sammlung-x"})


def _bis_schritt_4(client, kennung):
    client.post(f"/assistent/{kennung}/3",
                data={**DATEN_3, "firmen_quelle": "neu"}, follow_redirects=False)
    return client.get(f"/assistent/{kennung}/4")


def test_schritt_4_wartet_solange_gesammelt_wird(angemeldet,
                                                  gestartete_sammlungen,
                                                  monkeypatch):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)
    _stand(monkeypatch, "laeuft")

    seite = _bis_schritt_4(client, kennung).text

    assert "werden gesammelt" in seite
    assert "München" in seite
    # Keine Zahlen zeigen, solange sie falsch waeren.
    assert "übernommen" not in seite


def test_fertige_sammlung_wird_gemeldet(angemeldet, gestartete_sammlungen,
                                         monkeypatch):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)
    _stand(monkeypatch, "fertig", meldung="12 Firmen gesammelt.", firmen=12)

    seite = _bis_schritt_4(client, kennung).text

    assert "12 Firmen gesammelt." in seite
    assert "werden gesammelt" not in seite


def test_gescheiterte_sammlung_zeigt_den_grund(angemeldet,
                                                gestartete_sammlungen,
                                                monkeypatch):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)
    _stand(monkeypatch, "fehler", meldung="Apify antwortet mit 402")

    seite = _bis_schritt_4(client, kennung).text

    assert "402" in seite
    # Trotzdem weiterarbeiten koennen - mit dem, was schon da ist.
    assert "vorhandenen Bestand" in seite


def test_ohne_sammlung_bleibt_schritt_4_wie_bisher(angemeldet):
    client, _ = angemeldet
    kennung = _neuer_entwurf(client)
    client.post(f"/assistent/{kennung}/3", data=DATEN_3, follow_redirects=False)

    seite = client.get(f"/assistent/{kennung}/4").text

    assert "werden gesammelt" not in seite

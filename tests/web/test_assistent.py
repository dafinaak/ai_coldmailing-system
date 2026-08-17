"""Der Kampagnen-Assistent: sechs Schritte, Entwurf auf der Platte.

Getestet wird, was der Assistent verspricht: nichts Eingetipptes geht
verloren, der Firmen-Filter antwortet sofort aus dem eigenen Bestand,
und der Assistent sendet nichts und legt nichts in Instantly an.
"""
import json

from fastapi.testclient import TestClient
from passlib.context import CryptContext
import pytest
import yaml

from web.app import create_app

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def firma(name, plz, domain, kategorien=("IT-Berater",)):
    return {"name": name, "plz": plz, "domain": domain,
            "website": f"https://{domain}", "telefon": "0511 123",
            "categories": list(kategorien)}


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(
        yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")

    quelle = tmp_path / "laeufe" / "leadquellen" / "testgebiet"
    quelle.mkdir(parents=True)
    (quelle / "firmen.json").write_text(json.dumps([
        firma("Nah IT GmbH", "30159", "nah.de"),
        firma("Weit IT GmbH", "80331", "weit.de"),
        firma("Ohne Ort IT", "", "ohneort.de"),
        firma("Blumen Meyer", "30159", "blumen.de", ["Blumenladen"]),
    ]), encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(daten_dir):
    return TestClient(create_app(daten_dir))


@pytest.fixture
def angemeldet(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    client.cookies.set("intro_gesehen", "1")
    return client


def entwurf_starten(angemeldet) -> str:
    antwort = angemeldet.get("/assistent", follow_redirects=False)
    assert antwort.status_code == 303
    return antwort.headers["location"].split("/")[2]


def schritt_1_ausfuellen(angemeldet, kennung, **abweichend):
    werte = {"name": "IT-Partner", "sprache": "de", "anzahl_leads": "50",
             "verkaeufer_url": "meine-firma.de",
             "absender_email": "ich@meine-firma.de"}
    werte.update(abweichend)
    return angemeldet.post(f"/assistent/{kennung}/1", data=werte,
                           follow_redirects=False)


def test_seite_verlangt_anmeldung(client):
    antwort = client.get("/assistent", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_kampagnenseite_fuehrt_zum_assistenten(angemeldet):
    seite = angemeldet.get("/kampagnen").text
    assert 'href="/assistent"' in seite
    assert "Add" in seite


def test_start_legt_entwurf_an_und_zeigt_schritt_1(angemeldet, daten_dir):
    kennung = entwurf_starten(angemeldet)

    assert (daten_dir / "entwuerfe" / f"{kennung}.json").exists()
    seite = angemeldet.get(f"/assistent/{kennung}/1").text
    assert "Kampagnen-Name" in seite


def test_pflichtfelder_werden_freundlich_eingefordert(angemeldet):
    kennung = entwurf_starten(angemeldet)

    antwort = schritt_1_ausfuellen(angemeldet, kennung, name="")

    assert antwort.status_code == 400
    assert "Kampagnen-Name" in antwort.text


def test_eingetipptes_ueberlebt_den_schrittwechsel(angemeldet, daten_dir):
    kennung = entwurf_starten(angemeldet)

    schritt_1_ausfuellen(angemeldet, kennung, name="IT-Partner Hannover")
    gespeichert = json.loads(
        (daten_dir / "entwuerfe" / f"{kennung}.json").read_text())

    assert gespeichert["daten"]["name"] == "IT-Partner Hannover"
    # Ohne Schema getippt, mit Schema gespeichert - sonst laedt die KI nichts.
    assert gespeichert["daten"]["verkaeufer_url"] == "https://meine-firma.de"


def test_schritt_1_fuehrt_weiter_zu_schritt_2(angemeldet):
    kennung = entwurf_starten(angemeldet)

    antwort = schritt_1_ausfuellen(angemeldet, kennung)

    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"/assistent/{kennung}/2"


def test_schritt_2_ohne_usp_wird_abgelehnt(angemeldet):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)

    antwort = angemeldet.post(f"/assistent/{kennung}/2",
                              data={"icp_firmografisch": "Handwerk"},
                              follow_redirects=False)

    assert antwort.status_code == 400
    assert "USP" in antwort.text


def test_schritt_2_speichert_usp_und_icp(angemeldet, daten_dir):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)

    angemeldet.post(f"/assistent/{kennung}/2", data={
        "usp_titel_0": "Feste Ansprechpartner", "usp_text_0": "Immer dieselbe Person.",
        "usp_titel_1": "", "usp_text_1": "wird verworfen",
        "icp_firmografisch": "Handwerk"}, follow_redirects=False)
    daten = json.loads(
        (daten_dir / "entwuerfe" / f"{kennung}.json").read_text())["daten"]

    assert [u["titel"] for u in daten["usp"]] == ["Feste Ansprechpartner"]
    assert daten["icp"]["firmografisch"] == "Handwerk"


def test_schritt_3_bietet_nur_dienste_die_es_gibt(angemeldet):
    kennung = entwurf_starten(angemeldet)

    seite = angemeldet.get(f"/assistent/{kennung}/3").text

    assert "IT-Berater" in seite
    assert "Blumenladen" in seite          # kommt im Bestand vor
    # Kein Eingabefeld fuer Dinge, die unsere Quellen nicht kennen - der
    # Text erklaert das, aber es darf nichts zum Ausfuellen dastehen.
    assert 'name="jobtitel"' not in seite
    assert 'name="seniority"' not in seite
    assert 'name="technologien"' not in seite


def test_schritt_4_findet_nahe_firmen_und_laesst_ferne_weg(angemeldet):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)
    angemeldet.post(f"/assistent/{kennung}/3",
                    data={"ort": "Hannover", "radius_km": "40",
                          "dienste": "IT-Berater"}, follow_redirects=False)

    seite = angemeldet.get(f"/assistent/{kennung}/4").text

    assert "Nah IT GmbH" in seite
    assert "Weit IT GmbH" not in seite
    assert "Blumen Meyer" not in seite


def test_schritt_4_verschweigt_firmen_ohne_ort_nicht(angemeldet):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)
    angemeldet.post(f"/assistent/{kennung}/3",
                    data={"ort": "Hannover", "radius_km": "40",
                          "dienste": "IT-Berater"}, follow_redirects=False)

    seite = angemeldet.get(f"/assistent/{kennung}/4").text

    assert "Postleitzahl fehlt" in seite


def test_schritt_4_sagt_was_der_naechste_klick_kostet(angemeldet):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)
    angemeldet.post(f"/assistent/{kennung}/3",
                    data={"ort": "Hannover", "radius_km": "40",
                          "dienste": "IT-Berater"}, follow_redirects=False)

    seite = angemeldet.get(f"/assistent/{kennung}/4").text

    assert "Credits" in seite
    # Ohne je gesehene Zahl wird keine erfunden.
    assert "noch nicht bekannt" in seite


def test_schritt_4_zeigt_den_gemerkten_guthabenstand(angemeldet, daten_dir):
    from pipeline.guthaben import merken

    merken(187, daten_dir)
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)
    angemeldet.post(f"/assistent/{kennung}/3",
                    data={"ort": "Hannover", "radius_km": "40",
                          "dienste": "IT-Berater"}, follow_redirects=False)

    seite = angemeldet.get(f"/assistent/{kennung}/4").text

    assert "187 Credits" in seite
    assert "Stand" in seite          # nie ohne Zeitpunkt


def test_zu_wenig_guthaben_wird_vorher_gesagt(angemeldet, daten_dir):
    from pipeline.guthaben import merken

    merken(0, daten_dir)
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)
    angemeldet.post(f"/assistent/{kennung}/3",
                    data={"ort": "Hannover", "radius_km": "40",
                          "dienste": "IT-Berater"}, follow_redirects=False)

    seite = angemeldet.get(f"/assistent/{kennung}/4").text

    assert "reicht nicht für alle" in seite


def test_unbekannter_ort_fuehrt_zurueck_zum_filter(angemeldet):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)
    angemeldet.post(f"/assistent/{kennung}/3",
                    data={"ort": "Gibtsnichthausen", "radius_km": "40"},
                    follow_redirects=False)

    antwort = angemeldet.get(f"/assistent/{kennung}/4")

    assert antwort.status_code == 400
    assert "nicht gefunden" in antwort.text


def test_schritt_5_verlangt_ein_absender_postfach(angemeldet):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)

    antwort = angemeldet.post(f"/assistent/{kennung}/5",
                              data={"versand_postfach": "", "tageslimit": "20"},
                              follow_redirects=False)

    assert antwort.status_code == 400
    assert "Postfach" in antwort.text


def test_schritt_5_speichert_die_versand_einstellungen(angemeldet, daten_dir):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)

    angemeldet.post(f"/assistent/{kennung}/5", data={
        "versand_postfach": "ich@meine-firma.de", "tageslimit": "25",
        "zeit_von": "09:00", "zeit_bis": "17:00", "tag_mo": "1", "tag_di": "1",
        "abstand_1_2": "5", "abstand_2_3": "9", "signatur": "Viele Grüße"},
        follow_redirects=False)
    daten = json.loads(
        (daten_dir / "entwuerfe" / f"{kennung}.json").read_text())["daten"]

    assert daten["tageslimit"] == 25
    assert daten["wochentage"] == ["mo", "di"]
    assert daten["abstand_2_3"] == 9


def test_unsinnige_zahlen_werden_eingefangen(angemeldet, daten_dir):
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)

    angemeldet.post(f"/assistent/{kennung}/5", data={
        "versand_postfach": "ich@meine-firma.de", "tageslimit": "99999",
        "abstand_1_2": "abc"}, follow_redirects=False)
    daten = json.loads(
        (daten_dir / "entwuerfe" / f"{kennung}.json").read_text())["daten"]

    assert daten["tageslimit"] == 500
    assert daten["abstand_1_2"] == 7


def test_verworfener_entwurf_ist_weg(angemeldet, daten_dir):
    kennung = entwurf_starten(angemeldet)

    angemeldet.post(f"/assistent/{kennung}/abbrechen", follow_redirects=False)

    assert not (daten_dir / "entwuerfe" / f"{kennung}.json").exists()


def test_verschwundener_entwurf_startet_neu_statt_zu_scheitern(angemeldet):
    antwort = angemeldet.get("/assistent/gibtsnicht/1", follow_redirects=False)

    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/assistent"


def test_der_assistent_sendet_nichts(angemeldet):
    # Schritt 6 fasst nur zusammen: kein Versand, keine Instantly-Kampagne.
    kennung = entwurf_starten(angemeldet)
    schritt_1_ausfuellen(angemeldet, kennung)

    seite = angemeldet.get(f"/assistent/{kennung}/6").text

    assert "sendet nichts" in seite
    assert "Freigabe" in seite

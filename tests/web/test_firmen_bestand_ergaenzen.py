"""Eine neue Sammlung soll den Bestand auffrischen, nicht nur vergroessern.

Gewuenscht am 17.08.2026: "vetem me i shtu edhe te rejat aty me u bo
update". Vorher gewann beim Zusammenfuehren schlicht der erste Fund - fand
eine spaetere Sammlung die inzwischen umgezogene Webseite oder die
fehlende Telefonnummer einer bekannten Firma, flog sie weg.

Die aeltere Sammeldatei wird dabei NIE ueberschrieben: sie haelt 1.481
Firmen und rund sieben Dollar Sammelkosten. Zusammengefuehrt wird erst
beim Lesen.
"""
import json

from web.routen.assistent import _firmen_bestand


def _sammlung(daten_dir, name, firmen):
    ordner = daten_dir / "laeufe" / "leadquellen" / name
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "firmen.json").write_text(json.dumps(firmen), encoding="utf-8")


def test_fehlende_felder_werden_nachgetragen(tmp_path):
    _sammlung(tmp_path, "a-alt", [{"name": "Firma", "domain": "firma.de",
                                    "plz": "30159", "telefon": ""}])
    _sammlung(tmp_path, "b-neu", [{"name": "Firma", "domain": "firma.de",
                                    "telefon": "+49 511 1", "ort": "Hannover"}])

    firma, = _firmen_bestand(tmp_path)

    assert firma["telefon"] == "+49 511 1"
    assert firma["ort"] == "Hannover"
    assert firma["plz"] == "30159"        # aus der aelteren Sammlung


def test_gefuellte_felder_bleiben_unangetastet(tmp_path):
    # Ergaenzen, nicht ueberschreiben: was schon dasteht, gilt.
    _sammlung(tmp_path, "a-alt", [{"name": "Firma", "domain": "firma.de",
                                    "telefon": "+49 511 ALT"}])
    _sammlung(tmp_path, "b-neu", [{"name": "Firma", "domain": "firma.de",
                                    "telefon": "+49 511 NEU"}])

    firma, = _firmen_bestand(tmp_path)

    assert firma["telefon"] == "+49 511 ALT"


def test_die_firma_steht_nur_einmal_im_bestand(tmp_path):
    _sammlung(tmp_path, "a-alt", [{"name": "Firma", "domain": "firma.de"}])
    _sammlung(tmp_path, "b-neu", [{"name": "Firma", "domain": "firma.de"}])

    assert len(_firmen_bestand(tmp_path)) == 1


def test_neue_firmen_kommen_dazu(tmp_path):
    _sammlung(tmp_path, "a-alt", [{"name": "Alt", "domain": "alt.de"}])
    _sammlung(tmp_path, "b-neu", [{"name": "Neu", "domain": "neu.de"}])

    assert {f["domain"] for f in _firmen_bestand(tmp_path)} == {"alt.de", "neu.de"}


def test_kategorien_und_quellen_werden_gesammelt(tmp_path):
    _sammlung(tmp_path, "a-alt", [{"name": "Firma", "domain": "firma.de",
                                    "categories": ["IT"], "quelle": "maps"}])
    _sammlung(tmp_path, "b-neu", [{"name": "Firma", "domain": "firma.de",
                                    "categories": ["Webdesign"],
                                    "quellen": ["gelbe_seiten"]}])

    firma, = _firmen_bestand(tmp_path)

    assert sorted(firma["categories"]) == ["IT", "Webdesign"]
    assert sorted(firma["quellen"]) == ["gelbe_seiten", "maps"]


def test_die_sammeldatei_wird_nicht_veraendert(tmp_path):
    # Zusammengefuehrt wird nur im Speicher - die Datei auf der Platte
    # bleibt, wie sie ist.
    alt = [{"name": "Firma", "domain": "firma.de", "telefon": ""}]
    _sammlung(tmp_path, "a-alt", alt)
    _sammlung(tmp_path, "b-neu", [{"name": "Firma", "domain": "firma.de",
                                    "telefon": "+49 511 1"}])

    _firmen_bestand(tmp_path)

    pfad = tmp_path / "laeufe" / "leadquellen" / "a-alt" / "firmen.json"
    assert json.loads(pfad.read_text(encoding="utf-8")) == alt


def test_kaputte_datei_haelt_den_bestand_nicht_auf(tmp_path):
    ordner = tmp_path / "laeufe" / "leadquellen" / "kaputt"
    ordner.mkdir(parents=True)
    (ordner / "firmen.json").write_text("{kein json", encoding="utf-8")
    _sammlung(tmp_path, "gut", [{"name": "Firma", "domain": "firma.de"}])

    assert len(_firmen_bestand(tmp_path)) == 1

"""Olivers Feld "CEO/Inhaber" - gefuellt aus dem, was schon dasteht.

Vor dem 28.08.2026 war das Feld zu 91% leer, weil nur ein selten
gesetztes Extra-Feld gelesen wurde. Die Angabe steckt aber meistens in
den Entscheidern selbst. Erfunden wird nichts: ohne Fuehrungsrolle im
Impressum bleibt das Feld leer.
"""
import json
import sqlite3

from pipeline.master_db import DB_NAME, _ceo_owner, bauen


def _bauen(tmp_path, firmen):
    ziel = tmp_path / "laeufe" / "leadquellen" / "lauf1"
    ziel.mkdir(parents=True)
    (ziel / "firmen.json").write_text(json.dumps(firmen, ensure_ascii=False),
                                      encoding="utf-8")
    bauen(str(tmp_path))
    db = sqlite3.connect(tmp_path / DB_NAME)
    return dict(db.execute("SELECT domain, ceo_owner FROM companies"))


def test_geschaeftsfuehrer_wird_uebernommen():
    personen = [{"name": "Anna Meier", "rolle": "Geschäftsführerin"}]
    assert _ceo_owner({}, personen) == "Anna Meier - Geschäftsführerin"


def test_inhaber_wird_uebernommen():
    personen = [{"name": "Bernd Klein", "rolle": "Inhaber"}]
    assert _ceo_owner({}, personen) == "Bernd Klein - Inhaber"


def test_ohne_fuehrungsrolle_bleibt_leer():
    """Ein Vertriebsmitarbeiter ist nicht der Inhaber."""
    personen = [{"name": "Carla Weber", "rolle": "Vertrieb"}]
    assert _ceo_owner({}, personen) == ""


def test_abteilungsleiter_ist_nicht_der_inhaber():
    """Die Grenze sitzt bewusst zwischen Gruender und Leiter: ein
    Abteilungsleiter ist Entscheider, aber nicht Inhaber der Firma."""
    assert _ceo_owner({}, [{"name": "Ida Leit", "rolle": "Leiterin IT"}]) == ""
    assert _ceo_owner({}, [{"name": "Jan Prok", "rolle": "Prokurist"}]) == ""


def test_gruenderin_zaehlt_noch_dazu():
    assert _ceo_owner({}, [{"name": "Kim Start", "rolle": "Gründerin"}]) \
        == "Kim Start - Gründerin"


def test_person_ohne_rolle_bleibt_leer():
    assert _ceo_owner({}, [{"name": "Dirk Ohne", "rolle": ""}]) == ""


def test_vorstand_einer_ag_ist_chef():
    """Der Vorstand leitet eine AG/SE. In der Rollen-Tabelle steht er in
    derselben Gruppe wie "Leiter", faellt also sonst faelschlich raus."""
    assert _ceo_owner({}, [{"name": "Klemens B.", "rolle": "Vorstand"}]) \
        == "Klemens B. - Vorstand"
    assert _ceo_owner({}, [{"name": "Michael R.",
                            "rolle": "Vorstandvorsitzender"}]) \
        == "Michael R. - Vorstandvorsitzender"


def test_aufsichtsrat_ist_kein_chef():
    """Der Aufsichtsrat kontrolliert die Leitung, er ist sie nicht."""
    assert _ceo_owner({}, [{"name": "Otto A.",
                            "rolle": "Aufsichtsratvorsitzender"}]) == ""


def test_vertreten_durch_ist_keine_position():
    """"Vertreten durch: X" benennt den gesetzlichen Vertreter - also die
    Geschaeftsfuehrung. Die Person zaehlt, die Formel ist aber kein Titel
    und wird nicht als Position ausgegeben."""
    assert _ceo_owner({}, [{"name": "Sören Korf",
                            "rolle": "Vertreten durch"}]) == "Sören Korf"


def test_inhaltlich_verantwortlich_ist_kein_chefbeleg():
    """Wer nach §55 RStV fuer den Webseiten-Inhalt zustaendig ist, kann
    jede beliebige Person im Haus sein - kein Beleg fuer Fuehrung."""
    assert _ceo_owner({}, [{"name": "Nina Web",
                            "rolle": "Inhaltlich verantwortlich"}]) == ""


def test_vertreten_durch_auch_im_vorrang_feld():
    """Der Weg ueber 'entscheider_primaer' umging die Pruefung frueher
    ganz - 201 Firmen trugen dadurch 'Vertreten durch' als Position."""
    firma = {"entscheider_primaer": {"name": "Markus Lee",
                                     "rolle": "Vertreten durch"}}
    assert _ceo_owner(firma, []) == "Markus Lee"


def test_aufsichtsrat_im_vorrang_feld_wird_uebersprungen():
    firma = {"entscheider_primaer": {"name": "Otto A.",
                                     "rolle": "Aufsichtsrat"}}
    personen = [{"name": "Rita Chef", "rolle": "Geschäftsführerin"}]
    assert _ceo_owner(firma, personen) == "Rita Chef - Geschäftsführerin"


def test_vorhandenes_feld_hat_vorrang():
    """Steht die Angabe schon ausdruecklich da, wird sie nicht ueberstimmt."""
    firma = {"entscheider_primaer": {"name": "Eva Alt", "rolle": "Inhaberin"}}
    personen = [{"name": "Frank Neu", "rolle": "Geschäftsführer"}]
    assert _ceo_owner(firma, personen) == "Eva Alt - Inhaberin"


def test_erster_chef_gewinnt_bei_mehreren():
    personen = [{"name": "Gerd Erst", "rolle": "Geschäftsführer"},
                {"name": "Hans Zweit", "rolle": "Geschäftsführer"}]
    assert _ceo_owner({}, personen).startswith("Gerd Erst")


def test_in_der_datenbank(tmp_path):
    laender = _bauen(tmp_path, [
        {"name": "Chef GmbH", "domain": "chef.de", "plz": "34117",
         "entscheider": [{"name": "Anna Meier", "vorname": "Anna",
                          "nachname": "Meier", "rolle": "Geschäftsführerin"}]},
        {"name": "Kein Chef GmbH", "domain": "keinchef.de", "plz": "34117",
         "entscheider": [{"name": "Carla Weber", "vorname": "Carla",
                          "nachname": "Weber", "rolle": "Vertrieb"}]},
    ])
    assert laender["chef.de"] == "Anna Meier - Geschäftsführerin"
    assert laender["keinchef.de"] == ""

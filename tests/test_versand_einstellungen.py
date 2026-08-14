"""Die Versand-Einstellungen aus Schritt 5 muessen bei Instantly ankommen.

Gefunden am 14.08.2026 an einer echten Probe: Das Formular fragte nach
Postfach, Tageslimit, Zeitfenster und Wochentagen - und KEINE dieser
Antworten kam an. Die Kampagne wurde ohne Absender-Postfach angelegt
(email_list fehlte komplett), mit fest eingebautem Zeitplan. Eine so
uebergebene Kampagne kann nicht senden.

Ausserdem: der Test-Empfaenger-Schutz galt IMMER, also konnte eine im
Formular gebaute Kampagne nie an echte Empfaenger uebergeben werden.
"""
import json

import pytest
import yaml

from pipeline.config import Kunde, load_kunde
from pipeline.senders.instantly import InstantlySender


class FakeAntwort:
    def __init__(self, daten):
        self._daten = daten
        self.status_code = 200

    def json(self):
        return self._daten

    def raise_for_status(self):
        pass


class FakeSession:
    """Merkt sich, was an Instantly geschickt wurde."""

    def __init__(self):
        self.aufrufe = []

    def post(self, url, headers=None, json=None, timeout=None):
        self.aufrufe.append({"url": url, "payload": json})
        return FakeAntwort({"id": "kampagne-1"})


def _kunde(**abweichungen) -> Kunde:
    grund = {
        "name": "Probe GmbH", "zielgruppe": {}, "angebot": "A",
        "tonalitaet": "ruhig", "absender": "Oliver Redschlag",
        "follow_up_tage": [7, 14], "test_empfaenger": ["ich@example.com"],
    }
    grund.update(abweichungen)
    return Kunde(**grund)


def _kampagne(session):
    return session.aufrufe[0]["payload"]


def test_absender_postfach_landet_in_der_kampagne():
    session = FakeSession()
    InstantlySender("key", session=session).create_campaign(
        _kunde(versand_postfach="post@example.com"))

    assert _kampagne(session)["email_list"] == ["post@example.com"]


def test_ohne_postfach_bleibt_email_list_weg():
    # Lieber gar kein Feld als ein leeres - so bleibt das alte Verhalten
    # fuer Kundendateien, die kein Postfach nennen.
    session = FakeSession()
    InstantlySender("key", session=session).create_campaign(_kunde())

    assert "email_list" not in _kampagne(session)


def test_tageslimit_und_zeitfenster_kommen_aus_der_kundendatei():
    session = FakeSession()
    InstantlySender("key", session=session).create_campaign(
        _kunde(tageslimit=35, zeit_von="09:30", zeit_bis="17:00"))

    kampagne = _kampagne(session)
    zeitplan = kampagne["campaign_schedule"]["schedules"][0]
    assert kampagne["daily_limit"] == 35
    assert zeitplan["timing"] == {"from": "09:30", "to": "17:00"}


def test_wochentage_werden_auf_die_instantly_nummern_uebersetzt():
    session = FakeSession()
    InstantlySender("key", session=session).create_campaign(
        _kunde(wochentage=["mo", "mi", "sa"]))

    tage = _kampagne(session)["campaign_schedule"]["schedules"][0]["days"]
    # 0=So 1=Mo 2=Di 3=Mi 4=Do 5=Fr 6=Sa
    assert tage == {"0": False, "1": True, "2": False, "3": True,
                    "4": False, "5": False, "6": True}


def test_ausdrueckliche_absender_gewinnen_ueber_die_kundendatei():
    session = FakeSession()
    InstantlySender("key", session=session).create_campaign(
        _kunde(versand_postfach="aus-datei@example.com"),
        absender_emails=["ausdruecklich@example.com"])

    assert _kampagne(session)["email_list"] == ["ausdruecklich@example.com"]


# --- Kundendatei ----------------------------------------------------------

def _schreibe(tmp_path, **felder):
    inhalt = {
        "name": "Probe", "zielgruppe": {"titel": ["Geschäftsführer"]},
        "angebot": "A", "tonalitaet": "ruhig", "absender": "Oliver",
        "follow_up_tage": [7, 14], "test_empfaenger": ["ich@example.com"],
    }
    inhalt.update(felder)
    pfad = tmp_path / "kunde.yaml"
    pfad.write_text(yaml.safe_dump(inhalt, allow_unicode=True), encoding="utf-8")
    return pfad


def test_alte_kundendatei_bleibt_auf_probe_versand(tmp_path):
    # WICHTIG: Das blosse Vorhandensein dieses Codes darf keine bestehende
    # Kampagne scharf machen.
    kunde = load_kunde(_schreibe(tmp_path))

    assert kunde.versand_modus == "test"
    assert kunde.tageslimit == 20
    assert kunde.wochentage == ["mo", "di", "mi", "do", "fr"]


def test_echt_modus_wird_gelesen(tmp_path):
    kunde = load_kunde(_schreibe(tmp_path, versand_modus="echt"))

    assert kunde.versand_modus == "echt"


def test_unbekannter_modus_gibt_klaren_fehler(tmp_path):
    with pytest.raises(ValueError, match="versand_modus"):
        load_kunde(_schreibe(tmp_path, versand_modus="vielleicht"))


def test_unbekannter_wochentag_gibt_klaren_fehler(tmp_path):
    with pytest.raises(ValueError, match="wochentage"):
        load_kunde(_schreibe(tmp_path, wochentage=["mo", "montag"]))


# --- der Schutz vor fremden Empfaengern -----------------------------------

_TEXTE = [{"email": "fremd@echt.de", "betreff": "B", "mail_1": "M",
           "follow_up_1": "F", "follow_up_2": "F"}]


class MitschreibenderSender:
    def __init__(self):
        self.namen = []

    def create_campaign(self, kunde, name=None, absender_emails=None,
                         betreffs=None):
        self.namen.append(name or kunde.name)
        return "camp-1"

    def import_leads(self, campaign_id, texte_pro_lead):
        pass


def _lauf(tmp_path, kunde_datei):
    from pipeline.approval import approve
    from pipeline.run_store import RunStore

    store = RunStore(tmp_path, "Probe")
    store.save_step("kunde_pfad", {"pfad": str(kunde_datei)})
    store.save_step("pruefung_ok", _TEXTE)
    approve(store)
    return store


def test_probe_modus_haelt_fremde_empfaenger_auf(tmp_path):
    from pipeline.__main__ import SendenFehler, _versand_ausfuehren

    store = _lauf(tmp_path, _schreibe(tmp_path))

    with pytest.raises(SendenFehler, match="Test-Empfänger"):
        _versand_ausfuehren(store, MitschreibenderSender())


def test_echt_modus_laesst_die_gefundenen_empfaenger_durch(tmp_path):
    from pipeline.__main__ import _versand_ausfuehren

    store = _lauf(tmp_path, _schreibe(tmp_path, versand_modus="echt"))
    sender = MitschreibenderSender()

    _versand_ausfuehren(store, sender)

    # Ohne [TEST]-Vorsilbe: das ist eine echte Kampagne.
    assert sender.namen == ["Probe"]


def test_probe_modus_traegt_die_test_vorsilbe(tmp_path):
    from pipeline.__main__ import _versand_ausfuehren

    # Empfaenger steht in der Testliste, der Versand geht also durch.
    kunde_datei = _schreibe(tmp_path, test_empfaenger=["fremd@echt.de"])
    store = _lauf(tmp_path, kunde_datei)
    sender = MitschreibenderSender()

    _versand_ausfuehren(store, sender)

    assert sender.namen == ["[TEST] Probe"]


def test_versand_einstellungen_werden_gelesen(tmp_path):
    kunde = load_kunde(_schreibe(
        tmp_path, versand_postfach="post@example.com", tageslimit=42,
        zeit_von="07:00", zeit_bis="21:00", wochentage=["mo", "fr"],
        signatur="Oliver Redschlag\nPolePosition"))

    assert kunde.versand_postfach == "post@example.com"
    assert kunde.tageslimit == 42
    assert (kunde.zeit_von, kunde.zeit_bis) == ("07:00", "21:00")
    assert kunde.wochentage == ["mo", "fr"]
    assert "PolePosition" in kunde.signatur

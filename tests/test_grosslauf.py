import pytest
from pipeline.grosslauf import (lauf_ausfuehren, zusammenfassung,
                                bericht_markdown, dubletten_finden,
                                lauf_speichern, lauf_laden)
from tests.test_sourcing import (_FakeProspeo, _FakeDropcontact, _FakeImpressum,
                                 _FakeHunterMitPruefer, _kunde, _prospeo_person)


def firma(name, domain, telefon="0511 123", **extra):
    return {"name": name, "website": f"https://{domain}" if domain else "",
            "domain": domain, "address": "", "categories": [],
            "plz": extra.pop("plz", "30159"), "telefon": telefon,
            "gf_name_liste": "", "ausserhalb_region": False, **extra}


def _quellen_fuer_lauf():
    prospeo = _FakeProspeo(
        personen_je_domain={"a.de": [_prospeo_person()]},
        mail_je_person_id={"p-1": {"email": "paula.prosp@a.de", "status": "VERIFIED",
                                   "verification_method": "SMTP", "schon_bezahlt": False}})
    impressum = _FakeImpressum(
        texte={"https://b.de": "Impressum ..."},
        ergebnisse={"b.de": {"personen": [{"vorname": "Ben", "nachname": "Berg"}],
                             "mail_domain": None}})
    dropcontact = _FakeDropcontact({"Ben": "ben.berg@b.de"})
    return prospeo, dropcontact, impressum


def _kunde_grosslauf():
    return _kunde(anbieter_reihenfolge=["prospeo", "impressum"])


def _drei_firmen():
    # a: Prospeo trifft. b: Impressum rettet. c: nichts -> nur die
    # Sammeladresse bleibt gespeichert (Kampagnen-Regel 20.08.2026).
    return [firma("Alpha GmbH", "a.de"),
            firma("Beta GmbH", "b.de"),
            firma("Gamma GmbH", "c.de", telefon="0511 999",
                  ausserhalb_region=True, plz="10557")]


def test_lauf_fuehrt_kaskade_je_firma_aus():
    ergebnisse = lauf_ausfuehren(_drei_firmen(), _kunde_grosslauf(),
                                 *_quellen_fuer_lauf(),
                                 fortschritt=lambda t: None)
    assert [e["ausgang"] for e in ergebnisse] == \
        ["mit_entscheider", "mit_entscheider", "ohne_persoenliche_mail"]
    assert [e.get("stufe") for e in ergebnisse] == ["prospeo", "impressum", None]
    assert ergebnisse[0]["leads"][0]["email"] == "paula.prosp@a.de"
    # Zusatzfelder der Liste bleiben am Ergebnis erhalten (Telefon fuer Oliver):
    assert ergebnisse[2]["telefon"] == "0511 999"


def test_zusammenfassung_und_bericht_im_oliver_format():
    ergebnisse = lauf_ausfuehren(_drei_firmen(), _kunde_grosslauf(),
                                 *_quellen_fuer_lauf(),
                                 fortschritt=lambda t: None)
    z = zusammenfassung(ergebnisse)
    assert z["firmen_gesamt"] == 3 and z["persoenliche_mail"] == 2
    assert z["quote_prozent"] == 66.7
    assert z["je_stufe"] == {"prospeo": 1, "impressum": 1}
    assert z["info_ungeprueft"] == 1 and z["ausserhalb_region"] == 1
    text = bericht_markdown(ergebnisse, z, [])
    # Olivers bestellte Bestandteile:
    assert "66.7" in text
    assert "Gamma GmbH" in text and "0511 999" in text      # Restliste + Telefon
    assert "außerhalb der Region" in text                    # nicht vergessen
    assert "ungeprüft" in text                               # info@-Kennzeichnung


def test_lauf_prueft_info_adressen_mit_hunter():
    # Bauplan Versandstart 2026-07-28, Schritt 1: Mit Hunter-Quelle wird die
    # info@-Rueckfalladresse VOR der Aufnahme geprueft statt ungeprueft
    # uebernommen.
    hunter = _FakeHunterMitPruefer({}, {"info@c.de": "valid"})
    ergebnisse = lauf_ausfuehren(_drei_firmen(), _kunde_grosslauf(),
                                 *_quellen_fuer_lauf(), hunter=hunter,
                                 fortschritt=lambda t: None)
    assert hunter.geprueft == ["info@c.de"]
    # Geprueft und gespeichert - Empfaenger wird sie trotzdem nie.
    assert ergebnisse[2]["ausgang"] == "ohne_persoenliche_mail"
    assert ergebnisse[2]["info_pruefstatus"] == "valid"
    assert ergebnisse[2]["leads"] == []


def test_lauf_verwirft_ungueltige_info_adressen():
    hunter = _FakeHunterMitPruefer({}, {"info@c.de": "invalid"})
    ergebnisse = lauf_ausfuehren(_drei_firmen(), _kunde_grosslauf(),
                                 *_quellen_fuer_lauf(), hunter=hunter,
                                 fortschritt=lambda t: None)
    assert ergebnisse[2]["ausgang"] == "info_ungueltig"
    assert ergebnisse[2]["leads"] == []


def test_lauf_setzt_fort_ohne_neue_abfragen(tmp_path):
    prospeo, dropcontact, impressum = _quellen_fuer_lauf()
    ergebnisse = lauf_ausfuehren(_drei_firmen(), _kunde_grosslauf(),
                                 prospeo, dropcontact, impressum,
                                 fortschritt=lambda t: None)
    lauf_speichern(tmp_path, ergebnisse, [])
    geladen = lauf_laden(tmp_path)
    assert len(geladen) == 3
    # Zweiter Lauf: Quellen wuerden bei erneuter Abfrage scheitern -> es darf
    # keine einzige neue Anbieter-Abfrage geben.
    class _Explodiert:
        def __getattr__(self, name):
            raise AssertionError("darf nicht erneut abgefragt werden")
    neu = lauf_ausfuehren(_drei_firmen(), _kunde_grosslauf(),
                          _Explodiert(), _Explodiert(), _Explodiert(),
                          vorhandene=geladen, fortschritt=lambda t: None)
    assert [e["ausgang"] for e in neu] == \
        ["mit_entscheider", "mit_entscheider", "ohne_persoenliche_mail"]


def test_dubletten_ueber_domain_und_namenskern():
    firmen = [firma("Bechtle IT-Systemhaus Hannover", "bechtle.com"),
              firma("Bechtle IT-Systemhaus Braunschweig", "bechtle-bs.de"),
              firma("Alpha GmbH", "a.de"),
              firma("Alpha IT Service", "a.de")]
    gruppen = dubletten_finden(firmen)
    assert len(gruppen) == 2
    domains = [sorted(m["domain"] for m in g) for g in gruppen]
    assert ["a.de", "a.de"] in domains                       # gleiche Domain
    assert ["bechtle-bs.de", "bechtle.com"] in domains       # gleicher Namenskern

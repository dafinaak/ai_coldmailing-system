import json
import pytest
from pipeline.vergleich import (weg_a_pruefen, weg_b_pruefen, vergleich_ausfuehren,
                               zusammenfassung, bericht_markdown, lauf_speichern,
                               lauf_laden, STANDARD_ROLLEN)


# --- Fakes: gleiche Schnittstellen wie die echten Quellen, ohne Netz ---

class FakeProspeo:
    def __init__(self, personen=None, anreicherungen=None, fehler=None):
        self.personen = personen or {}
        self.anreicherungen = anreicherungen or {}
        self.fehler = fehler
        self.such_domains, self.angereichert = [], []
    def entscheider_finden(self, domain):
        if self.fehler:
            raise RuntimeError(self.fehler)
        self.such_domains.append(domain)
        return self.personen.get(domain, [])
    def email_anreichern(self, person_id):
        self.angereichert.append(person_id)
        return self.anreicherungen.get(person_id)


class FakeHunter:
    def __init__(self, personen=None, fehler=None):
        self.personen, self.fehler = personen or {}, fehler
    def entscheider_finden(self, domain):
        if self.fehler:
            raise RuntimeError(self.fehler)
        return self.personen.get(domain, [])


class FakeDropcontact:
    def __init__(self, mails=None):
        self.mails = mails or {}
    def email_bauen(self, first_name, last_name, website, company=""):
        return self.mails.get((first_name, last_name))


def firma(name="Firma GmbH", domain="firma.de"):
    return {"name": name, "domain": domain,
            "website": f"https://{domain}" if domain else "",
            "address": "Teststr. 1, Hannover", "categories": ["IT"]}


def prospeo_person(pid="p-1", first="Anna", last="Muster",
                   titel="Geschäftsführerin", seniority="Founder/Owner"):
    return {"person_id": pid, "first_name": first, "last_name": last,
            "title": titel, "seniority": seniority}


def hunter_person(first="Anna", last="Muster", titel="Geschäftsführerin",
                  email="anna@firma.de", status="valid", decision_maker=True):
    return {"first_name": first, "last_name": last, "title": titel,
            "email": email, "confidence": 90, "decision_maker": decision_maker,
            "verification_status": status}


# --- Weg A (Prospeo) ---

def test_weg_a_gepruefte_mail():
    prospeo = FakeProspeo(
        personen={"firma.de": [prospeo_person()]},
        anreicherungen={"p-1": {"email": "anna.muster@firma.de", "status": "VERIFIED",
                                "verification_method": "SMTP", "schon_bezahlt": False}})
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, prospeo)
    assert e["status"] == "gepruefte_mail"
    assert e["person"] == {"vorname": "Anna", "nachname": "Muster",
                           "titel": "Geschäftsführerin"}
    assert e["email"] == "anna.muster@firma.de" and e["email_geprueft"] is True
    assert e["pruefweg"] == "prospeo:SMTP"
    assert e["domain_passt"] is True
    assert e["fehler"] is None


def test_weg_a_person_ohne_gepruefte_mail():
    prospeo = FakeProspeo(personen={"firma.de": [prospeo_person()]})
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, prospeo)
    assert e["status"] == "person_ohne_gepruefte_mail"
    assert e["person"]["nachname"] == "Muster" and e["email"] is None


def test_weg_a_seniority_qualifiziert_auch_ohne_titel_treffer():
    # Prospeo kennt keinen decision_maker-Schalter wie Hunter; die Seniority
    # "Founder/Owner" muss deshalb als Entscheider-Merkmal zaehlen.
    inhaber = prospeo_person(titel="Bäckermeister", seniority="Founder/Owner")
    prospeo = FakeProspeo(personen={"firma.de": [inhaber]},
                          anreicherungen={"p-1": {"email": "a.m@firma.de",
                                                  "status": "VERIFIED",
                                                  "verification_method": "SMTP",
                                                  "schon_bezahlt": False}})
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, prospeo)
    assert e["status"] == "gepruefte_mail"


def test_weg_a_kein_entscheider_bei_nur_unpassenden_personen():
    azubi = prospeo_person(titel="Auszubildender", seniority="Entry")
    prospeo = FakeProspeo(personen={"firma.de": [azubi]})
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, prospeo)
    assert e["status"] == "kein_entscheider" and prospeo.angereichert == []


def test_weg_a_kein_treffer_und_keine_webseite():
    assert weg_a_pruefen(firma(), STANDARD_ROLLEN, FakeProspeo())["status"] == "kein_treffer"
    e = weg_a_pruefen(firma(domain=""), STANDARD_ROLLEN, FakeProspeo())
    assert e["status"] == "keine_webseite"


def test_weg_a_fehler_wird_gefangen():
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, FakeProspeo(fehler="Prospeo 500"))
    assert e["status"] == "fehler" and "Prospeo 500" in e["fehler"]


def test_weg_a_probiert_naechste_person_wenn_erste_ohne_mail():
    p1 = prospeo_person(pid="p-1")
    p2 = prospeo_person(pid="p-2", first="Ben", last="Berg", titel="Inhaber")
    prospeo = FakeProspeo(
        personen={"firma.de": [p1, p2]},
        anreicherungen={"p-2": {"email": "ben.berg@firma.de", "status": "VERIFIED",
                                "verification_method": "SMTP", "schon_bezahlt": False}})
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, prospeo)
    assert e["status"] == "gepruefte_mail" and e["email"] == "ben.berg@firma.de"
    assert prospeo.angereichert == ["p-1", "p-2"]


def test_weg_a_fremde_domain_wird_markiert():
    prospeo = FakeProspeo(
        personen={"firma.de": [prospeo_person()]},
        anreicherungen={"p-1": {"email": "anna@andere-firma.de", "status": "VERIFIED",
                                "verification_method": "SMTP", "schon_bezahlt": False}})
    e = weg_a_pruefen(firma(), STANDARD_ROLLEN, prospeo)
    assert e["domain_passt"] is False


# --- Weg B (Hunter -> Dropcontact) ---

def test_weg_b_gepruefte_mail_ueber_dropcontact():
    hunter = FakeHunter(personen={"firma.de": [hunter_person()]})
    dropcontact = FakeDropcontact(mails={("Anna", "Muster"): {
        "email": "anna.muster@firma.de", "qualification": "nominative@pro"}})
    e = weg_b_pruefen(firma(), STANDARD_ROLLEN, hunter, dropcontact)
    assert e["status"] == "gepruefte_mail"
    assert e["email"] == "anna.muster@firma.de" and e["email_geprueft"] is True
    assert e["pruefweg"] == "dropcontact:nominative@pro"
    assert e["domain_passt"] is True


def test_weg_b_faellt_auf_hunter_valid_zurueck():
    hunter = FakeHunter(personen={"firma.de": [hunter_person()]})
    e = weg_b_pruefen(firma(), STANDARD_ROLLEN, hunter, FakeDropcontact())
    assert e["status"] == "gepruefte_mail"
    assert e["email"] == "anna@firma.de" and e["pruefweg"] == "hunter:valid"


def test_weg_b_person_ohne_gepruefte_mail():
    person = hunter_person(status="accept_all")
    hunter = FakeHunter(personen={"firma.de": [person]})
    e = weg_b_pruefen(firma(), STANDARD_ROLLEN, hunter, FakeDropcontact())
    assert e["status"] == "person_ohne_gepruefte_mail"
    assert e["person"]["vorname"] == "Anna" and e["email"] is None


def test_weg_b_statusfaelle():
    assert weg_b_pruefen(firma(), STANDARD_ROLLEN, FakeHunter(),
                         FakeDropcontact())["status"] == "kein_treffer"
    assert weg_b_pruefen(firma(domain=""), STANDARD_ROLLEN, FakeHunter(),
                         FakeDropcontact())["status"] == "keine_webseite"
    e = weg_b_pruefen(firma(), STANDARD_ROLLEN, FakeHunter(fehler="Hunter 500"),
                      FakeDropcontact())
    assert e["status"] == "fehler" and "Hunter 500" in e["fehler"]


# --- Gesamtlauf, Zusammenfassung, Bericht, Wiederaufnahme ---

def _lauf_mit_einer_firma():
    prospeo = FakeProspeo(
        personen={"firma.de": [prospeo_person()]},
        anreicherungen={"p-1": {"email": "anna.muster@firma.de", "status": "VERIFIED",
                                "verification_method": "SMTP", "schon_bezahlt": False}})
    hunter = FakeHunter(personen={"firma.de": [hunter_person()]})
    dropcontact = FakeDropcontact(mails={("Anna", "Muster"): {
        "email": "anna.muster@firma.de", "qualification": "nominative@pro"}})
    return vergleich_ausfuehren([firma()], STANDARD_ROLLEN, prospeo=prospeo,
                                hunter=hunter, dropcontact=dropcontact,
                                fortschritt=lambda text: None)


def test_vergleich_beide_wege_pro_firma():
    ergebnisse = _lauf_mit_einer_firma()
    assert len(ergebnisse) == 1
    e = ergebnisse[0]
    assert e["firma"] == "Firma GmbH" and e["domain"] == "firma.de"
    assert e["weg_a"]["status"] == "gepruefte_mail"
    assert e["weg_b"]["status"] == "gepruefte_mail"


def test_zusammenfassung_zaehlt_quote_und_fehler():
    ergebnisse = _lauf_mit_einer_firma()
    fehlerfirma = {"firma": "Kaputt AG", "domain": "kaputt.de",
                   "weg_a": {"status": "fehler", "fehler": "Prospeo 500",
                             "email_geprueft": False, "credits": 0, "dauer_s": 0.1},
                   "weg_b": {"status": "kein_treffer", "fehler": None,
                             "email_geprueft": False, "credits": 0, "dauer_s": 0.1}}
    z = zusammenfassung(ergebnisse + [fehlerfirma])
    assert z["firmen_gesamt"] == 2
    assert z["weg_a"]["gepruefte_mail"] == 1 and z["weg_a"]["quote_prozent"] == 50.0
    assert z["weg_a"]["fehler"] == 1
    assert z["weg_b"]["fehler"] == 0 and z["weg_b"]["quote_prozent"] == 50.0


def test_bericht_enthaelt_kernzahlen():
    ergebnisse = _lauf_mit_einer_firma()
    text = bericht_markdown(ergebnisse, zusammenfassung(ergebnisse))
    assert "Weg A" in text and "Weg B" in text
    assert "Firma GmbH" in text and "anna.muster@firma.de" in text
    assert "100.0" in text  # Trefferquote
    assert "Manuelle Prüfung" in text  # Spalte fuer die Handkontrolle


def test_lauf_speichern_und_fortsetzen(tmp_path):
    ergebnisse = _lauf_mit_einer_firma()
    lauf_speichern(tmp_path, ergebnisse, zusammenfassung(ergebnisse))
    assert (tmp_path / "ergebnisse.json").exists()
    assert (tmp_path / "bericht.md").exists()
    geladen = lauf_laden(tmp_path)
    assert geladen[0]["domain"] == "firma.de"
    # Wiederaufnahme: bereits geprüfte Firmen werden nicht erneut angefragt.
    prospeo = FakeProspeo(fehler="darf nicht aufgerufen werden")
    hunter = FakeHunter(fehler="darf nicht aufgerufen werden")
    neu = vergleich_ausfuehren([firma()], STANDARD_ROLLEN, prospeo=prospeo,
                               hunter=hunter, dropcontact=FakeDropcontact(),
                               vorhandene=geladen, fortschritt=lambda text: None)
    assert neu[0]["weg_a"]["status"] == "gepruefte_mail"

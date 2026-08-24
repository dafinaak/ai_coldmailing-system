"""Tests für den FullEnrich-POC.

Alle Antworten sind nachgebaut - kein Netz, kein einziger echter Credit.
"""
import json
import sqlite3

import pytest

from pipeline.fullenrich_poc import (
    RANG_GRUPPEN, bericht_text, entscheider_waehlen, exportieren,
    firmen_abgleich, firmen_waehlen, handpruefung_liste, kennzahlen_rechnen,
    pruefung_kontakt, rang_von_titel, _leere_zeile, db_oeffnen,
    ergebnis_speichern, _saubern, _eine_firma, _telefone_einordnen,
    _entscheider_guete, _guete_grund)
from pipeline.sources.fullenrich import (
    COMPANY_LOOKUP_URL, ENRICH_BULK_URL, ENRICH_FELDER, FullEnrichFehler,
    FullEnrichSource, KontingentLeer, PEOPLE_SEARCH_URL, beste_mail,
    nur_domain, TESTKONTAKT, ist_sammeladresse,
    telefon_art)


# --------------------------------------------------------------- Attrappen

class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.posts, self.gets = [], []

    def post(self, url, json=None, headers=None, timeout=None):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return self.antworten.pop(0)

    def get(self, url, headers=None, timeout=None):
        self.gets.append({"url": url, "headers": headers})
        return self.antworten.pop(0)


def quelle_mit(antworten, **kwargs):
    kwargs.setdefault("schlafen", lambda _s: None)
    return FullEnrichSource("geheim-123", FakeSession(antworten), **kwargs)


PERSON_CEO = {
    "full_name": "Anna Beispiel", "first_name": "Anna", "last_name": "Beispiel",
    "headline": "Geschäftsführerin",
    "social_profiles": {"professional_network": {
        "url": "https://www.linkedin.com/in/anna"}},
    "employment": [{"title": "Geschäftsführerin", "is_current": True,
                    "company": {"name": "Beispiel GmbH",
                                "domain": "beispiel.de"}}],
}
PERSON_PRAKTIKANT = {
    "full_name": "Tim Klein", "first_name": "Tim", "last_name": "Klein",
    "employment": [{"title": "Werkstudent", "is_current": True,
                    "company": {"name": "Beispiel GmbH",
                                "domain": "beispiel.de"}}],
}


# ------------------------------------------------------- 1. Authentifizierung

def test_ohne_schluessel_gibt_es_keine_quelle():
    with pytest.raises(FullEnrichFehler) as fehler:
        FullEnrichSource("")
    assert "FULLENRICH_API_KEY" in str(fehler.value)


def test_bearer_header_wird_gesetzt():
    quelle = quelle_mit([FakeResponse(200, {"name": "Beispiel GmbH"})])
    quelle.firma_finden("beispiel.de")
    kopf = quelle.session.posts[0]["headers"]
    assert kopf["Authorization"] == "Bearer geheim-123"
    assert kopf["Content-Type"] == "application/json"


def test_schluessel_taucht_in_keiner_fehlermeldung_auf():
    quelle = quelle_mit([FakeResponse(401, {"code": "error.api.key",
                                            "message": "Unknown api key"})])
    with pytest.raises(FullEnrichFehler) as fehler:
        quelle.firma_finden("beispiel.de")
    assert "geheim-123" not in str(fehler.value)
    assert fehler.value.status == 401


# ------------------------------------------------------------ 2. Firmensuche

def test_firma_finden_schickt_die_nackte_domain():
    """Die Doku will "beispiel.de", nicht die ganze URL. Eine URL würde
    durchgehen und trotzdem nichts finden - ein stiller Fehlschlag."""
    quelle = quelle_mit([FakeResponse(200, {"company": {
        "name": "Beispiel GmbH", "domain": "beispiel.de"}})])
    firma = quelle.firma_finden("https://WWW.Beispiel.de/impressum")
    assert quelle.session.posts[0]["url"] == COMPANY_LOOKUP_URL
    assert quelle.session.posts[0]["json"] == {"domain": "beispiel.de"}
    assert firma["name"] == "Beispiel GmbH"


@pytest.mark.parametrize("eingabe,erwartet", [
    ("https://www.beispiel.de/impressum", "beispiel.de"),
    ("HTTP://Beispiel.DE", "beispiel.de"),
    ("beispiel.de", "beispiel.de"),
    ("www.beispiel.de?x=1", "beispiel.de"),
    ("", ""),
])
def test_domain_wird_sauber_normalisiert(eingabe, erwartet):
    assert nur_domain(eingabe) == erwartet


def test_personensuche_nimmt_ebenfalls_die_nackte_domain():
    quelle = quelle_mit([FakeResponse(200, {"people": []})])
    quelle.personen_suchen("https://www.beispiel.de/", ["CEO"])
    assert quelle.session.posts[0]["json"]["current_company_domains"] == [
        {"value": "beispiel.de", "exact_match": True}]


def test_firma_nicht_gefunden_ist_kein_fehler():
    quelle = quelle_mit([FakeResponse(404, {"message": "not found"})])
    assert quelle.firma_finden("unbekannt.de") is None


def test_firma_ohne_domain_kostet_keinen_aufruf():
    quelle = quelle_mit([])
    assert quelle.firma_finden("") is None
    assert quelle.session.posts == []


# --------------------------------------------------------- 3. Firmen-Abgleich

def test_gleiche_domain_ist_ein_starker_treffer():
    status, punkte, _ = firmen_abgleich(
        {"name": "Beispiel GmbH", "domain": "beispiel.de"},
        {"name": "Beispiel GmbH", "domain": "beispiel.de"},
        {"firmenname": "Beispiel GmbH", "firmen_domain": "beispiel.de"})
    assert status == "strong_match"
    assert punkte >= 0.7


def test_widersprechende_domain_ist_no_match():
    status, punkte, belege = firmen_abgleich(
        {"name": "Beispiel GmbH", "domain": "beispiel.de"},
        {"name": "Ganz Anders AG", "domain": "ganzanders.com"}, None)
    assert status == "no_match"
    assert punkte == 0.0
    assert "weicht ab" in belege


def test_nur_namensaehnlichkeit_bleibt_unsicher():
    status, _, _ = firmen_abgleich(
        {"name": "Beispiel GmbH", "domain": "beispiel.de"},
        None, {"firmenname": "Beispiel GmbH", "firmen_domain": ""})
    assert status in ("possible_match", "uncertain")


# ----------------------------------------------------------- 4. Personensuche

def test_personensuche_schraenkt_auf_die_firmendomain_ein():
    """Die Filter sind Listen von OBJEKTEN, nicht von Strings.

    Mit Strings antwortet die API 400 ("cannot unmarshal string into Go
    struct field") - genau so im ersten echten Lauf am 24.08.2026
    passiert. Dieser Test hält die Form fest."""
    quelle = quelle_mit([FakeResponse(200, {"people": [PERSON_CEO]})])
    quelle.personen_suchen("beispiel.de", ["CEO", "Geschäftsführer"])
    anfrage = quelle.session.posts[0]
    assert anfrage["url"] == PEOPLE_SEARCH_URL
    assert anfrage["json"]["current_company_domains"] == [
        {"value": "beispiel.de", "exact_match": True}]
    titel = anfrage["json"]["current_position_titles"]
    assert {"value": "Geschäftsführer", "exact_match": False} in titel
    # Kein einziger nackter String darf durchrutschen.
    assert all(isinstance(t, dict) for t in titel)


def test_personensuche_ohne_treffer_gibt_leere_liste():
    quelle = quelle_mit([FakeResponse(200, {"people": []})])
    assert quelle.personen_suchen("beispiel.de", ["CEO"]) == []


def test_personensuche_vertraegt_fehlendes_people_feld():
    quelle = quelle_mit([FakeResponse(200, {})])
    assert quelle.personen_suchen("beispiel.de", ["CEO"]) == []


# ------------------------------------------------------ 5. Entscheider-Rang

@pytest.mark.parametrize("titel,erwartet", [
    # Rangfolge laut Auftrag 24.08.2026: CEO vor Geschäftsführer vor
    # Inhaber vor Managing Director vor Founder vor Managing Partner.
    ("CEO", 0), ("Chief Executive Officer", 0),
    ("Geschäftsführer", 1), ("Geschäftsführerin", 1),
    ("Inhaber", 2), ("Owner", 2), ("Proprietor", 2),
    ("Managing Director", 3),
    ("Founder", 4), ("Gründer", 4),
    ("Managing Partner", 5),
    ("Prokurist", 6), ("Director", 6),
    ("Werkstudent", len(RANG_GRUPPEN)), ("", len(RANG_GRUPPEN)),
])
def test_rangfolge_der_titel(titel, erwartet):
    assert rang_von_titel(titel) == erwartet


def test_nie_blind_der_erste_treffer():
    gewaehlt, alternativen = entscheider_waehlen(
        [PERSON_PRAKTIKANT, PERSON_CEO])
    assert gewaehlt["name"] == "Anna Beispiel"
    assert gewaehlt["rang"] == 1          # Geschäftsführerin
    assert alternativen[0]["name"] == "Tim Klein"


def test_headline_wird_nie_als_funktionsbezeichnung_uebernommen():
    """Im echten Lauf bekam ein "Digital problem solver" so einen
    Entscheider-Titel angedichtet. Die headline ist Selbstbeschreibung."""
    person = {"full_name": "Joda Stoesser", "first_name": "Joda",
              "last_name": "Stoesser", "headline": "Digital problem solver",
              "employment": [{"is_current": True,
                              "company": {"name": "coders.win"}}]}
    gewaehlt, _ = entscheider_waehlen([person])
    assert gewaehlt["titel"] == ""
    assert gewaehlt["headline"] == "Digital problem solver"
    assert gewaehlt["rang"] == len(RANG_GRUPPEN)


def test_ohne_entscheider_titel_wird_das_vermerkt():
    gewaehlt, _ = entscheider_waehlen([PERSON_PRAKTIKANT])
    assert gewaehlt["rang"] == len(RANG_GRUPPEN)
    assert "kein Entscheider-Titel" in gewaehlt["rang_grund"]


def test_leere_personenliste_gibt_keinen_entscheider():
    assert entscheider_waehlen([]) == (None, [])


# --------------------------------------------------- 6. Kontakt-Anreicherung

def test_anreicherung_schickt_die_drei_enrich_felder():
    quelle = quelle_mit([FakeResponse(200, {"enrichment_id": "abc"})])
    kennung = quelle.anreicherung_starten(
        [{"first_name": "Anna", "last_name": "Beispiel",
          "domain": "beispiel.de", "company_name": "Beispiel GmbH"}], "POC")
    assert kennung == "abc"
    körper = quelle.session.posts[0]["json"]
    assert quelle.session.posts[0]["url"] == ENRICH_BULK_URL
    assert körper["data"][0]["enrich_fields"] == ENRICH_FELDER


def test_anreicherung_ohne_eintraege_ruft_nichts_auf():
    quelle = quelle_mit([])
    assert quelle.anreicherung_starten([], "POC") is None
    assert quelle.session.posts == []


def test_abholen_pollt_bis_fertig():
    quelle = quelle_mit([
        FakeResponse(200, {"status": "IN_PROGRESS"}),
        FakeResponse(200, {"status": "FINISHED", "data": [],
                           "cost": {"credits": 4}}),
    ], wartezeit=0)
    ergebnis = quelle.anreicherung_abholen("abc")
    assert ergebnis["status"] == "FINISHED"
    assert len(quelle.session.gets) == 2


def test_leeres_guthaben_wirft_eigenen_fehler():
    quelle = quelle_mit([FakeResponse(200, {"status": "CREDITS_INSUFFICIENT"})],
                        wartezeit=0)
    with pytest.raises(KontingentLeer):
        quelle.anreicherung_abholen("abc")


def test_abholen_gibt_auf_statt_ewig_zu_pollen():
    quelle = quelle_mit([FakeResponse(200, {"status": "IN_PROGRESS"})] * 3,
                        wartezeit=0, max_abfragen=3)
    with pytest.raises(FullEnrichFehler) as fehler:
        quelle.anreicherung_abholen("abc")
    assert "erneut abgeholt" in str(fehler.value)


# --------------------------------------------------------- 7. Antwort lesen

def test_beste_mail_nimmt_deliverable_vor_catch_all():
    treffer = beste_mail([
        {"email": "b@x.de", "status": "CATCH_ALL"},
        {"email": "a@x.de", "status": "DELIVERABLE"}])
    assert treffer["email"] == "a@x.de"


def test_beste_mail_verwirft_ungueltige():
    assert beste_mail([{"email": "a@x.de", "status": "INVALID"},
                       {"email": "b@x.de", "status": "INVALID_DOMAIN"}]) is None


def test_beste_mail_vertraegt_leere_liste():
    assert beste_mail(None) is None
    assert beste_mail([]) is None


@pytest.mark.parametrize("nummer,erwartet", [
    ("+49 151 61690365", "mobil"), ("0176-55382897", "mobil"),
    ("017642190990", "mobil"), ("+49 5221 9660", "festnetz"),
    ("05235 / 501577-0", "festnetz"),
    # Auslandsnummern werden NICHT geraten - lieber offen unbekannt.
    ("+1 415 555 0100", "unbekannt"), ("+33 6 76 78 90 65", "unbekannt"),
    ("", ""),
])
def test_telefon_art_wird_selbst_bestimmt(nummer, erwartet):
    # Die API sagt NICHT, ob eine Nummer mobil ist - wir ordnen an der
    # Vorwahl ein und geben sonst "unbekannt" zurück.
    assert telefon_art(nummer) == erwartet


@pytest.mark.parametrize("email,erwartet", [
    ("info@firma.de", True), ("office@firma.de", True),
    ("sales@firma.de", True), ("kontakt@firma.de", True),
    ("info-de@firma.de", True), ("no-reply@firma.de", True),
    ("t.cappelmann@firma.de", False), ("mueller@firma.de", False),
    ("anna.beispiel@firma.de", False), ("", False),
])
def test_sammeladressen_werden_erkannt(email, erwartet):
    """Auch eine "work_email" kann info@ sein. Olivers Anforderung meint
    die personenbezogene Adresse, deshalb getrennt messen."""
    assert ist_sammeladresse(email) is erwartet


# --------------------------------------------------------- 8. Fehlende Felder

def test_fehlende_felder_kippen_den_lauf_nicht():
    quelle = quelle_mit([
        FakeResponse(200, {"name": "Beispiel GmbH", "domain": "beispiel.de"}),
        FakeResponse(200, {"people": [PERSON_CEO]}),
        FakeResponse(200, {"enrichment_id": "abc"}),
        FakeResponse(200, {"status": "FINISHED",
                           "data": [{"contact_info": {}}],
                           "cost": {}}),
    ], wartezeit=0)
    zeile = _leere_zeile({"id": 1, "name": "Beispiel GmbH",
                          "domain": "beispiel.de"}, "run-1")
    _eine_firma(quelle, {"id": 1, "name": "Beispiel GmbH",
                         "domain": "beispiel.de"}, zeile, True)
    assert zeile["decision_maker_found"] == 1
    assert zeile["work_email"] == ""
    assert zeile["credits_used"] == 0


def test_voller_durchlauf_fuellt_alle_felder():
    quelle = quelle_mit([
        FakeResponse(200, {"name": "Beispiel GmbH", "domain": "beispiel.de"}),
        FakeResponse(200, {"people": [PERSON_CEO]}),
        FakeResponse(200, {"enrichment_id": "abc"}),
        FakeResponse(200, {"status": "FINISHED", "cost": {"credits": 14},
                           "data": [{"contact_info": {
                               "work_emails": [{"email": "a@beispiel.de",
                                                "status": "DELIVERABLE"}],
                               "personal_emails": [{"email": "a@gmx.de",
                                                    "status": "DELIVERABLE"}],
                               "phones": [{"number": "+49 151 61690365"},
                                          {"number": "+49 5221 9660"}]}}]}),
    ], wartezeit=0)
    firma = {"id": 7, "name": "Beispiel GmbH", "domain": "beispiel.de"}
    zeile = _leere_zeile(firma, "run-1")
    _eine_firma(quelle, firma, zeile, True)
    assert zeile["company_match_status"] == "strong_match"
    assert zeile["decision_maker_name"] == "Anna Beispiel"
    assert zeile["decision_maker_linkedin"].endswith("/anna")
    assert zeile["work_email"] == "a@beispiel.de"
    assert zeile["personal_email"] == "a@gmx.de"
    assert zeile["mobile_phone"] == "+49 151 61690365"
    assert zeile["direct_phone"] == "+49 5221 9660"
    assert zeile["credits_used"] == 14


def test_falsche_firma_wird_nicht_angereichert():
    """Kein Geld für eine Person, die nachweislich woanders arbeitet."""
    quelle = quelle_mit([
        FakeResponse(200, {"name": "Ganz Anders AG", "domain": "anders.com"}),
        FakeResponse(200, {"people": [PERSON_CEO]}),
    ], wartezeit=0)
    firma = {"id": 1, "name": "Beispiel GmbH", "domain": "beispiel.de"}
    zeile = _leere_zeile(firma, "run-1")
    _eine_firma(quelle, firma, zeile, True)
    assert zeile["company_match_status"] == "no_match"
    assert zeile["api_status"] == "skipped_company_mismatch"
    # Nur zwei Aufrufe: lookup und search. Keine Anreicherung.
    assert len(quelle.session.posts) == 2


# --------------------------------------------------------------- 9. Fehler

@pytest.mark.parametrize("code,erwartet", [
    (401, "Schlüssel"), (429, "Ratenlimit"), (500, "500")])
def test_http_fehler_werden_klar_benannt(code, erwartet):
    # 429 und 500 werden wiederholt, deshalb genug Antworten bereitlegen.
    quelle = quelle_mit([FakeResponse(code, {"message": "kaputt"})] * 3,
                        max_wiederholungen=3, pause_bei_limit=0,
                        pause_bei_serverfehler=0)
    with pytest.raises(FullEnrichFehler) as fehler:
        quelle.personen_suchen("beispiel.de", ["CEO"])
    assert erwartet in str(fehler.value)


def test_kaputtes_json_wird_als_fehler_behandelt():
    quelle = quelle_mit(
        [FakeResponse(500, ValueError("kein json"), "<html>")] * 3,
        max_wiederholungen=3, pause_bei_serverfehler=0)
    with pytest.raises(FullEnrichFehler):
        quelle.personen_suchen("beispiel.de", ["CEO"])


# --------------------------------------------------- Begrenzte Wiederholung

def test_ratenlimit_wird_wiederholt_und_klappt_dann():
    quelle = quelle_mit([FakeResponse(429, {"message": "zu viele"}),
                         FakeResponse(200, {"people": [PERSON_CEO]})],
                        pause_bei_limit=0)
    leute = quelle.personen_suchen("beispiel.de", ["CEO"])
    assert len(leute) == 1
    assert len(quelle.session.posts) == 2


def test_serverfehler_wird_wiederholt():
    quelle = quelle_mit([FakeResponse(503, {"message": "weg"}),
                         FakeResponse(200, {"people": []})],
                        pause_bei_serverfehler=0)
    assert quelle.personen_suchen("beispiel.de", ["CEO"]) == []


@pytest.mark.parametrize("code", [400, 401, 402, 404])
def test_diese_fehler_werden_NICHT_wiederholt(code):
    """Ein falscher Schlüssel oder leeres Guthaben ändert sich beim
    zweiten Versuch nicht - Wiederholen wäre nur Zeitverschwendung."""
    quelle = quelle_mit([FakeResponse(code, {"message": "nein"})],
                        pause_bei_limit=0, pause_bei_serverfehler=0)
    with pytest.raises(FullEnrichFehler):
        quelle.personen_suchen("beispiel.de", ["CEO"])
    assert len(quelle.session.posts) == 1


def test_wiederholung_ist_begrenzt():
    quelle = quelle_mit([FakeResponse(500, {"message": "weg"})] * 5,
                        max_wiederholungen=3, pause_bei_serverfehler=0)
    with pytest.raises(FullEnrichFehler):
        quelle.personen_suchen("beispiel.de", ["CEO"])
    assert len(quelle.session.posts) == 3


# ------------------------------------------------------------ 10. Ratenlimit

def test_ratenlimit_wartet_erst_wenn_das_fenster_voll_ist():
    geschlafen = []
    uhr = {"t": 0.0}
    quelle = quelle_mit([FakeResponse(200, {"people": []})] * 4,
                        limit_pro_minute=3,
                        schlafen=lambda s: geschlafen.append(s),
                        jetzt=lambda: uhr["t"])
    for _ in range(4):
        quelle.personen_suchen("beispiel.de", ["CEO"])
    # Die ersten drei laufen ohne Pause, erst der vierte muss warten.
    assert len(geschlafen) == 1
    assert geschlafen[0] > 59


# ------------------------------------------------------- 11. Kennzahlen

def _zeile(**abweichung):
    satz = _leere_zeile({"id": 1, "name": "X", "domain": "x.de"}, "r")
    satz.update(abweichung)
    return satz


def test_kennzahlen_zaehlen_nur_zulaessige_firmen_fuer_die_quoten():
    zeilen = [
        _zeile(automation_status="NO", eligible=1,
               fullenrich_company_found=1, decision_maker_found=1,
               decision_maker_rank=0, decision_maker_status="valid",
               work_email="a@x.de", individual_work_email="a@x.de",
               company_match_status="strong_match",
               verification_status="strong_match",
               mobile_phone="+49 151 1", credits_used=11),
        _zeile(automation_status="NO", eligible=1,
               fullenrich_company_found=1, decision_maker_found=0,
               company_match_status="uncertain",
               verification_status="invalid"),
        _zeile(automation_status="YES", eligible=0,
               exclusion_reason="automation_provider"),
        _zeile(automation_status="UNCERTAIN", eligible=0,
               exclusion_reason="automation_uncertain"),
    ]
    k = kennzahlen_rechnen(zeilen)
    assert k["companies_tested"] == 4
    assert k["automation_yes"] == 1
    assert k["automation_uncertain"] == 1
    assert k["companies_skipped_before_enrichment"] == 2
    assert k["eligible_companies"] == 2
    # Quoten beziehen sich auf die 2 zulässigen, nicht auf alle 4.
    assert k["decision_maker_rate"] == 50.0
    assert k["work_email_rate"] == 50.0
    assert k["fully_enriched_contacts"] == 1
    assert k["credible_decision_makers"] == 1
    assert k["uncertain_people"] == 0
    assert k["total_credits_used"] == 11


def test_work_mail_zaehlt_nie_als_persoenliche_mail():
    """Olivers Anforderung: persönliche Mail getrennt messen."""
    k = kennzahlen_rechnen([_zeile(
        automation_status="NO", eligible=1, decision_maker_found=1,
        work_email="info@x.de", verification_status="possible_match")])
    assert k["work_emails_found"] == 1
    assert k["personal_emails_found"] == 0
    assert k["personal_email_rate"] == 0.0
    assert k["both_emails_found"] == 0


def test_kennzahlen_ohne_zulaessige_firmen_teilen_nicht_durch_null():
    k = kennzahlen_rechnen([_zeile(automation_status="YES", eligible=0)])
    assert k["eligible_companies"] == 0
    assert k["decision_maker_rate"] == 0.0
    assert k["average_credits_per_usable_contact"] == 0.0


def test_bericht_nennt_alle_pflichtzahlen():
    text = bericht_text(kennzahlen_rechnen(
        [_zeile(automation_status="NO", eligible=1)]))
    for stueck in ("Companies tested", "Automation YES", "Automation NO",
                   "Automation UNCERTAIN", "Eligible companies",
                   "Companies matched", "CREDIBLE decision makers",
                   "uncertain people", "INDIVIDUAL work emails",
                   "Generic company emails", "Private personal emails",
                   "Direct lines found", "Mobile numbers found",
                   "Usable contacts", "Fully enriched",
                   "Needing manual review", "API failures",
                   "Total credits used"):
        assert stueck in text


# -------------------------------------------------------- 12. Auswahl / DB

def _master_db_bauen(pfad, anzahl):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(pfad)
    db.execute("""CREATE TABLE companies (id INTEGER PRIMARY KEY,
                  kennung TEXT, name TEXT, domain TEXT, website TEXT,
                  strasse TEXT, plz TEXT, ort TEXT, land TEXT,
                  telefon TEXT, email_allgemein TEXT, sektor TEXT,
                  keywords TEXT, mitarbeiter TEXT, ceo_owner TEXT)""")
    for nummer in range(anzahl):
        db.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (nummer + 1, f"firma{nummer:03d}.de", f"Firma {nummer}",
                    f"firma{nummer:03d}.de", f"https://firma{nummer:03d}.de",
                    "Musterweg 1", "32049", "Herford", "Deutschland",
                    "05221 1234", "", "IT", "", "", ""))
    db.commit()
    db.close()


def test_auswahl_ist_wiederholbar(tmp_path):
    _master_db_bauen(tmp_path / "daten/master.db", 250)
    erste = firmen_waehlen(tmp_path, 100)
    zweite = firmen_waehlen(tmp_path, 100)
    assert len(erste) == 100
    assert [f["id"] for f in erste] == [f["id"] for f in zweite]


def test_auswahl_nimmt_alles_wenn_weniger_als_gewuenscht_da_ist(tmp_path):
    _master_db_bauen(tmp_path / "daten/master.db", 12)
    assert len(firmen_waehlen(tmp_path, 100)) == 12


def test_auswahl_wird_weggeschrieben(tmp_path):
    _master_db_bauen(tmp_path / "daten/master.db", 30)
    firmen_waehlen(tmp_path, 10)
    daten = json.loads(
        (tmp_path / "daten/fullenrich-poc-auswahl.json").read_text("utf-8"))
    assert daten["gewaehlt"] == 10
    assert len(daten["company_ids"]) == 10


def test_poc_datenbank_beruehrt_die_master_db_nicht(tmp_path):
    _master_db_bauen(tmp_path / "daten/master.db", 5)
    db = db_oeffnen(tmp_path)
    ergebnis_speichern(db, _zeile(company_name="Firma 0"))
    db.close()
    assert (tmp_path / "daten/fullenrich-poc.db").exists()
    master = sqlite3.connect(tmp_path / "daten/master.db")
    tabellen = {r[0] for r in master.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    master.close()
    assert tabellen == {"companies"}


# ------------------------------------------------------------- 13. Export

def test_export_schreibt_drei_dateien(tmp_path):
    zeilen = [
        _zeile(company_name="Gut", automation_status="NO", eligible=1,
               decision_maker_found=1, decision_maker_status="valid",
               work_email="a@x.de", individual_work_email="a@x.de",
               company_match_status="strong_match",
               verification_status="strong_match"),
        _zeile(company_name="Automation", automation_status="YES"),
        _zeile(company_name="Unklar", automation_status="UNCERTAIN"),
    ]
    ziele = exportieren(zeilen, tmp_path, stempel="test")
    alle = ziele["alle_csv"].read_text(encoding="utf-8")
    kontakte = ziele["kontakte_csv"].read_text(encoding="utf-8")
    pruefung = ziele["handpruefung_csv"].read_text(encoding="utf-8")
    assert alle.count("\n") == 4                 # Kopf + drei Firmen
    assert kontakte.count("\n") == 2             # Kopf + nur der gute
    assert "Gut" in kontakte and "Automation" not in kontakte
    assert "Unklar" in pruefung                  # unklare kommen zur Hand


def test_handpruefung_verwirft_nichts_stillschweigend():
    zeilen = [
        _zeile(automation_status="UNCERTAIN"),
        _zeile(automation_status="NO", eligible=1,
               company_match_status="uncertain",
               verification_status="uncertain"),
        _zeile(automation_status="NO", eligible=1,
               company_match_status="strong_match",
               verification_status="strong_match"),
    ]
    treffer = handpruefung_liste(zeilen)
    assert len(treffer) == 2
    gruende = " ".join(g for g, _ in treffer)
    assert "Automatisierung unklar" in gruende
    assert "Firmen-Zuordnung unsicher" in gruende


# ------------------------------------------------- Kontakt-Qualitaetspruefung

def test_ohne_entscheider_ist_der_kontakt_ungueltig():
    assert pruefung_kontakt(_zeile(decision_maker_found=0))[0] == "invalid"


def test_person_der_falschen_firma_ist_ungueltig():
    zustand, grund = pruefung_kontakt(_zeile(
        decision_maker_found=1, work_email="a@x.de",
        company_match_status="no_match"))
    assert zustand == "invalid"
    assert "andere" in grund.lower() or "falsch" in grund.lower()


def test_unsichere_zuordnung_wird_nicht_still_als_geprueft_gespeichert():
    zustand, grund = pruefung_kontakt(_zeile(
        decision_maker_found=1, work_email="a@x.de",
        company_match_status="uncertain", decision_maker_rank=None))
    assert zustand == "uncertain"
    assert grund


def test_sauberer_fall_ist_strong_match():
    zustand, grund = pruefung_kontakt(_zeile(
        decision_maker_found=1, work_email="a@x.de",
        work_email_status="DELIVERABLE",
        company_match_status="strong_match", decision_maker_rank=0))
    assert zustand == "strong_match"
    assert grund == ""


# --------------------------------------------------------- Telefon-Trennung

def test_firmenzentrale_zaehlt_nie_als_persoenliche_nummer():
    """Olivers Anforderung: die Zentrale ist keine Durchwahl."""
    zeile = _zeile(company_phone="+49 5221 9660")
    _telefone_einordnen([{"number": "05221 9660"}], zeile)
    assert zeile["direct_phone"] == ""
    assert zeile["mobile_phone"] == ""
    assert zeile["direct_phone_status"] == "company_switchboard_ignored"


def test_mobil_und_festnetz_werden_getrennt():
    zeile = _zeile(company_phone="+49 5221 9660")
    _telefone_einordnen([{"number": "+49 151 61690365"},
                         {"number": "+49 5221 111222"}], zeile)
    assert zeile["mobile_phone"] == "+49 151 61690365"
    assert zeile["direct_phone"] == "+49 5221 111222"


def test_auslandsnummer_wird_nicht_als_mobil_oder_durchwahl_gezaehlt():
    """Nicht raten: eine falsch als mobil ausgewiesene Nummer wäre
    schlimmer als eine offen unbekannte."""
    zeile = _zeile()
    _telefone_einordnen([{"number": "+1 415 555 0100"}], zeile)
    assert zeile["mobile_phone"] == ""
    assert zeile["direct_phone"] == ""
    assert zeile["direct_phone_status"] == "type_unknown_not_counted"
    # Verloren geht sie trotzdem nicht.
    assert "+1 415 555 0100" in zeile["unknown_phones"]


def test_guthaben_wird_vom_konto_gelesen():
    quelle = quelle_mit([FakeResponse(200, {"balance": 313.5})])
    assert quelle.guthaben() == 313.5
    assert quelle.session.gets[0]["url"].endswith("/account/credits")


# ------------------------------------------------------ Such-Credits/Bremse

def test_suchtreffer_werden_als_credits_mitgezaehlt():
    """Die Suche kostet 0,25 je Treffer - die API meldet das aber nicht.
    Also zählen wir selbst mit, sonst fehlt der halbe Preis im Bericht."""
    quelle = quelle_mit([
        FakeResponse(200, {"name": "Beispiel GmbH", "domain": "beispiel.de"}),
        FakeResponse(200, {"people": [PERSON_CEO, PERSON_PRAKTIKANT]}),
        FakeResponse(200, {"enrichment_id": "abc"}),
        FakeResponse(200, {"status": "FINISHED", "data": [],
                           "cost": {"credits": 1}}),
    ], wartezeit=0)
    firma = {"id": 1, "name": "Beispiel GmbH", "domain": "beispiel.de"}
    zeile = _leere_zeile(firma, "run-1")
    zaehler = [0.0]
    _eine_firma(quelle, firma, zeile, True, zaehler)
    # 1 Firma + 2 Personen = 3 Treffer * 0,25
    assert zaehler[0] == pytest.approx(0.75)


def test_nicht_gefundene_firma_kostet_keine_such_credits():
    quelle = quelle_mit([
        FakeResponse(404, {"message": "not found"}),
        FakeResponse(200, {"people": []}),
    ], wartezeit=0)
    firma = {"id": 1, "name": "X", "domain": "x.de"}
    zeile = _leere_zeile(firma, "run-1")
    zaehler = [0.0]
    _eine_firma(quelle, firma, zeile, True, zaehler)
    assert zaehler[0] == 0.0
    assert zeile["fullenrich_company_found"] == 0


def test_schluessel_pruefung_nutzt_den_gratis_testkontakt():
    quelle = quelle_mit([FakeResponse(200, {"enrichment_id": "test-1"})])
    urteil = quelle.schluessel_pruefen()
    assert urteil["ok"] is True
    gesendet = quelle.session.posts[0]["json"]["data"][0]
    assert gesendet["domain"] == TESTKONTAKT["domain"]
    assert gesendet["last_name"] == TESTKONTAKT["last_name"]


def test_schluessel_pruefung_wirft_nicht_bei_falschem_schluessel():
    quelle = quelle_mit([FakeResponse(401, {"message": "Unknown api key"})])
    urteil = quelle.schluessel_pruefen()
    assert urteil["ok"] is False
    assert urteil["status"] == 401
    assert "geheim-123" not in urteil["meldung"]


# --------------------------------------------------------------- Sicherheit

def test_rohantwort_mit_schluesselartigem_feld_wird_redigiert():
    text = _saubern({"authorization": "Bearer geheim"})
    assert "geheim" not in text
    assert "redigiert" in text


def test_normale_rohantwort_bleibt_lesbar():
    assert "FINISHED" in _saubern({"status": "FINISHED"})


def test_402_gilt_als_leeres_guthaben_nicht_als_allgemeiner_fehler():
    """Gemessen am 24.08.2026: bei 13,25 Credits kam 402 beim Abholen.
    Weiterlaufen hätte keinen Sinn, also eigener Fehlertyp."""
    quelle = quelle_mit([FakeResponse(402, {"message": "Payment Required"})],
                        wartezeit=0)
    with pytest.raises(KontingentLeer):
        quelle.anreicherung_abholen("abc")


# ------------------------------------------- Kosten-Tor: Entscheider zuerst

def _person(titel="", headline="", rang=None, domain="beispiel.de"):
    return {"name": "Anna Beispiel", "first_name": "Anna",
            "last_name": "Beispiel", "titel": titel, "headline": headline,
            "firmenname": "Beispiel GmbH", "firmen_domain": domain,
            "linkedin": "", "rang": rang if rang is not None
            else rang_von_titel(titel)}


def test_glaubwuerdiger_entscheider_oeffnet_das_tor():
    zeile = _zeile(domain="beispiel.de", company_match_status="strong_match")
    assert _entscheider_guete(zeile, _person("Geschäftsführer")) == "valid"


def test_ohne_stellentitel_kein_teurer_aufruf():
    """Eine Mobilnummer kostet 10 Credits - nicht für jemanden, von dem
    wir nur eine headline kennen."""
    zeile = _zeile(domain="beispiel.de", company_match_status="strong_match")
    person = _person("", "Digital problem solver")
    assert _entscheider_guete(zeile, person) == "uncertain"
    assert "headline" in _guete_grund(zeile, person)


def test_schwacher_firmentreffer_oeffnet_das_tor_nicht():
    zeile = _zeile(domain="beispiel.de", company_match_status="possible_match")
    assert _entscheider_guete(zeile, _person("CEO")) == "uncertain"


def test_person_anderer_domain_ist_company_mismatch():
    zeile = _zeile(domain="beispiel.de", company_match_status="strong_match")
    assert _entscheider_guete(
        zeile, _person("CEO", domain="ganzanders.de")) == "company_mismatch"


def test_unpassender_titel_oeffnet_das_tor_nicht():
    zeile = _zeile(domain="beispiel.de", company_match_status="strong_match")
    person = _person("Werkstudent")
    assert _entscheider_guete(zeile, person) == "uncertain"
    assert "kein" in _guete_grund(zeile, person).lower()


def test_kein_enrich_aufruf_ohne_glaubwuerdigen_entscheider():
    """Das Tor muss die Anreicherung wirklich verhindern, nicht nur
    markieren - sonst fließen die Credits trotzdem."""
    quelle = quelle_mit([
        FakeResponse(200, {"companies": [{"name": "Beispiel GmbH",
                                          "domain": "beispiel.de"}]}),
        FakeResponse(200, {"people": [PERSON_PRAKTIKANT]}),
    ], wartezeit=0)
    firma = {"id": 1, "name": "Beispiel GmbH", "domain": "beispiel.de"}
    zeile = _leere_zeile(firma, "run-1")
    _eine_firma(quelle, firma, zeile, True)
    assert zeile["decision_maker_status"] == "uncertain"
    assert zeile["api_status"] == "skipped_uncertain"
    # Nur lookup und search - KEIN enrich.
    assert len(quelle.session.posts) == 2


# ----------------------------------------------- Drei E-Mail-Kategorien

def test_individuelle_geschaeftsmail_ist_olivers_ziel():
    quelle = quelle_mit([
        FakeResponse(200, {"companies": [{"name": "Beispiel GmbH",
                                          "domain": "beispiel.de"}]}),
        FakeResponse(200, {"people": [PERSON_CEO]}),
        FakeResponse(200, {"enrichment_id": "abc"}),
        FakeResponse(200, {"status": "FINISHED", "cost": {"credits": 1},
                           "data": [{"contact_info": {"work_emails": [
                               {"email": "a.beispiel@beispiel.de",
                                "status": "DELIVERABLE"}]}}]}),
    ], wartezeit=0)
    firma = {"id": 1, "name": "Beispiel GmbH", "domain": "beispiel.de"}
    zeile = _leere_zeile(firma, "run-1")
    _eine_firma(quelle, firma, zeile, True)
    assert zeile["individual_work_email"] == "a.beispiel@beispiel.de"
    assert zeile["generic_company_email"] == ""


def test_sammeladresse_landet_nicht_bei_den_individuellen():
    quelle = quelle_mit([
        FakeResponse(200, {"companies": [{"name": "Beispiel GmbH",
                                          "domain": "beispiel.de"}]}),
        FakeResponse(200, {"people": [PERSON_CEO]}),
        FakeResponse(200, {"enrichment_id": "abc"}),
        FakeResponse(200, {"status": "FINISHED", "cost": {"credits": 1},
                           "data": [{"contact_info": {"work_emails": [
                               {"email": "info@beispiel.de",
                                "status": "DELIVERABLE"}]}}]}),
    ], wartezeit=0)
    firma = {"id": 1, "name": "Beispiel GmbH", "domain": "beispiel.de"}
    zeile = _leere_zeile(firma, "run-1")
    _eine_firma(quelle, firma, zeile, True)
    assert zeile["generic_company_email"] == "info@beispiel.de"
    assert zeile["individual_work_email"] == ""


def test_kennzahlen_zaehlen_nur_individuelle_mails_als_brauchbar():
    zeilen = [
        _zeile(automation_status="NO", eligible=1, decision_maker_found=1,
               decision_maker_status="valid",
               individual_work_email="a@x.de", mobile_phone="+49 151 1"),
        _zeile(automation_status="NO", eligible=1, decision_maker_found=1,
               decision_maker_status="valid",
               generic_company_email="info@x.de"),
    ]
    k = kennzahlen_rechnen(zeilen)
    assert k["individual_work_emails"] == 1
    assert k["generic_company_emails"] == 1
    assert k["usable_contacts"] == 1
    assert k["fully_enriched_contacts"] == 1

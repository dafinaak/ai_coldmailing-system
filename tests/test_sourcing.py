import pytest
from pipeline.config import Kunde
from pipeline.sourcing import (source_leads, _rolle_passt, _qualifiziert,
                                _nach_rollen_sortieren, _firmenname_saeubern)


class _FakeApify:
    def __init__(self, firmen):
        self._firmen = firmen
    def search(self, suchbegriff, limit):
        return self._firmen[:limit]


class _FakeHunter:
    """Liefert je Domain eine feste Personenliste (wie HunterSource.entscheider_finden)."""
    def __init__(self, personen_je_domain):
        self._p = personen_je_domain
    def entscheider_finden(self, domain, limit=10):
        return list(self._p.get(domain, []))


class _FakeDropcontact:
    """Baut je Vorname eine feste gepruefte Mail (oder None, wenn nicht im Plan)."""
    def __init__(self, mail_je_vorname=None):
        self._mails = mail_je_vorname or {}
        self.aufrufe = []
    def email_bauen(self, first_name, last_name, website, company=""):
        self.aufrufe.append((first_name, last_name, website))
        wert = self._mails.get(first_name)
        return {"email": wert, "qualification": "nominative@pro"} if wert else None


def _person(first, last="Muster", title="Geschäftsführer", email="",
            confidence=90, decision_maker=True, verification_status=""):
    return {"first_name": first, "last_name": last, "title": title, "email": email,
            "confidence": confidence, "decision_maker": decision_maker,
            "verification_status": verification_status}


def _kunde(**overrides):
    basis = dict(name="Demo", zielgruppe={}, angebot="A", tonalitaet="T", absender="Ab",
                 follow_up_tage=[1, 2], test_empfaenger=["t@example.com"],
                 maps_suche="IT-Dienstleister Hannover", kontakt_rollen=["Geschäftsführer"])
    basis.update(overrides)
    return Kunde(**basis)


def _firma(domain, name=None):
    return {"name": name or domain, "website": f"https://{domain}", "domain": domain,
            "address": "", "categories": []}


def _quellen(firmen, personen_je_domain, mails):
    return dict(apify_source=_FakeApify(firmen),
                hunter_source=_FakeHunter(personen_je_domain),
                dropcontact_source=_FakeDropcontact(mails))


# --- Kern: Hunter findet Entscheider, Dropcontact prueft die Mail ----------

def test_lead_aus_hunter_treffer_und_dropcontact_mail():
    firmen = [_firma("firma-a.de")]
    personen = {"firma-a.de": [_person("Anna", title="Geschäftsführerin")]}
    leads, deckung, ausgang = source_leads(
        _kunde(), 10, "apify", "hunter", "dropcontact",
        **_quellen(firmen, personen, {"Anna": "anna@firma-a.de"}))
    assert len(leads) == 1
    lead = leads[0]
    assert lead.email == "anna@firma-a.de"
    assert lead.first_name == "Anna" and lead.title == "Geschäftsführerin"
    assert lead.company == "firma-a.de"
    assert lead.source == "dropcontact"
    assert deckung == {"firmen_gesamt": 1, "firmen_mit_kontakt": 1, "quote_prozent": 100.0,
                       "je_stufe": {"hunter_dropcontact": 1, "info@": 0}}
    assert [f["ausgang"] for f in ausgang] == ["mit_entscheider"]


def test_dropcontact_findet_nichts_faellt_auf_info_at():
    # Hunter kennt die Person, Dropcontact baut keine Mail, Hunters eigene Mail
    # ist nicht als valid verifiziert -> info@ als Rueckfall.
    firmen = [_firma("klein.de")]
    personen = {"klein.de": [_person("Anna", email="anna@klein.de", verification_status="")]}
    leads, deckung, ausgang = source_leads(
        _kunde(), 10, "a", "b", "c", **_quellen(firmen, personen, {}))
    assert len(leads) == 1
    assert leads[0].email == "info@klein.de" and leads[0].source == "info@"
    assert deckung["firmen_mit_kontakt"] == 1
    assert [f["ausgang"] for f in ausgang] == ["info_fallback"]


def test_hunter_findet_niemanden_faellt_auf_info_at():
    firmen = [_firma("leer.de")]
    leads, deckung, ausgang = source_leads(
        _kunde(), 10, "a", "b", "c", **_quellen(firmen, {"leer.de": []}, {}))
    assert leads[0].email == "info@leer.de" and leads[0].source == "info@"
    assert [f["ausgang"] for f in ausgang] == ["info_fallback"]


def test_faellt_auf_hunters_eigene_mail_wenn_valide_und_dropcontact_leer():
    # Dropcontact baut nichts, aber Hunter hat die Mail selbst als valid
    # verifiziert -> die wird genutzt (Quelle "hunter"), kein info@.
    firmen = [_firma("firma-b.de")]
    personen = {"firma-b.de": [_person("Bea", email="bea@firma-b.de",
                                        verification_status="valid")]}
    leads, deckung, ausgang = source_leads(
        _kunde(), 10, "a", "b", "c", **_quellen(firmen, personen, {}))
    assert leads[0].email == "bea@firma-b.de" and leads[0].source == "hunter"
    assert [f["ausgang"] for f in ausgang] == ["mit_entscheider"]


# --- Auswahl: Rollen-Prioritaet, Qualifikation, Deckelung ------------------

def test_rollen_treffer_wird_vor_anderem_entscheider_gewaehlt():
    # Zwei Entscheider: ein CFO (decision_maker, aber keine Wunschrolle) und
    # eine Geschaeftsfuehrerin (Wunschrolle). Bei Deckelung auf 1 muss die
    # Geschaeftsfuehrerin gewinnen.
    firmen = [_firma("firma-c.de")]
    personen = {"firma-c.de": [
        _person("Fritz", title="CFO", decision_maker=True),
        _person("Gerda", title="Geschäftsführerin", decision_maker=True)]}
    leads, _, _ = source_leads(
        _kunde(max_kontakte_pro_firma=1), 10, "a", "b", "c",
        **_quellen(firmen, personen, {"Fritz": "fritz@firma-c.de", "Gerda": "gerda@firma-c.de"}))
    assert len(leads) == 1 and leads[0].first_name == "Gerda"


def test_nicht_entscheider_ohne_rollentreffer_wird_uebersprungen():
    # Hunter liefert nur einen Support-Mitarbeiter (kein Entscheider, keine
    # Wunschrolle) -> nicht anschreiben, stattdessen info@.
    firmen = [_firma("support.de")]
    personen = {"support.de": [_person("Tom", title="Support", decision_maker=False)]}
    leads, _, ausgang = source_leads(
        _kunde(), 10, "a", "b", "c",
        **_quellen(firmen, personen, {"Tom": "tom@support.de"}))
    assert leads[0].email == "info@support.de"
    assert [f["ausgang"] for f in ausgang] == ["info_fallback"]


def test_standard_ist_ein_entscheider_pro_firma():
    firmen = [_firma("viele.de")]
    personen = {"viele.de": [_person(f"P{i}", title="Geschäftsführer") for i in range(5)]}
    mails = {f"P{i}": f"p{i}@viele.de" for i in range(5)}
    leads, _, _ = source_leads(_kunde(), 10, "a", "b", "c",  # Default-Deckel = 1
                               **_quellen(firmen, personen, mails))
    assert len(leads) == 1


def test_deckelung_respektiert_hoehere_obergrenze():
    firmen = [_firma("viele.de")]
    personen = {"viele.de": [_person(f"P{i}", title="Geschäftsführer") for i in range(5)]}
    mails = {f"P{i}": f"p{i}@viele.de" for i in range(5)}
    leads, _, _ = source_leads(_kunde(max_kontakte_pro_firma=2), 10, "a", "b", "c",
                               **_quellen(firmen, personen, mails))
    assert len(leads) == 2


# --- Deckungsquote + Robustheit -------------------------------------------

def test_deckungsquote_4_von_5_firmen():
    firmen = [_firma(f"f{i}.de") for i in range(4)]
    # 5. Firma ohne Webseite (keine Domain) -> kein Kontakt, kein info@.
    firmen.append({"name": "Ohne", "website": "", "domain": "", "address": "", "categories": []})
    personen = {f"f{i}.de": [_person(f"A{i}", title="Geschäftsführer")] for i in range(4)}
    mails = {f"A{i}": f"a@f{i}.de" for i in range(4)}
    leads, deckung, _ = source_leads(_kunde(), 10, "a", "b", "c",
                                     **_quellen(firmen, personen, mails))
    assert deckung == {"firmen_gesamt": 5, "firmen_mit_kontakt": 4, "quote_prozent": 80.0,
                       "je_stufe": {"hunter_dropcontact": 4, "info@": 0}}


def test_deckungsquote_ohne_firmen_ist_null():
    leads, deckung, _ = source_leads(_kunde(), 10, "a", "b", "c",
                                     **_quellen([], {}, {}))
    assert leads == [] and deckung == {"firmen_gesamt": 0, "firmen_mit_kontakt": 0, "quote_prozent": 0.0,
                                       "je_stufe": {"hunter_dropcontact": 0, "info@": 0}}


def test_fehlerhafte_firma_bricht_den_lauf_nicht_ab():
    # Eine einzelne fehlerhafte Firma (z.B. Dropcontact lehnt den Batch ab)
    # darf den Lauf nicht sprengen - sie zaehlt als "fehler", der Rest laeuft.
    firmen = [_firma("f1.de"), _firma("f2.de"), _firma("f3.de")]
    personen = {d: [_person("A", title="Geschäftsführer")] for d in ("f1.de", "f2.de", "f3.de")}

    class _FlackerndesDropcontact:
        def email_bauen(self, first_name, last_name, website, company=""):
            if "f2.de" in website:
                raise RuntimeError("Dropcontact lehnt den Batch ab: no credits left")
            domain = website.split("//")[-1]
            return {"email": f"a@{domain}", "qualification": "nominative@pro"}

    leads, deckung, ausgang = source_leads(
        _kunde(), 10, "a", "b", "c",
        apify_source=_FakeApify(firmen), hunter_source=_FakeHunter(personen),
        dropcontact_source=_FlackerndesDropcontact())
    assert {l.email for l in leads} == {"a@f1.de", "a@f3.de"}
    assert deckung == {"firmen_gesamt": 3, "firmen_mit_kontakt": 2, "quote_prozent": 66.7,
                       "je_stufe": {"hunter_dropcontact": 2, "info@": 0}}
    ausgang_je_domain = {f["domain"]: f["ausgang"] for f in ausgang}
    assert ausgang_je_domain == {"f1.de": "mit_entscheider", "f2.de": "fehler",
                                 "f3.de": "mit_entscheider"}


# --- Ausgang-Aufschluesselung ---------------------------------------------

def test_ausgang_keine_webseite():
    firmen = [{"name": "Ohne Webseite GmbH", "website": "", "domain": "",
               "address": "", "categories": []}]
    leads, _, ausgang = source_leads(_kunde(), 10, "a", "b", "c",
                                     **_quellen(firmen, {}, {}))
    assert leads == []
    assert [f["ausgang"] for f in ausgang] == ["keine_webseite"]


def test_ausgang_kein_entscheider_bei_webseite_ohne_domain():
    # Webseite vorhanden, aber keine brauchbare Domain (also kein info@ moeglich)
    # und Hunter findet nichts -> "kein_entscheider" (nicht "keine_webseite").
    firmen = [{"name": "Komische URL", "website": "http://localhost", "domain": "",
               "address": "", "categories": []}]
    leads, _, ausgang = source_leads(_kunde(), 10, "a", "b", "c",
                                     **_quellen(firmen, {}, {}))
    assert leads == []
    assert [f["ausgang"] for f in ausgang] == ["kein_entscheider"]


# --- Konfig-Fehler + echte Klassen ----------------------------------------

def test_fehlende_maps_suche_wirft_klaren_deutschen_fehler():
    with pytest.raises(ValueError, match="maps_suche"):
        source_leads(_kunde(maps_suche=""), 10, "a", "b", "c", **_quellen([], {}, {}))


def test_fehlende_kontakt_rollen_wirft_klaren_deutschen_fehler():
    with pytest.raises(ValueError, match="kontakt_rollen"):
        source_leads(_kunde(kontakt_rollen=[]), 10, "a", "b", "c", **_quellen([], {}, {}))


def test_ohne_injizierte_quellen_werden_die_echten_klassen_mit_den_keys_gebaut():
    # Kein Netzwerkaufruf - nur pruefen, dass source_leads() die echten Klassen
    # mit den uebergebenen Keys baut (Netzverhalten ist in den je-Quelle-Tests
    # abgedeckt). Firmenliste leer, damit nichts angereichert wird.
    import pipeline.sourcing as s
    gebaut = {}

    class _SpionApify(s.ApifyMapsSource):
        def __init__(self, api_key):
            gebaut["apify"] = api_key
        def search(self, suchbegriff, limit):
            return []

    class _SpionHunter(s.HunterSource):
        def __init__(self, api_key):
            gebaut["hunter"] = api_key

    class _SpionDropcontact(s.DropcontactSource):
        def __init__(self, api_key):
            gebaut["dropcontact"] = api_key

    orig = (s.ApifyMapsSource, s.HunterSource, s.DropcontactSource)
    s.ApifyMapsSource, s.HunterSource, s.DropcontactSource = _SpionApify, _SpionHunter, _SpionDropcontact
    try:
        leads, deckung, _ = source_leads(_kunde(), 10, "apify-key", "hunter-key", "dropcontact-key")
    finally:
        s.ApifyMapsSource, s.HunterSource, s.DropcontactSource = orig
    assert leads == []
    assert gebaut == {"apify": "apify-key", "hunter": "hunter-key", "dropcontact": "dropcontact-key"}


# --- Firmenname aus dem (bereinigten) Google-Maps-Titel -------------------

def test_firmenname_kommt_aus_bereinigtem_maps_namen():
    firmen = [{"name": "IT-Dienstleister Hannover - Ihre Helden",
               "website": "https://ihrehelden.de", "domain": "ihrehelden.de",
               "address": "", "categories": []}]
    personen = {"ihrehelden.de": [_person("Anna", title="Geschäftsführerin")]}
    leads, _, _ = source_leads(_kunde(), 10, "a", "b", "c",
                               **_quellen(firmen, personen, {"Anna": "anna@ihrehelden.de"}))
    assert leads[0].company == "Ihre Helden"


# --- Hilfsfunktionen: _qualifiziert / _nach_rollen_sortieren ---------------

def test_qualifiziert_bei_decision_maker_oder_rollentreffer():
    assert _qualifiziert(_person("A", title="Support", decision_maker=True), ["Geschäftsführer"])
    assert _qualifiziert(_person("A", title="Geschäftsführer", decision_maker=False), ["Geschäftsführer"])
    assert not _qualifiziert(_person("A", title="Support", decision_maker=False), ["Geschäftsführer"])


def test_nach_rollen_sortieren_holt_rollentreffer_nach_vorn():
    personen = [_person("A", title="CFO"), _person("B", title="Geschäftsführer")]
    sortiert = _nach_rollen_sortieren(personen, ["Geschäftsführer"])
    assert [p["first_name"] for p in sortiert] == ["B", "A"]


# --- Rollen-Synonym-Matcher (_rolle_passt) - unveraendert ------------------

def test_managing_director_passt_zu_geschaeftsfuehrer():
    assert _rolle_passt("Managing Director", "Geschäftsführer") is True


def test_head_of_it_passt_zu_it_leiter():
    assert _rolle_passt("Head of IT", "IT-Leiter") is True


def test_cto_matcht_nicht_raw_substring_in_director_titeln():
    for titel in ("Sales Director", "Finance Director", "General Contractor"):
        assert _rolle_passt(titel, "IT-Leiter") is False, titel


def test_kurze_akronyme_matchen_weiterhin_als_eigenes_wort():
    assert _rolle_passt("CTO", "IT-Leiter") is True
    assert _rolle_passt("CEO", "Geschäftsführer") is True
    assert _rolle_passt("Buchhalter", "Geschäftsführer") is False


def test_weibliche_form_passt_zur_maennlichen_rolle():
    # In Deutschland sehr haeufig: der Titel steht in der weiblichen Form.
    assert _rolle_passt("Geschäftsführerin", "Geschäftsführer") is True
    assert _rolle_passt("IT-Leiterin", "IT-Leiter") is True
    assert _rolle_passt("Inhaberin", "Geschäftsführer") is True


# --- Firmenname-Bereinigung (_firmenname_saeubern) - unveraendert ----------

def test_firmenname_saeubern_entfernt_suchbegriff_praefix():
    assert (_firmenname_saeubern("IT-Dienstleister Hannover - Ihre Helden",
                                  "IT-Dienstleister Hannover") == "Ihre Helden")


def test_firmenname_saeubern_laesst_saubere_namen_unangetastet():
    assert _firmenname_saeubern("Ihre Helden GmbH", "IT-Dienstleister Hannover") == "Ihre Helden GmbH"


def test_firmenname_saeubern_laesst_echten_bindestrich_namen_unangetastet():
    assert (_firmenname_saeubern("Müller - Schmidt GbR", "IT-Dienstleister Hannover")
            == "Müller - Schmidt GbR")


# --- Kaskade (Chef-Vorgabe 23.07.2026): Stufe 1 -> Stufe 2 -> info@ --------

class _FakeProspeo:
    """Wie ProspeoSource: findet Personen je Domain, deckt Mails je person_id auf."""
    def __init__(self, personen_je_domain=None, mail_je_person_id=None):
        self._p = personen_je_domain or {}
        self._m = mail_je_person_id or {}
        self.such_domains = []
    def entscheider_finden(self, domain):
        self.such_domains.append(domain)
        return list(self._p.get(domain, []))
    def email_anreichern(self, person_id):
        return self._m.get(person_id)


class _FakeHunterMitPruefer(_FakeHunter):
    """Hunter-Fake samt Email-Verifier (fuer die info@-Pruefung)."""
    def __init__(self, personen_je_domain, pruefstatus_je_email=None, pruef_fehler=None):
        super().__init__(personen_je_domain)
        self._status = pruefstatus_je_email or {}
        self._fehler = pruef_fehler
        self.geprueft = []
    def email_pruefen(self, email):
        if self._fehler:
            raise RuntimeError(self._fehler)
        self.geprueft.append(email)
        return {"status": self._status.get(email, "unknown"), "score": 50}


def _prospeo_person(pid="p-1", first="Paula", last="Prosp", title="Geschäftsführerin",
                    seniority="Founder/Owner"):
    return {"person_id": pid, "first_name": first, "last_name": last,
            "title": title, "seniority": seniority}


def test_stufe2_prospeo_fuellt_die_luecken_von_stufe1():
    firmen = [_firma("a.de"), _firma("b.de")]
    kunde = _kunde(anbieter_reihenfolge=["hunter_dropcontact", "prospeo"])
    prospeo = _FakeProspeo(
        personen_je_domain={"b.de": [_prospeo_person()]},
        mail_je_person_id={"p-1": {"email": "paula.prosp@b.de", "status": "VERIFIED",
                                   "verification_method": "SMTP", "schon_bezahlt": False}})
    leads, deckung, firmen_aus = source_leads(
        kunde, 10, "k", "k", "k",
        **_quellen(firmen, {"a.de": [_person("Anna")]}, {"Anna": "anna@a.de"}),
        prospeo_source=prospeo)
    assert deckung["firmen_mit_kontakt"] == 2
    assert [l.source for l in leads] == ["dropcontact", "prospeo"]
    assert deckung["je_stufe"] == {"hunter_dropcontact": 1, "prospeo": 1, "info@": 0}
    assert [f["stufe"] for f in firmen_aus] == ["hunter_dropcontact", "prospeo"]
    # Stufe 2 wird nur fuer die Luecke gefragt, nicht fuer die schon gefundene Firma:
    assert prospeo.such_domains == ["b.de"]


def test_reihenfolge_der_stufen_ist_konfigurierbar():
    firmen = [_firma("a.de")]
    kunde = _kunde(anbieter_reihenfolge=["prospeo", "hunter_dropcontact"])
    prospeo = _FakeProspeo(
        personen_je_domain={"a.de": [_prospeo_person()]},
        mail_je_person_id={"p-1": {"email": "paula.prosp@a.de", "status": "VERIFIED",
                                   "verification_method": "SMTP", "schon_bezahlt": False}})
    leads, deckung, _ = source_leads(
        kunde, 10, "k", "k", "k",
        **_quellen(firmen, {"a.de": [_person("Anna")]}, {"Anna": "anna@a.de"}),
        prospeo_source=prospeo)
    # Prospeo steht vorn und liefert - Hunter/Dropcontact kommen nicht mehr dran.
    assert [l.source for l in leads] == ["prospeo"]
    assert deckung["je_stufe"]["prospeo"] == 1


def test_unbekannte_stufe_scheitert_mit_klarem_fehler():
    kunde = _kunde(anbieter_reihenfolge=["zauberquelle"])
    with pytest.raises(ValueError, match="zauberquelle"):
        source_leads(kunde, 10, "k", "k", "k",
                     **_quellen([_firma("a.de")], {}, {}))


def test_prospeo_stufe_ohne_quelle_scheitert_mit_klarem_fehler():
    kunde = _kunde(anbieter_reihenfolge=["prospeo"])
    with pytest.raises(ValueError, match="PROSPEO_API_KEY"):
        source_leads(kunde, 10, "k", "k", "k",
                     **_quellen([_firma("a.de")], {}, {}))


def test_info_mail_wird_vor_uebernahme_geprueft():
    hunter = _FakeHunterMitPruefer({}, {"info@a.de": "accept_all"})
    leads, deckung, firmen_aus = source_leads(
        _kunde(), 10, "k", "k", "k",
        apify_source=_FakeApify([_firma("a.de")]),
        hunter_source=hunter, dropcontact_source=_FakeDropcontact())
    assert [l.email for l in leads] == ["info@a.de"]
    assert hunter.geprueft == ["info@a.de"]
    assert firmen_aus[0]["ausgang"] == "info_fallback"
    assert firmen_aus[0]["info_pruefstatus"] == "accept_all"
    assert deckung["je_stufe"]["info@"] == 1


def test_ungueltige_info_mail_wird_verworfen():
    hunter = _FakeHunterMitPruefer({}, {"info@a.de": "invalid"})
    leads, deckung, firmen_aus = source_leads(
        _kunde(), 10, "k", "k", "k",
        apify_source=_FakeApify([_firma("a.de")]),
        hunter_source=hunter, dropcontact_source=_FakeDropcontact())
    assert leads == []
    assert firmen_aus[0]["ausgang"] == "info_ungueltig"
    assert deckung["firmen_mit_kontakt"] == 0


def test_fehler_bei_der_info_pruefung_verwendet_mail_nicht():
    hunter = _FakeHunterMitPruefer({}, pruef_fehler="Verifier 500")
    leads, deckung, firmen_aus = source_leads(
        _kunde(), 10, "k", "k", "k",
        apify_source=_FakeApify([_firma("a.de")]),
        hunter_source=hunter, dropcontact_source=_FakeDropcontact())
    # Zuverlaessigkeit zuerst: eine ungepruefte Adresse geht NICHT in den
    # Versand, die Firma endet als Fehler statt als stiller info@-Lead.
    assert leads == []
    assert firmen_aus[0]["ausgang"] == "fehler"


def test_ohne_pruefer_bleibt_altes_info_verhalten():
    # Alte Fakes/Quellen ohne email_pruefen: info@ wird wie bisher ungeprueft
    # uebernommen (Rueckwaerts-Kompatibilitaet der bestehenden Tests/Ablaeufe).
    leads, deckung, firmen_aus = source_leads(
        _kunde(), 10, "k", "k", "k",
        **_quellen([_firma("a.de")], {}, {}))
    assert [l.email for l in leads] == ["info@a.de"]
    assert firmen_aus[0]["ausgang"] == "info_fallback"


# --- Deutsche Titelformen (Messlauf-Funde 23.07.2026) ----------------------

def test_geschaeftsfuehrender_gesellschafter_passt_zu_geschaeftsfuehrer():
    # Live-Fund: "Geschäftsführender Gesellschafter" IST die Geschäftsführung,
    # wurde aber vom Wortgrenzen-Abgleich verfehlt ("geschäftsführender" ist
    # ein anderes Wort als "geschäftsführer").
    assert _rolle_passt("Geschäftsführender Gesellschafter", "Geschäftsführer")
    assert _rolle_passt("Geschäftsführende Gesellschafterin", "Geschäftsführer")
    assert _rolle_passt("Gründungspartner", "Geschäftsführer")


def test_prospeo_seniority_partner_zaehlt_als_entscheider():
    from pipeline.sourcing import _qualifiziert_prospeo
    partner = {"title": "Irgendwas ohne Rollentreffer", "seniority": "Partner"}
    angestellter = {"title": "IT-Administrator", "seniority": "Manager"}
    assert _qualifiziert_prospeo(partner, ["Geschäftsführer"])
    assert not _qualifiziert_prospeo(angestellter, ["Geschäftsführer"])


def test_product_owner_ist_kein_inhaber():
    # Messlauf-Fund: "Product Owner" matchte ueber das Wort "Owner" die
    # Geschäftsführer-Gruppe - eine Projektrolle, kein Inhaber.
    assert not _rolle_passt("Product Owner", "Geschäftsführer")
    assert not _rolle_passt("Senior Process Owner", "Inhaber")
    # Ein echtes "Owner" (allein oder kombiniert) bleibt ein Treffer:
    assert _rolle_passt("Owner", "Geschäftsführer")
    assert _rolle_passt("Owner / CEO", "Geschäftsführer")

"""Paying Dropcontact only for what we can use (Dafina, 29.09.2026).

Dropcontact refunds a row where it finds no address. It charges a row where
it finds one - also when that address sits on a catch-all domain and cannot
be checked, which our rule throws away. In zone 40 that was 8 of 73 people,
and two more were asked twice because their company is on the map with two
websites. Dafina chose three savings:

  1. one person on two sites of the same company is asked once; the second
     site only when the first gave no usable address;
  2. a catch-all domain is remembered, nobody there is asked again - that
     part lives in the register (tests/test_dropcontact_register.py);
  3. the addresses we pay for but cannot send to are kept, not thrown away.
"""
from pipeline.dropcontact_rounds import is_catch_all, paid_unusable, split_rounds


def _request(first, last, website, company=""):
    return {"first_name": first, "last_name": last, "website": website,
            "company": company}


def test_same_person_on_two_sites_of_one_company_is_asked_once():
    requests = [
        _request("Alexander", "Gazke", "http://www.fusion-it.services/",
                 "Fusion IT GmbH & Co. KG"),
        _request("Anna", "Muster", "https://a.de", "A GmbH"),
        _request("Alexander", "Gazke", "https://www.fusion-it-duesseldorf.de/",
                 "Fusion IT GmbH & Co. KG"),
    ]

    first, later = split_rounds(requests)

    assert first == [0, 1]
    assert later == {2: 0}          # asked only if request 0 finds nothing


def test_the_company_is_recognised_by_its_domain_under_another_name():
    requests = [
        _request("Markus", "Janhsen",
                 "https://www.wedoit.gmbh/it-dienstleister-duesseldorf/",
                 "Ihr IT Dienstleister Düsseldorf | we do IT Betriebs GmbH"),
        _request("Markus", "Janhsen", "http://www.wedoit-gmbh.de/", "we do IT"),
    ]

    assert split_rounds(requests) == ([0], {1: 0})


def test_the_same_name_at_two_different_companies_is_asked_twice():
    # A common name is no proof of one person. A contact lost at another
    # company costs more than the credit we would save.
    requests = [
        _request("Thomas", "Müller", "https://it-mueller-neuss.de",
                 "IT Müller Neuss"),
        _request("Thomas", "Müller", "https://pc-hilfe-dormagen.de",
                 "PC Hilfe Dormagen"),
    ]

    assert split_rounds(requests) == ([0, 1], {})


def test_everyday_words_in_two_names_do_not_make_one_company():
    requests = [
        _request("Jan", "Klein", "https://it-service-duesseldorf.de",
                 "IT Service Düsseldorf"),
        _request("Jan", "Klein", "https://edv-service-duesseldorf.de",
                 "EDV Service Düsseldorf"),
    ]

    assert split_rounds(requests) == ([0, 1], {})


def test_a_paid_catch_all_address_is_kept_but_not_sendable():
    sent = [_request("Hamid", "Nazari", "www.mylsp.de"),
            _request("Anna", "Muster", "a.de"),
            _request("Otto", "Leer", "leer.de")]
    rows = [
        {"first_name": "Hamid", "last_name": "Nazari", "email": [
            {"email": "hamid.nazari@mylsp.de", "qualification": "catch-all@pro"}]},
        {"first_name": "Anna", "last_name": "Muster", "email": [
            {"email": "anna@a.de", "qualification": "nominative@pro"}]},
        {"first_name": "Otto", "last_name": "Leer", "email": []},
    ]

    assert paid_unusable(sent, rows) == [
        {"first_name": "Hamid", "last_name": "Nazari", "website": "www.mylsp.de",
         "email": "hamid.nazari@mylsp.de", "qualification": "catch-all@pro"}]


def test_generic_and_private_addresses_are_kept_invalid_ones_are_not():
    sent = [_request("Ida", "Info", "info-firma.de"),
            _request("Paul", "Privat", "p.de"),
            _request("Ina", "Falsch", "f.de")]
    rows = [
        {"email": [{"email": "info@info-firma.de", "qualification": "generic@pro"}]},
        {"email": [{"email": "paul@gmail.com", "qualification": "nominative@perso"}]},
        {"email": [{"email": "", "qualification": "invalid@pro"}]},
    ]

    kept = paid_unusable(sent, rows)

    assert [a["qualification"] for a in kept] == ["generic@pro", "nominative@perso"]


def test_both_spellings_of_catch_all_count():
    # The API answered "catch-all@pro" on 29.09.2026, its docs write "catch_all".
    assert is_catch_all("catch-all@pro")
    assert is_catch_all("catch_all@pro")
    assert not is_catch_all("nominative@pro")
    assert not is_catch_all("")

"""Batch mode: many people in one request instead of one request each.

The whole point of the batch is speed, and the whole risk of the batch is
that an address ends up at the wrong company. These tests pin the
mapping: right person -> right address, and a shifted answer must stop
the run instead of handing out strangers' addresses.
"""
import pytest

from pipeline.sources.dropcontact import DropcontactSource, ENRICH_URL
from tests.test_dropcontact import FakeResponse, FakeSession, abgegeben, \
    noch_nicht_fertig, email


def zeile(vorname, nachname, *emails):
    return {"first_name": vorname, "last_name": nachname, "email": list(emails)}


def fertig_mit(*zeilen):
    return FakeResponse(200, {"error": False, "success": True, "data": list(zeilen)})


ANFRAGEN = [
    {"first_name": "Anna", "last_name": "Muster",
     "website": "https://a.de", "company": "A GmbH"},
    {"first_name": "Bernd", "last_name": "Beispiel",
     "website": "https://b.de", "company": "B GmbH"},
    {"first_name": "Clara", "last_name": "Cent",
     "website": "https://c.de", "company": "C GmbH"},
]


def test_eine_anfrage_fuer_die_ganze_liste():
    # Der Sinn des Batches: EIN POST statt drei.
    session = FakeSession([
        abgegeben(),
        fertig_mit(zeile("Anna", "Muster", email("anna@a.de")),
                   zeile("Bernd", "Beispiel", email("bernd@b.de")),
                   zeile("Clara", "Cent", email("clara@c.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(ANFRAGEN)

    assert len(session.posts) == 1
    assert session.posts[0]["url"] == ENRICH_URL
    assert len(session.posts[0]["json"]["data"]) == 3
    assert [e["email"] for e in ergebnis] == \
        ["anna@a.de", "bernd@b.de", "clara@c.de"]


def test_jede_adresse_landet_bei_ihrer_person():
    session = FakeSession([
        abgegeben(),
        fertig_mit(zeile("Anna", "Muster", email("anna@a.de")),
                   zeile("Bernd", "Beispiel", email("bernd@b.de")),
                   zeile("Clara", "Cent", email("clara@c.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(ANFRAGEN)

    for anfrage, treffer in zip(ANFRAGEN, ergebnis):
        vorname, domain = treffer["email"].split("@")
        assert vorname == anfrage["first_name"].lower()
        assert anfrage["website"].endswith(domain)


def test_verschobene_antwort_bricht_ab_statt_falsche_adressen_zu_liefern():
    # Der gefaehrlichste Fall: Dropcontact antwortet in anderer Reihenfolge.
    # Dann bekaeme jede Firma die Adresse einer fremden Person. Erkennbar
    # daran, dass weder Name noch Domain der Zeile zur Anfrage passen.
    def fremd(vorname, nachname, domain, mail):
        z = zeile(vorname, nachname, email(mail))
        z["website"] = domain
        return z

    session = FakeSession([
        abgegeben(),
        fertig_mit(fremd("Clara", "Cent", "www.c.de", "clara@c.de"),
                   fremd("Anna", "Muster", "www.a.de", "anna@a.de"),
                   fremd("Bernd", "Beispiel", "www.b.de", "bernd@b.de"))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    with pytest.raises(RuntimeError, match="weder Name noch Domain"):
        quelle.email_bauen_viele(ANFRAGEN)


def test_vertauschter_vor_und_nachname_ist_dieselbe_person():
    # Echter Fall vom 11.08.2026: "Peter-Christoph Haider" kam als
    # "Haider Peter-Christoph" zurueck - Dropcontact haelt den Nachnamen
    # fuer den Vornamen. Gleiche Person, gleiche Firma: kein Abbruch,
    # aber ein Hinweis, weil die Adresse aus dem falschen Namensteil
    # gebaut sein kann.
    anfrage = [{"first_name": "Peter-Christoph", "last_name": "Haider",
                "website": "https://www.bell.de", "company": "Bell GmbH"}]
    getauscht = zeile("Haider", "Peter-Christoph", email("peter@bell.net"))
    getauscht["website"] = "www.bell.de"
    session = FakeSession([abgegeben(), fertig_mit(getauscht)])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(anfrage)

    assert ergebnis[0]["email"] == "peter@bell.net"
    assert "Haider Peter-Christoph" in ergebnis[0]["hinweis"]


def test_voellig_neuer_name_bei_gleicher_domain_gilt_als_dieselbe_zeile():
    # Dropcontact korrigiert manchmal beide Felder. Solange die Firma
    # dieselbe ist, ist es unsere Zeile - mit Hinweis zur Kontrolle.
    anfrage = [{"first_name": "Anna", "last_name": "Muster",
                "website": "https://a.de", "company": "A GmbH"}]
    anders = zeile("Annemarie", "Musterfrau", email("annemarie@a.de"))
    anders["website"] = "a.de"
    session = FakeSession([abgegeben(), fertig_mit(anders)])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(anfrage)

    assert ergebnis[0]["email"] == "annemarie@a.de"
    assert ergebnis[0]["hinweis"]


def test_passender_name_bekommt_keinen_hinweis():
    session = FakeSession([
        abgegeben(), fertig_mit(zeile("Anna", "Muster", email("anna@a.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    assert "hinweis" not in quelle.email_bauen_viele([ANFRAGEN[0]])[0]


def test_fehlende_zeilen_brechen_ab():
    session = FakeSession([
        abgegeben(),
        fertig_mit(zeile("Anna", "Muster", email("anna@a.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    with pytest.raises(RuntimeError, match="Zuordnung unsicher"):
        quelle.email_bauen_viele(ANFRAGEN)


def test_korrigierte_schreibweise_gilt_nicht_als_verschiebung():
    # Dropcontact putzt Namen ("bernd" -> "Bernd"). Ein einzelnes
    # korrigiertes Feld ist normal und darf den Lauf nicht abbrechen.
    session = FakeSession([
        abgegeben(),
        fertig_mit(zeile("Anna", "Muster", email("anna@a.de")),
                   zeile("Bernd", "Beispiél", email("bernd@b.de")),
                   zeile("Clara", "Cent", email("clara@c.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(ANFRAGEN)

    assert ergebnis[1]["email"] == "bernd@b.de"


def test_nur_geprueft_persoenliche_adressen_zaehlen():
    # Gleiche Qualitaetsregel wie im Einzelbetrieb: info@ und private
    # Adressen sind keine Entscheider-Mail.
    session = FakeSession([
        abgegeben(),
        fertig_mit(zeile("Anna", "Muster", email("info@a.de", "generic@pro")),
                   zeile("Bernd", "Beispiel", email("bernd@gmail.com", "nominative@perso")),
                   zeile("Clara", "Cent", email("clara@c.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(ANFRAGEN)

    assert ergebnis[0] is None
    assert ergebnis[1] is None
    assert ergebnis[2]["email"] == "clara@c.de"


def test_personen_ohne_namen_werden_nicht_mitgeschickt():
    anfragen = [
        {"first_name": "", "last_name": "", "website": "https://a.de"},
        {"first_name": "Clara", "last_name": "Cent", "website": "https://c.de"},
    ]
    session = FakeSession([
        abgegeben(), fertig_mit(zeile("Clara", "Cent", email("clara@c.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele(anfragen)

    assert len(session.posts[0]["json"]["data"]) == 1
    assert ergebnis[0] is None
    assert ergebnis[1]["email"] == "clara@c.de"


def test_wartet_bis_der_batch_fertig_ist():
    session = FakeSession([
        abgegeben(), noch_nicht_fertig(), noch_nicht_fertig(),
        fertig_mit(zeile("Anna", "Muster", email("anna@a.de")))])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    ergebnis = quelle.email_bauen_viele([ANFRAGEN[0]])

    assert ergebnis[0]["email"] == "anna@a.de"
    assert len(session.gets) == 3


def test_leere_liste_kostet_keine_anfrage():
    session = FakeSession([])
    quelle = DropcontactSource("key", session=session, wartezeit=0, batch_wartezeit=0)

    assert quelle.email_bauen_viele([]) == []
    assert session.posts == []

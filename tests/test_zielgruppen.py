"""Zielgruppen: derselbe Zonen-Ablauf fuer mehr als eine Branche
(Dafina, 15.10.2026: "ky eshte jo IT, AMA TNJEJTIN SEN duhesh me bo").

Die Kette war an drei Stellen auf eine einzige Zielgruppe verdrahtet:
die Suchbegriffe, der Profil-Prompt und der Name der Listen. Hier liegen
sie beisammen, eine Zeile je Zielgruppe, damit die IT-Arbeit unberuehrt
bleibt und eine neue Branche nichts kopieren muss.

Die IT-Zielgruppe LIEST ihre Begriffe und ihren Prompt dort, wo sie
schon stehen. Eine zweite Kopie wuerde mit der Zeit auseinanderlaufen,
und dann sammelt die Kette nach anderen Worten als sie urteilt.
"""
import pytest

from pipeline import zonen
from pipeline.branchen_filter import SYSTEM_PROMPT
from pipeline.zielgruppen import ZIELGRUPPEN, zielgruppe


def test_it_bleibt_wie_sie_war():
    z = zielgruppe("it")
    assert list(z.suchbegriffe) == list(zonen.SUCHBEGRIFFE)
    assert z.system_prompt == SYSTEM_PROMPT
    assert z.listen_prefix == "IT-Liste-Emails-"


def test_ohne_angabe_ist_es_die_it_zielgruppe():
    """Jeder alte Aufruf ohne Zielgruppe muss weiter die IT treffen."""
    assert zielgruppe() is zielgruppe("it")


def test_prozessberater_hat_dafinas_begriffe():
    z = zielgruppe("prozess")
    begriffe = list(z.suchbegriffe)
    # Dafinas Liste vom 15.10.2026, ohne die doppelte "Prozessoptimierung"
    assert len(begriffe) == 21
    assert len(set(begriffe)) == 21, "doppelte Begriffe kosten Geld"
    for erwartet in ("Prozessberater", "Prozessberatung", "Prozessmanagement",
                     "Geschäftsprozessanalyse", "REFA Consulting",
                     "REFA Berater", "REFA Beratung",
                     "Prozess- und Organisationsberatung"):
        assert erwartet in begriffe, erwartet


def test_prozess_prompt_fragt_nach_prozessberatung_nicht_nach_it():
    z = zielgruppe("prozess")
    p = z.system_prompt
    assert "IT" not in p.replace("IT-Dienstleister", ""), \
        "der IT-Prompt darf hier nicht durchschlagen"
    for wort in ("Prozess", "Organisation", "REFA", "passt"):
        assert wort in p, wort


def test_beide_zielgruppen_pruefen_wettbewerber():
    """Dafina, 15.10.2026: "po vlen automatizimi edhe ketu" - eine Firma,
    die selbst Automationen anbietet, bleibt auch hier draussen."""
    assert zielgruppe("it").wettbewerber_pruefung is True
    assert zielgruppe("prozess").wettbewerber_pruefung is True


def test_jede_zielgruppe_hat_ihren_eigenen_listen_namen():
    """Zwei Zielgruppen im selben Postleitzahl-Gebiet duerfen sich die
    Listen nicht ueberschreiben - die Zonen-Nummer allein reicht nicht."""
    prefixe = [z.listen_prefix for z in ZIELGRUPPEN.values()]
    assert len(prefixe) == len(set(prefixe))
    for p in prefixe:
        assert p.endswith("-Liste-Emails-"), p


def test_unbekannte_zielgruppe_ist_ein_fehler():
    """Keine stille Rueckkehr zur IT: wer sich bei der Zielgruppe
    vertippt, sammelt sonst die falsche Branche und zahlt dafuer."""
    with pytest.raises(KeyError, match="prozesse"):
        zielgruppe("prozesse")


def test_jede_zielgruppe_hat_ihre_osm_merkmale():
    """Overpass sucht nach Karten-Merkmalen, nicht nach Worten.

    Fuer die IT ist das `office=it`. Mit demselben Merkmal wuerde die
    Prozess-Zielgruppe IT-Firmen einsammeln - also die falsche Branche,
    und der Profil-Filter wuerfe sie danach alle weg: die freie zweite
    Quelle waere still wirkungslos.
    """
    from pipeline.sources.overpass import STANDARD_MERKMALE

    assert tuple(zielgruppe("it").osm_merkmale) == tuple(STANDARD_MERKMALE)
    prozess = tuple(zielgruppe("prozess").osm_merkmale)
    assert ("office", "consulting") in prozess
    assert ("office", "it") not in prozess


def test_der_ordner_name_traegt_die_zielgruppe():
    """Die Listen-Werkzeuge suchen ihre Lauf-Ordner mit einem Muster.

    Am 15.10.2026 hiess das Muster "zona33-dropcontact-*" - ohne
    Zielgruppe. Fuer die Prozessberater fand es damit den IT-Ordner vom
    September, warf dessen Firmen als "ausserhalb der Zone" weg und
    schrieb eine LEERE Liste, ohne sich zu beschweren. Acht Zonen,
    39 gefundene E-Mails, null Zeilen.
    """
    it, pr = zielgruppe("it"), zielgruppe("prozess")
    assert it.lauf_glob("33", "dropcontact") == "zona33-dropcontact-*"
    assert pr.lauf_glob("33", "dropcontact") == "zona33-prozess-dropcontact-*"
    # und das IT-Muster darf den Prozess-Ordner NICHT fangen
    import fnmatch
    assert not fnmatch.fnmatch("zona33-prozess-dropcontact-2026-10-15",
                               it.lauf_glob("33", "dropcontact"))
    assert fnmatch.fnmatch("zona33-dropcontact-2026-09-04",
                           it.lauf_glob("33", "dropcontact"))

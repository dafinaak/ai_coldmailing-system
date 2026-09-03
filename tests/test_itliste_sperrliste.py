"""The final list is the last gate - it must check the blocklist itself.

Found on 03.09.2026: the FERTIG lists of zones 33 and 34 contained six
firms that stand in sperrliste-global.yaml - kisocon, Mibema, netgo tax,
BLUVIT, GRAPHISOFT Kassel, elastify. They are the software vendors Dafina
had blocked on 31.08.2026.

How they got through: the blocklist was only applied in the Dropcontact
step, before paying. Those batches ran on 28.08, before the entries
existed, and the list builder reads the stored result without ever asking
the blocklist again. A blocklist that only runs before payment protects
the budget, not the recipient.

The project rule says the blocklist acts at the last gate before Instantly.
The final list IS that gate, so it filters too - and says out loud what it
removed, because a silent drop is how a list quietly gets shorter without
anyone knowing why.
"""
import pytest

from pipeline.sperrliste_pruefung import ist_gesperrt, gesperrte_domains


EINTRAEGE = [{"domain": "mibema-software.de"}, {"domain": "*.bluvit.de"},
             {"domain": "elastify.net"}]


def test_gesperrte_domain_wird_erkannt():
    domains = gesperrte_domains(EINTRAEGE)
    assert ist_gesperrt("https://www.mibema-software.de/impressum", domains)
    assert ist_gesperrt("mibema-software.de", domains)


def test_subdomain_faellt_mit():
    """Wer die Domain sperrt, meint die Firma - nicht nur die eine URL."""
    domains = gesperrte_domains(EINTRAEGE)
    assert ist_gesperrt("https://shop.bluvit.de", domains)
    assert ist_gesperrt("https://bluvit.de", domains)


def test_fremde_domain_bleibt_frei():
    domains = gesperrte_domains(EINTRAEGE)
    assert not ist_gesperrt("https://www.elastify-anders.de", domains)
    assert not ist_gesperrt("https://irgendwas.de", domains)


def test_aehnlicher_name_ist_keine_sperre():
    """'nicht-elastify.net' ist eine andere Firma als 'elastify.net'."""
    domains = gesperrte_domains(EINTRAEGE)
    assert not ist_gesperrt("https://nicht-elastify.net", domains)


def test_ohne_webseite_wird_nicht_gesperrt():
    """Ohne Domain koennen wir nichts beweisen - und was wir nicht
    beweisen koennen, werfen wir nicht raus."""
    domains = gesperrte_domains(EINTRAEGE)
    assert not ist_gesperrt("", domains)
    assert not ist_gesperrt(None, domains)


def test_leere_sperrliste_sperrt_nichts():
    assert not ist_gesperrt("https://mibema-software.de", gesperrte_domains([]))


def test_eintraege_ohne_domain_werden_uebergangen():
    """Die Sperrliste enthaelt auch Eintraege mit nur einer E-Mail. Die
    duerfen die Domain-Pruefung nicht durcheinanderbringen."""
    domains = gesperrte_domains([{"email": "wer@auch.de"}, {"domain": ""},
                                 {"domain": "bluvit.de"}])
    assert domains == {"bluvit.de"}
    assert ist_gesperrt("https://bluvit.de", domains)

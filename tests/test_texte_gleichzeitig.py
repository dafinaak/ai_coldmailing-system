"""Die Texte muessen fuer mehrere Kontakte gleichzeitig entstehen.

Gemessen am 17.08.2026 an einem echten Lauf: Adress-Suche 3:45, Texten
3:18 - die Haelfte der Gesamtzeit. Getextet wurde ein Kontakt nach dem
anderen, obwohl die Zeit fast vollstaendig aus Warten auf die KI besteht.

Geprueft wird beides: dass wirklich parallel gearbeitet wird UND dass
Reihenfolge und Fehlerbehandlung dabei unveraendert bleiben.
"""
import threading
import time

import pytest

from pipeline import __main__ as cli


def _behalten(anzahl):
    return [{"first_name": "Max", "last_name": f"Muster{i}",
             "email": f"max{i}@firma{i}.de", "company": f"Firma {i}",
             "title": "Geschäftsführer", "website": f"https://firma{i}.de",
             "source": "impressum"} for i in range(anzahl)]


class LangsamesTexten:
    """Zaehlt, wie viele Kontakte gleichzeitig unterwegs sind."""

    def __init__(self, wartezeit=0.2, fehler_bei=None):
        self.wartezeit = wartezeit
        self.fehler_bei = fehler_bei
        self.gleichzeitig = 0
        self.hoechststand = 0
        self._schloss = threading.Lock()

    def __call__(self, lead, kunde, ki, webseiten_text, check):
        with self._schloss:
            self.gleichzeitig += 1
            self.hoechststand = max(self.hoechststand, self.gleichzeitig)
        try:
            time.sleep(self.wartezeit)
            if self.fehler_bei and self.fehler_bei in lead.email:
                raise ValueError("Webseite nicht lesbar")
            return True, "", {"betreff": f"B {lead.company}",
                              "mail_1": "M", "follow_up_1": "F1",
                              "follow_up_2": "F2"}, None
        finally:
            with self._schloss:
                self.gleichzeitig -= 1


@pytest.fixture(autouse=True)
def ohne_netz(monkeypatch):
    monkeypatch.setattr(cli, "fetch_text", lambda url: "Webseiten-Text")
    monkeypatch.setattr(cli, "KI", lambda *a, **k: object())


def test_kontakte_werden_gleichzeitig_getextet(monkeypatch):
    texten = LangsamesTexten(wartezeit=0.2)
    monkeypatch.setattr(cli, "personalisiere_mit_nachbesserung", texten)

    start = time.monotonic()
    cli._texte_schreiben(_behalten(5), kunde=None, check=None)
    dauer = time.monotonic() - start

    # Nacheinander waeren das 5 x 0,2s = 1,0s.
    assert dauer < 0.7, f"zu langsam: {dauer:.2f}s"
    assert texten.hoechststand > 1, "es lief nur ein Kontakt zur Zeit"


def test_reihenfolge_bleibt_die_der_kontaktliste(monkeypatch):
    monkeypatch.setattr(cli, "personalisiere_mit_nachbesserung",
                        LangsamesTexten(wartezeit=0.02))

    ergebnis = cli._texte_schreiben(_behalten(6), kunde=None, check=None)

    assert [lead.email for lead, _ in ergebnis] == \
        [f"max{i}@firma{i}.de" for i in range(6)]


def test_ein_fehler_reisst_den_lauf_nicht_mit(monkeypatch):
    monkeypatch.setattr(cli, "personalisiere_mit_nachbesserung",
                        LangsamesTexten(wartezeit=0.02, fehler_bei="max2@"))

    ergebnis = cli._texte_schreiben(_behalten(4), kunde=None, check=None)

    nach_mail = {lead.email: ok for lead, (ok, _, _) in ergebnis}
    assert nach_mail["max2@firma2.de"] is False
    assert nach_mail["max0@firma0.de"] is True
    assert len(ergebnis) == 4


def test_grund_des_fehlers_bleibt_erhalten(monkeypatch):
    monkeypatch.setattr(cli, "personalisiere_mit_nachbesserung",
                        LangsamesTexten(wartezeit=0.01, fehler_bei="max0@"))

    (_, (ok, grund, texte)), *_ = cli._texte_schreiben(
        _behalten(2), kunde=None, check=None)

    assert ok is False
    assert "Webseite nicht lesbar" in grund
    assert texte == {}


def test_leere_liste_bricht_nicht(monkeypatch):
    monkeypatch.setattr(cli, "personalisiere_mit_nachbesserung",
                        LangsamesTexten())

    assert cli._texte_schreiben([], kunde=None, check=None) == []


def test_jeder_thread_bekommt_eine_eigene_ki(monkeypatch):
    # Die KI haelt eine HTTP-Sitzung; die ist fuer gleichzeitige Nutzung
    # nicht ausdruecklich freigegeben.
    gesehen, schloss = [], threading.Lock()

    def merken(lead, kunde, ki, webseiten_text, check):
        with schloss:
            gesehen.append(ki)
        time.sleep(0.05)
        return True, "", {"betreff": "B", "mail_1": "M",
                          "follow_up_1": "F1", "follow_up_2": "F2"}, None

    monkeypatch.setattr(cli, "personalisiere_mit_nachbesserung", merken)
    cli._texte_schreiben(_behalten(4), kunde=None, check=None)

    assert len({id(k) for k in gesehen}) > 1, "alle teilten sich eine KI"

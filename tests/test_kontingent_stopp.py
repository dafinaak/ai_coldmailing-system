"""Ein leeres Monats-Kontingent wird nur EINMAL erfragt.

Beobachtet am 14.08.2026 im laufenden Betrieb: Hunters Prüf-Kontingent war
erschöpft. Trotzdem fragte jede weitere Firma erneut - und weil der Client
den 429er für eine Überlast hält, versuchte er es je Firma dreimal mit
Wartezeit dazwischen. Zehn Firmen holten so nacheinander dieselbe längst
bekannte Absage ein.
"""
import pytest

from pipeline.sourcing import KontingentLeer, _mit_kontingent_stopp, fehler_satz


class Anbieter:
    """Zählt, wie oft wirklich angefragt wurde."""

    def __init__(self, fehler):
        self.anfragen = 0
        self.fehler = fehler

    def pruefen(self, email):
        self.anfragen += 1
        if self.fehler:
            raise self.fehler
        return {"status": "valid", "score": 90}


def test_nach_der_ersten_absage_wird_nicht_mehr_gefragt():
    anbieter = Anbieter(RuntimeError(
        "Hunter antwortet mit 429: too_many_requests"))
    pruefen = _mit_kontingent_stopp(anbieter.pruefen)

    with pytest.raises(RuntimeError):
        pruefen("eins@firma.de")
    for adresse in ("zwei@firma.de", "drei@firma.de", "vier@firma.de"):
        with pytest.raises(KontingentLeer):
            pruefen(adresse)

    assert anbieter.anfragen == 1


def test_die_firmen_danach_bekommen_denselben_grund():
    # Wichtig: nicht anfragen heisst nicht "stillschweigend durchlassen".
    # Die Firma muss weiterhin als ungeprueft gelten.
    anbieter = Anbieter(RuntimeError("reached the limit"))
    pruefen = _mit_kontingent_stopp(anbieter.pruefen)

    with pytest.raises(RuntimeError):
        pruefen("eins@firma.de")
    try:
        pruefen("zwei@firma.de")
    except KontingentLeer as fehler:
        assert "Kontingent" in fehler_satz(fehler)
    else:
        pytest.fail("zweite Anfrage haette abgelehnt werden muessen")


def test_andere_fehler_stoppen_nichts():
    # Ein einzelner Verbindungsabbruch ist kein leeres Kontingent - die
    # naechste Firma darf normal gefragt werden.
    anbieter = Anbieter(RuntimeError("Verbindung abgebrochen"))
    pruefen = _mit_kontingent_stopp(anbieter.pruefen)

    for adresse in ("eins@firma.de", "zwei@firma.de", "drei@firma.de"):
        with pytest.raises(RuntimeError):
            pruefen(adresse)

    assert anbieter.anfragen == 3


def test_ohne_pruefer_bleibt_es_bei_none():
    assert _mit_kontingent_stopp(None) is None


def test_erfolgreiche_pruefung_wird_durchgereicht():
    anbieter = Anbieter(None)
    pruefen = _mit_kontingent_stopp(anbieter.pruefen)

    assert pruefen("gut@firma.de") == {"status": "valid", "score": 90}
    assert pruefen("auch-gut@firma.de")["status"] == "valid"
    assert anbieter.anfragen == 2

"""Tote Webseiten duerfen nicht das Siebenfache der Wartezeit kosten.

Gemessen am 14.08.2026: Je Firma werden bis zu sieben Adressen probiert.
Antwortet der Server ueberhaupt nicht, lief das Programm trotzdem alle
sieben durch und wartete jedes Mal die volle Zeit ab. Ausserdem teilen sich
seit demselben Tag mehrere Threads dieselbe Quelle - jeder braucht seine
eigene HTTP-Sitzung.
"""
import threading

from pipeline.sources.impressum import ImpressumQuelle


class FakeAntwort:
    def __init__(self, text="", status=200):
        self.text = text
        self.status_code = status


class ZaehlendeSession:
    """Zaehlt Abrufe; wirft fuer bestimmte Hosts wie ein toter Server."""

    def __init__(self, tot=(), text=""):
        self.tot = tot
        self.text = text
        self.aufrufe = []

    def get(self, url, headers=None, timeout=None):
        self.aufrufe.append(url)
        if any(host in url for host in self.tot):
            raise OSError("Name oder Dienst nicht bekannt")
        return FakeAntwort(self.text)


IMPRESSUM_HTML = ("<html><body>" + "Impressum Geschäftsführer Max Muster. "
                  * 20 + "</body></html>")


def test_toter_server_wird_nach_zwei_versuchen_aufgegeben():
    session = ZaehlendeSession(tot=("tot.de",))
    quelle = ImpressumQuelle(ki=None, session=session, renderer=lambda url: None)

    assert quelle.impressum_text("https://tot.de") is None
    # Vorher waren es sieben Adressen plus Startseite.
    assert len(session.aufrufe) == 2, session.aufrufe


def test_erreichbarer_server_wird_weiter_durchprobiert():
    # 404 ist kein toter Server: der naechste Pfad kann trotzdem passen.
    class NurImpressumDa(ZaehlendeSession):
        def get(self, url, headers=None, timeout=None):
            self.aufrufe.append(url)
            if url.endswith("/impressum"):
                return FakeAntwort("", status=404)
            return FakeAntwort(IMPRESSUM_HTML)

    session = NurImpressumDa()
    quelle = ImpressumQuelle(ki=None, session=session, renderer=lambda url: None)

    text = quelle.impressum_text("https://lebt.de")

    assert text and "Impressum" in text
    assert len(session.aufrufe) >= 2


def test_ein_einzelner_aussetzer_bricht_nicht_ab():
    class ErsterFehlerDannGut(ZaehlendeSession):
        def get(self, url, headers=None, timeout=None):
            self.aufrufe.append(url)
            if len(self.aufrufe) == 1:
                raise OSError("kurzer Aussetzer")
            return FakeAntwort(IMPRESSUM_HTML)

    session = ErsterFehlerDannGut()
    quelle = ImpressumQuelle(ki=None, session=session, renderer=lambda url: None)

    assert quelle.impressum_text("https://wackelt.de") is not None


def test_jeder_thread_bekommt_seine_eigene_sitzung():
    # Ohne feste Session baut die Quelle je Thread eine eigene - mehrere
    # Firmen laufen seit 14.08.2026 gleichzeitig durch dieselbe Quelle.
    quelle = ImpressumQuelle(ki=None, renderer=lambda url: None)
    # Die Objekte selbst festhalten, nicht nur ihre id(): ein beendeter
    # Thread gibt seine Sitzung sonst frei und die naechste bekommt
    # dieselbe Speicheradresse - der Test wuerde faelschlich meckern.
    gesehen = []

    def merken():
        gesehen.append(quelle.session)

    faeden = [threading.Thread(target=merken) for _ in range(3)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join()

    assert len({id(s) for s in gesehen}) == 3, "Threads teilen sich eine Sitzung"


def test_uebergebene_sitzung_bleibt_die_eine():
    session = ZaehlendeSession()
    quelle = ImpressumQuelle(ki=None, session=session)

    assert quelle.session is session

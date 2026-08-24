"""Tests für Webseiten-Lesen in die Tiefe und die Automatisierungs-KI.

Kein Netz, keine KI, keine Credits - alles nachgebaut.
"""
import json

import pytest

from pipeline import automation_llm
from pipeline.website_tiefe import (
    links_auswaehlen, seiten_lesen, sichtbarer_text)


class FakeAntwort:
    def __init__(self, text, status_code=200):
        self.text, self.status_code = text, status_code


class FakeSession:
    """Liefert HTML je URL; alles Unbekannte ist ein 404."""

    def __init__(self, seiten):
        self.seiten = seiten
        self.geholt = []

    def get(self, url, timeout=None, headers=None):
        self.geholt.append(url)
        if url in self.seiten:
            return FakeAntwort(self.seiten[url])
        return FakeAntwort("", 404)


START = """<html><body>
  <a href="/impressum">Impressum</a>
  <a href="/leistungen/">Leistungen</a>
  <a href="/ueber-uns">Über uns</a>
  <a href="/karriere">Karriere</a>
  <a href="/prospekt.pdf">Prospekt</a>
  <a href="https://fremde-seite.de/leistungen">Fremd</a>
  <script>var x = "unsichtbar";</script>
  <p>Wir betreuen die IT von Firmen.</p>
</body></html>"""


# ------------------------------------------------------------ Text lesen

def test_skripte_und_tags_fliegen_raus():
    text = sichtbarer_text("<p>Hallo</p><script>böse()</script><b>Welt</b>")
    assert "Hallo" in text and "Welt" in text
    assert "böse" not in text


def test_html_entities_werden_aufgeloest():
    assert "Über uns" in sichtbarer_text("<p>&Uuml;ber uns</p>")


# --------------------------------------------------------- Links auswählen

def test_leistungsseiten_werden_bevorzugt():
    links = links_auswaehlen(START, "https://beispiel.de", max_seiten=4)
    assert "https://beispiel.de/leistungen/" == links[0]


def test_impressum_karriere_und_dateien_bleiben_draussen():
    links = links_auswaehlen(START, "https://beispiel.de", max_seiten=10)
    text = " ".join(links)
    assert "impressum" not in text
    assert "karriere" not in text
    assert ".pdf" not in text


def test_fremde_domains_bleiben_draussen():
    links = links_auswaehlen(START, "https://beispiel.de", max_seiten=10)
    assert all("fremde-seite.de" not in link for link in links)


def test_max_seiten_wird_eingehalten():
    assert len(links_auswaehlen(START, "https://beispiel.de",
                                max_seiten=1)) == 1


# ------------------------------------------------------------ Seiten lesen

def test_startseite_und_unterseite_werden_gelesen(tmp_path):
    session = FakeSession({
        "https://beispiel.de": START,
        "https://beispiel.de/leistungen/":
            "<p>" + ("Wir bieten Managed Services und IT-Support. " * 20) + "</p>",
    })
    ergebnis = seiten_lesen("beispiel.de", tmp_path, session=session,
                            max_seiten=2)
    assert ergebnis["status"] == "ok"
    assert len(ergebnis["seiten"]) == 2
    assert "Managed Services" in ergebnis["text"]
    # Die Quellenangabe muss mit im Text stehen, sonst kann die KI nicht
    # sagen, WO sie etwas gefunden hat.
    assert "[Quelle: https://beispiel.de/leistungen/]" in ergebnis["text"]


def test_unerreichbare_startseite_ist_nicht_erreichbar(tmp_path):
    ergebnis = seiten_lesen("tot.de", tmp_path, session=FakeSession({}))
    assert ergebnis["status"] == "nicht_erreichbar"
    assert ergebnis["text"] == ""


def test_ohne_adresse_gibt_es_keine_webseite(tmp_path):
    assert seiten_lesen("", tmp_path)["status"] == "keine_webseite"


def test_zu_duenne_seite_gilt_als_leer(tmp_path):
    session = FakeSession({"https://duenn.de": "<p>Hallo</p>"})
    assert seiten_lesen("duenn.de", tmp_path,
                        session=session)["status"] == "leer"


def test_kurze_unterseiten_werden_uebersprungen(tmp_path):
    session = FakeSession({
        "https://beispiel.de": START,
        "https://beispiel.de/leistungen/": "<p>zu kurz</p>",
    })
    ergebnis = seiten_lesen("beispiel.de", tmp_path, session=session)
    assert [s["url"] for s in ergebnis["seiten"]] == ["https://beispiel.de"]


# ---------------------------------------------------------------- Cache

def test_innerhalb_der_ttl_wird_nicht_neu_geholt(tmp_path):
    seiten = {"https://beispiel.de": START}
    erste = FakeSession(seiten)
    seiten_lesen("beispiel.de", tmp_path, session=erste, jetzt=lambda: 1000.0)
    zweite = FakeSession(seiten)
    ergebnis = seiten_lesen("beispiel.de", tmp_path, session=zweite,
                            jetzt=lambda: 1000.0 + 86400, ttl_tage=14)
    assert zweite.geholt == []
    assert ergebnis["aus_cache"] is True


def test_nach_ablauf_der_ttl_wird_neu_geholt(tmp_path):
    seiten = {"https://beispiel.de": START}
    seiten_lesen("beispiel.de", tmp_path, session=FakeSession(seiten),
                 jetzt=lambda: 1000.0)
    zweite = FakeSession(seiten)
    seiten_lesen("beispiel.de", tmp_path, session=zweite,
                 jetzt=lambda: 1000.0 + 86400 * 20, ttl_tage=14)
    assert zweite.geholt


def test_cache_kann_abgeschaltet_werden(tmp_path):
    seiten = {"https://beispiel.de": START}
    seiten_lesen("beispiel.de", tmp_path, session=FakeSession(seiten),
                 jetzt=lambda: 1000.0, cache=False)
    zweite = FakeSession(seiten)
    seiten_lesen("beispiel.de", tmp_path, session=zweite,
                 jetzt=lambda: 1000.0, cache=False)
    assert zweite.geholt


# ------------------------------------------------------ Automatisierungs-KI

class FakeKI:
    def __init__(self, antwort):
        self.antwort, self.gefragt = antwort, []

    def frage(self, system, prompt):
        self.gefragt.append({"system": system, "prompt": prompt})
        if isinstance(self.antwort, Exception):
            raise self.antwort
        return self.antwort


def seiten_ok(text="Wir bieten Prozessautomatisierung. " * 20):
    return {"text": f"[Quelle: https://beispiel.de/leistungen/]\n{text}",
            "seiten": [{"url": "https://beispiel.de/leistungen/",
                        "zeichen": len(text)}],
            "status": "ok"}


def test_klare_ja_antwort_wird_uebernommen():
    ki = FakeKI(json.dumps({
        "automation_status": "YES", "confidence": 0.9,
        "reason": "bietet RPA an", "evidence": "Wir bieten RPA",
        "source_url": "https://beispiel.de/leistungen/"}))
    urteil = automation_llm.klassifizieren({"name": "X"}, seiten_ok(), ki)
    assert urteil["automation_status"] == "YES"
    assert urteil["confidence"] == 0.9
    assert urteil["source_url"] == "https://beispiel.de/leistungen/"


def test_erfundene_quelle_wird_verworfen():
    """Eine Quelle, die nie gelesen wurde, ist schlimmer als keine."""
    ki = FakeKI(json.dumps({
        "automation_status": "YES", "confidence": 0.8, "reason": "x",
        "evidence": "y", "source_url": "https://ganz-woanders.de/erfunden"}))
    urteil = automation_llm.klassifizieren({"name": "X"}, seiten_ok(), ki)
    assert urteil["source_url"] == ""


def test_ohne_webseite_wird_nicht_geurteilt():
    ki = FakeKI(json.dumps({"automation_status": "NO", "confidence": 1.0}))
    urteil = automation_llm.klassifizieren(
        {"name": "X"}, {"status": "keine_webseite", "text": ""}, ki)
    assert urteil["automation_status"] == "UNCERTAIN"
    assert ki.gefragt == []          # kein KI-Aufruf, kein Raten


def test_unerreichbare_seite_ist_uncertain_nicht_no():
    urteil = automation_llm.klassifizieren(
        {"name": "X"}, {"status": "nicht_erreichbar", "text": ""},
        FakeKI("egal"))
    assert urteil["automation_status"] == "UNCERTAIN"


def test_ohne_ki_wird_nicht_geraten():
    urteil = automation_llm.klassifizieren({"name": "X"}, seiten_ok(), None)
    assert urteil["automation_status"] == "UNCERTAIN"
    assert "nicht geraten" in urteil["reason"]


def test_kaputte_ki_antwort_ist_uncertain():
    urteil = automation_llm.klassifizieren(
        {"name": "X"}, seiten_ok(), FakeKI("kein json hier"))
    assert urteil["automation_status"] == "UNCERTAIN"


def test_unbekannter_status_wird_nicht_akzeptiert():
    ki = FakeKI(json.dumps({"automation_status": "VIELLEICHT",
                            "confidence": 0.9}))
    assert automation_llm.klassifizieren(
        {"name": "X"}, seiten_ok(), ki)["automation_status"] == "UNCERTAIN"


def test_confidence_bleibt_zwischen_null_und_eins():
    ki = FakeKI(json.dumps({"automation_status": "NO", "confidence": 7.5,
                            "reason": "x", "evidence": "", "source_url": ""}))
    assert automation_llm.klassifizieren(
        {"name": "X"}, seiten_ok(), ki)["confidence"] == 1.0


def test_ki_fehler_kippt_den_lauf_nicht():
    urteil = automation_llm.klassifizieren(
        {"name": "X"}, seiten_ok(), FakeKI(RuntimeError("API tot")))
    assert urteil["automation_status"] == "UNCERTAIN"
    assert "API tot" in urteil["reason"]


def test_prompt_verlangt_leistung_statt_wortsuche():
    """Der Klassifizierer darf nicht nach dem Wort "Automatisierung"
    suchen, sondern muss Leistung von Eigenbedarf unterscheiden."""
    text = automation_llm.SYSTEM_PROMPT
    assert "INTERN" in text
    assert "INDUSTRIE" in text
    assert "UNCERTAIN" in text


def test_jede_firma_bekommt_ein_urteil():
    ki = FakeKI(json.dumps({"automation_status": "NO", "confidence": 0.8,
                            "reason": "IT-Betreuung", "evidence": "",
                            "source_url": ""}))
    firmen = [{"name": "A"}, {"name": "B"}, {"name": "C"}]
    seiten = {0: seiten_ok(), 1: {"status": "nicht_erreichbar", "text": ""},
              2: seiten_ok()}
    urteile = automation_llm.viele_klassifizieren(firmen, seiten, ki)
    assert set(urteile) == {0, 1, 2}
    assert urteile[1]["automation_status"] == "UNCERTAIN"

"""Tests fuer den Postfach-Bereich (Task 9): rein lesende Konversationsliste
+ Detailbereich in EINEM Screen (siehe web.routen.postfach Modul-Docstring).
Instantly ist ueber app.state.instantly_leser gefaked - exakt das Muster aus
tests/web/test_kampagnen.py (dort FakeInstantlyLeser.kampagnen_stand, hier
FakeInstantlyLeser.emails_stand). Fuer die Firmen-Anreicherung braucht es
echte leads.json-Eintraege wie in tests/web/test_kontakte.py (_lauf dort)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from pipeline.approval import approve
from pipeline.run_store import RunStore
from web.antwort_freigabe import (
    erstelle_antwort_freigabe,
    pruefe_versandhinweis,
)
from web.app import create_app
from web.instantly_antworter import (
    InstantlyAntwortAbgelehnt,
    InstantlyAntwortStatusUnklar,
)

PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

KUNDE_A_YAML = """
name: Demo GmbH
zielgruppe:
  titel: [CEO]
angebot: Testangebot
tonalitaet: ruhig
absender: Jonas Wilde
follow_up_tage: [4, 9]
test_empfaenger: [anna@firma.de]
sperrliste: []
"""


class FakeInstantlyLeser:
    """Ersetzt web.instantly_leser.InstantlyLeser.emails_stand - liefert
    vorbereitete Rohdaten statt echter HTTP-Aufrufe. `emails_by_campaign`
    bildet campaign_id auf eine Liste roher Email-Objekte ab (wie sie das
    Schema liefert, siehe web.instantly_leser Modul-Docstring)."""

    def __init__(self, emails_by_campaign: dict | None = None, erreichbar: bool = True,
                 stand: datetime | None = None):
        self.emails_by_campaign = emails_by_campaign or {}
        self.erreichbar = erreichbar
        self.stand = stand if stand is not None else datetime(2026, 7, 20, 9, 30)
        self.angefragt: list[str] = []
        self.verworfen: list[str] = []

    def emails_stand(self, campaign_ids):
        self.angefragt = list(campaign_ids)
        ergebnis = {}
        for cid in campaign_ids:
            ergebnis[cid] = {
                "items": self.emails_by_campaign.get(cid, []),
                "erreichbar": self.erreichbar,
                "stand": self.stand if self.erreichbar else None,
            }
        return ergebnis

    def verwerfe_email_cache(self, campaign_id):
        self.verworfen.append(campaign_id)


class FakeInstantlyAntworter:
    def __init__(self, fehler=None):
        self.fehler = fehler
        self.aufrufe = []

    def antworten(self, **daten):
        self.aufrufe.append(daten)
        if self.fehler is not None:
            raise self.fehler
        return {"id": "antwort-1"}


def _email(campaign_id="camp-1", ue_type=1, to="anna@firma.de", frm=None,
           betreff="Anschreiben", zeit="2026-07-20T09:00:00.000Z", text="Text der Mail"):
    return {
        "id": "mail-1", "campaign_id": campaign_id, "ue_type": ue_type,
        "to_address_email_list": to, "from_address_email": frm,
        "subject": betreff, "timestamp_email": zeit, "timestamp_created": zeit,
        "body": {"text": text}, "content_preview": text, "eaccount": "wir@digitaldiamonds.de",
    }


def _lead(vorname, nachname, email, firma):
    return {"first_name": vorname, "last_name": nachname, "email": email,
            "company": firma, "title": "CEO", "website": "https://" + firma.lower() + ".de",
            "source": "apollo"}


def _lauf(daten_dir: Path, slug: str, kunde_datei: str, ts: str, leads: list, *,
          campaign_id: str = "camp-1", name: str = "Lena Hartmann") -> Path:
    """Baut einen vollstaendig uebergebenen Lauf (Freigabe + versand_komplett)
    mit echten leads.json-Eintraegen - noetig, damit sowohl
    web.routen.kampagnen._alle_laeufe (liefert die campaign_id) als auch
    web.kontakte.sammle_kontakte (liefert die Firma zur Anreicherung) etwas
    zum Finden haben."""
    lauf_dir = daten_dir / "laeufe" / slug / ts
    lauf_dir.mkdir(parents=True)
    store = RunStore.resume(lauf_dir)
    store.save_step("kunde_pfad", {"pfad": f"kunden/{kunde_datei}"})
    store.save_step("leads", {"leads": leads, "ohne_email": 0})
    pruefung_ok = [{"email": l["email"], "betreff": "Betreff"} for l in leads]
    store.save_step("pruefung_ok", pruefung_ok)
    approve(store, name=name)
    store.save_step("versand", {"campaign_id": campaign_id})
    store.save_step("versand_komplett", {"campaign_id": campaign_id})
    return lauf_dir


def _bereite_antwortfall_vor(
    angemeldeter_client,
    daten_dir,
    *,
    eaccount="wir@digitaldiamonds.de",
    fehler=None,
):
    _lauf(
        daten_dir,
        "demo-gmbh",
        "demo-gmbh.yaml",
        "20260720-090000",
        leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")],
        campaign_id="camp-1",
    )
    empfangen = _email(
        ue_type=2,
        frm="anna@firma.de",
        betreff="Anschreiben",
        text="Klingt gut.",
    )
    empfangen["eaccount"] = eaccount
    leser = FakeInstantlyLeser(
        emails_by_campaign={"camp-1": [empfangen]}
    )
    antworter = FakeInstantlyAntworter(fehler)
    angemeldeter_client.app.state.instantly_leser = leser
    angemeldeter_client.app.state.instantly_antworter = antworter
    return leser, antworter


def _direkter_antwort_token(angemeldeter_client, kontakt="anna@firma.de"):
    return erstelle_antwort_freigabe(
        angemeldeter_client.app.state.serializer,
        kontakt=kontakt,
        reply_to_uuid="mail-1",
    )


@pytest.fixture
def daten_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_SECRET", "test-geheimnis-nur-fuer-tests")
    monkeypatch.setenv("WEB_COOKIE_SECURE", "0")
    nutzer = [{"name": "Lena Hartmann", "passwort_hash": PWD_CONTEXT.hash("richtig123")}]
    (tmp_path / "users.yaml").write_text(yaml.safe_dump(nutzer, allow_unicode=True), encoding="utf-8")
    (tmp_path / "kunden").mkdir()
    (tmp_path / "kunden" / "demo-gmbh.yaml").write_text(KUNDE_A_YAML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def app(daten_dir):
    return create_app(daten_dir)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def angemeldeter_client(client):
    client.post("/login", data={"name": "Lena Hartmann", "passwort": "richtig123"})
    # Copy-Rework (20.07.2026): siehe tests/web/test_dashboard.py fuer den Grund.
    client.cookies.set("intro_gesehen", "1")
    return client


# Anmeldung / Methode -----------------------------------------------------

def test_verlangt_anmeldung(client):
    antwort = client.get("/postfach", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/login"


def test_keine_post_route(angemeldeter_client):
    antwort = angemeldeter_client.post("/postfach")
    assert antwort.status_code == 405


# Leer-/Fehlzustaende -------------------------------------------------------

def test_ohne_kampagnen_zeigt_neutralen_leer_zustand_ohne_instantly_abfrage(angemeldeter_client):
    app = angemeldeter_client.app
    leser = FakeInstantlyLeser()
    app.state.instantly_leser = leser
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Noch keine Konversation" in antwort.text
    assert leser.angefragt == []  # keine Kampagnen -> kein Abruf noetig


def test_api_nicht_erreichbar_zeigt_freundlichen_text(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(erreichbar=False)
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Live-Stand gerade nicht erreichbar" in antwort.text


def test_erreichbar_aber_leer_zeigt_ehrlichen_hinweis(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": []})
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Antworten siehst du derzeit nur in Instantly." in antwort.text


# Konversationsliste + Detail -----------------------------------------------

def test_liste_zeigt_konversation_mit_firmen_anreicherung_und_richtung(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": [
        _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben",
               zeit="2026-07-20T09:00:00.000Z", text="Erstes Anschreiben"),
        _email(ue_type=2, frm="anna@firma.de", betreff="Re: Anschreiben",
               zeit="2026-07-21T10:00:00.000Z", text="Klingt gut, mehr Infos?"),
    ]})
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    assert "Anna Muster" in antwort.text
    assert "Demo GmbH" in antwort.text
    assert "Re: Anschreiben" in antwort.text  # Betreff der juengsten Nachricht
    assert "Antwort erhalten" in antwort.text  # Richtungs-Indikator: letzte Nachricht empfangen


def test_detail_zeigt_chronologische_nachrichten_mit_sichtbarer_richtung(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")], campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": [
        _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben",
               zeit="2026-07-20T09:00:00.000Z", text="Erstes Anschreiben"),
        _email(ue_type=2, frm="anna@firma.de", betreff="Re: Anschreiben",
               zeit="2026-07-21T10:00:00.000Z", text="Klingt gut, mehr Infos?"),
    ]})
    antwort = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    assert antwort.status_code == 200
    text = antwort.text
    # beide Nachrichten sichtbar, chronologisch (gesendet vor empfangen)...
    assert text.index("Erstes Anschreiben") < text.index("Klingt gut, mehr Infos?")
    # ... und optisch unterscheidbar (eigene CSS-Klassen je Richtung).
    assert "postfach-nachricht--gesendet" in text
    assert "postfach-nachricht--empfangen" in text
    # Antwort-Knopf zeigt zu Instantly, kein eigenes Antwortfeld im Markup.
    assert "In Instantly antworten ↗" in text
    assert "<textarea" not in text


def test_neuere_konversation_ist_zuerst_ausgewaehlt_ohne_query_parameter(angemeldeter_client, daten_dir):
    _lauf(daten_dir, "demo-gmbh", "demo-gmbh.yaml", "20260720-090000",
          leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH"),
                 _lead("Bob", "Beispiel", "bob@firma.de", "Beispiel AG")],
          campaign_id="camp-1")
    app = angemeldeter_client.app
    app.state.instantly_leser = FakeInstantlyLeser(emails_by_campaign={"camp-1": [
        _email(ue_type=1, to="anna@firma.de", betreff="Anschreiben Anna",
               zeit="2026-07-18T09:00:00.000Z", text="An Anna"),
        _email(ue_type=1, to="bob@firma.de", betreff="Anschreiben Bob",
               zeit="2026-07-20T09:00:00.000Z", text="An Bob"),
    ]})
    antwort = angemeldeter_client.get("/postfach")
    assert antwort.status_code == 200
    # Bob ist die juengere Konversation (20.07. vs. 18.07.) -> Detailbereich
    # zeigt seine Nachricht, ohne dass ein Kontakt explizit gewaehlt wurde.
    assert "An Bob" in antwort.text


# Antworten über Instantly -------------------------------------------------

def test_antwort_wird_genau_einmal_aus_belegten_instantly_daten_gesendet(
    angemeldeter_client, daten_dir
):
    leser, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )
    token = _direkter_antwort_token(angemeldeter_client)

    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token,
            "antwort_text": "  Danke für die Rückmeldung.  ",
        },
        follow_redirects=False,
    )

    assert antwort.status_code == 303
    ziel = urlparse(antwort.headers["location"])
    parameter = parse_qs(ziel.query)
    assert ziel.path == "/postfach"
    assert parameter["kontakt"] == ["anna@firma.de"]
    assert pruefe_versandhinweis(
        angemeldeter_client.app.state.serializer,
        parameter["versand"][0],
        kontakt="anna@firma.de",
    ) is True
    assert antworter.aufrufe == [{
        "eaccount": "wir@digitaldiamonds.de",
        "reply_to_uuid": "mail-1",
        "betreff": "Re: Anschreiben",
        "text": "Danke für die Rückmeldung.",
    }]
    assert leser.verworfen == ["camp-1"]

    zweite_antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token,
            "antwort_text": "Danke für die Rückmeldung.",
        },
    )
    assert zweite_antwort.status_code == 409
    assert len(antworter.aufrufe) == 1


@pytest.mark.parametrize("text", ["", " ", "x" * 10_001])
def test_ungueltiger_text_sendet_nichts(
    angemeldeter_client, daten_dir, text
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": _direkter_antwort_token(
                angemeldeter_client
            ),
            "antwort_text": text,
        },
    )

    assert antwort.status_code == 400
    assert antworter.aufrufe == []


def test_kontakt_manipulation_sendet_nichts(
    angemeldeter_client, daten_dir
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "bob@firma.de",
            "antwort_token": _direkter_antwort_token(
                angemeldeter_client, kontakt="anna@firma.de"
            ),
            "antwort_text": "Antwort",
        },
    )

    assert antwort.status_code == 400
    assert antworter.aufrufe == []


def test_token_manipulation_sendet_nichts(
    angemeldeter_client, daten_dir
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )
    token = _direkter_antwort_token(angemeldeter_client)
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token + "manipuliert",
            "antwort_text": "Antwort",
        },
    )

    assert antwort.status_code == 400
    assert antworter.aufrufe == []


@pytest.mark.parametrize(
    ("fehler", "erwarteter_text", "unsicher"),
    [
        (
            InstantlyAntwortAbgelehnt("HTTP 422"),
            "Instantly hat die Antwort nicht angenommen.",
            False,
        ),
        (
            InstantlyAntwortStatusUnklar("Timeout"),
            "Der Versandstatus ist unklar.",
            True,
        ),
    ],
)
def test_fehlerzustand_bleibt_ehrlich_und_entwurf_bleibt_erhalten(
    angemeldeter_client,
    daten_dir,
    fehler,
    erwarteter_text,
    unsicher,
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir, fehler=fehler
    )
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": _direkter_antwort_token(
                angemeldeter_client
            ),
            "antwort_text": "Mein nicht verlorener Entwurf",
        },
    )

    assert antwort.status_code == 502
    assert antwort.context["antwort_fehler"].startswith(erwarteter_text)
    assert antwort.context["antwort_text"] == "Mein nicht verlorener Entwurf"
    assert antwort.context["antwort_unsicher"] is unsicher
    assert len(antworter.aufrufe) == 1

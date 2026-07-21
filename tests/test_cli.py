import json, os
from datetime import datetime, timedelta
from pathlib import Path
import pytest
import yaml
import pipeline.__main__ as cli
import pipeline.run_store as run_store_modul
from pipeline.__main__ import senden
from pipeline.models import Lead
from pipeline.run_store import RunStore
from pipeline.senders.instantly import InstantlySender
from pipeline.approval import approve
from tests.test_apollo import FakeSession, FakeResponse

_PRUEFUNG_OK = [{"email": "test1@example.com", "betreff": "B", "mail_1": "M",
                "follow_up_1": "F1", "follow_up_2": "F2"}]

_TEST_KUNDE_YAML = """
name: Test GmbH
zielgruppe:
  titel: [CEO]
angebot: Testangebot
tonalitaet: ruhig
absender: Tester
follow_up_tage: [1, 2]
test_empfaenger:
  - test1@example.com
"""

def _freigegebener_lauf(tmp_path):
    # Eigene Kunden-Datei statt kunden/demo-gmbh.yaml: die echte Demo-Datei
    # aendert sich im Betrieb (echte Test-Empfaenger) und darf Tests nicht
    # kippen.
    kunde_datei = tmp_path / "test-kunde.yaml"
    kunde_datei.write_text(_TEST_KUNDE_YAML, encoding="utf-8")
    store = RunStore(tmp_path, "Demo")
    store.save_step("kunde_pfad", {"pfad": str(kunde_datei)})
    store.save_step("pruefung_ok", _PRUEFUNG_OK)
    approve(store)
    return store

def test_senden_verweigert_ohne_freigabe(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    store = RunStore(tmp_path, "Demo")
    store.save_step("pruefung_ok", [])
    with pytest.raises(SystemExit, match="Freigabe"):
        senden(store.run_dir)

def test_senden_verweigert_fremde_empfaenger(tmp_path, monkeypatch):
    # Aufbau: freigegebener Lauf, aber ein Empfaenger fehlt in test_empfaenger
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    from pipeline.approval import approve
    store = RunStore(tmp_path, "Demo")
    store.save_step("kunde_pfad", {"pfad": "kunden/demo-gmbh.yaml"})
    store.save_step("pruefung_ok", [{"email": "fremd@echt.de", "betreff": "B",
                                     "mail_1": "M", "follow_up_1": "F", "follow_up_2": "F"}])
    approve(store)
    with pytest.raises(SystemExit, match="Test-Empfänger"):
        senden(store.run_dir)

def test_laedt_dotenv_ohne_vorhandene_variablen_zu_ueberschreiben(tmp_path, monkeypatch):
    monkeypatch.delenv("MEINE_TEST_VAR", raising=False)
    monkeypatch.setenv("SCHON_GESETZT", "alt")
    env_datei = tmp_path / ".env"
    env_datei.write_text(
        "# Kommentar\n\nMEINE_TEST_VAR=neu\nSCHON_GESETZT=ueberschrieben\n", encoding="utf-8")
    cli.lade_dotenv(env_datei)
    assert os.environ["MEINE_TEST_VAR"] == "neu"
    assert os.environ["SCHON_GESETZT"] == "alt"

def test_lade_dotenv_entfernt_umschliessende_anfuehrungszeichen(monkeypatch, tmp_path):
    monkeypatch.delenv("MIT_DOPPELTEN_QUOTES", raising=False)
    monkeypatch.delenv("MIT_EINFACHEN_QUOTES", raising=False)
    monkeypatch.delenv("OHNE_QUOTES", raising=False)
    env_datei = tmp_path / ".env"
    env_datei.write_text(
        'MIT_DOPPELTEN_QUOTES="hallo welt"\n'
        "MIT_EINFACHEN_QUOTES='hallo welt'\n"
        "OHNE_QUOTES=hallo\n",
        encoding="utf-8")
    cli.lade_dotenv(env_datei)
    assert os.environ["MIT_DOPPELTEN_QUOTES"] == "hallo welt"
    assert os.environ["MIT_EINFACHEN_QUOTES"] == "hallo welt"
    assert os.environ["OHNE_QUOTES"] == "hallo"

def test_lade_dotenv_ohne_datei_tut_nichts(tmp_path):
    cli.lade_dotenv(tmp_path / "gibts-nicht.env")  # darf nicht werfen

def test_lauf_bricht_ohne_apify_key_ab(monkeypatch):
    monkeypatch.delenv("APIFY_API_KEY", raising=False)
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(SystemExit, match="APIFY_API_KEY"):
        cli.lauf("kunden/demo-gmbh.yaml", 10, None)

def test_lauf_bricht_ohne_apollo_key_ab(monkeypatch):
    monkeypatch.setenv("APIFY_API_KEY", "x")
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(SystemExit, match="APOLLO_API_KEY"):
        cli.lauf("kunden/demo-gmbh.yaml", 10, None)

def test_lauf_bricht_ohne_anthropic_key_ab(monkeypatch):
    monkeypatch.setenv("APIFY_API_KEY", "x")
    monkeypatch.setenv("APOLLO_API_KEY", "x")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        cli.lauf("kunden/demo-gmbh.yaml", 10, None)

def test_senden_bricht_ohne_instantly_key_ab(tmp_path, monkeypatch):
    monkeypatch.delenv("INSTANTLY_API_KEY", raising=False)
    store = RunStore(tmp_path, "Demo")
    with pytest.raises(SystemExit, match="INSTANTLY_API_KEY"):
        senden(store.run_dir)

def test_senden_verweigert_erneuten_versand_nach_erfolgreichem_lauf(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    store = _freigegebener_lauf(tmp_path)
    store.save_step("versand_komplett", {"campaign_id": "camp-9"})
    with pytest.raises(SystemExit, match="camp-9"):
        senden(store.run_dir)

def test_senden_verweigert_abgelehnten_lauf(tmp_path, monkeypatch):
    # Review-Fund (Task 5): abgelehnt.json muss den Versand an der EINEN
    # Stelle sperren, die sowohl CLI (senden) als auch die Web-Route
    # (_versand_ausfuehren) teilen - unabhaengig davon, ob der Lauf
    # (versehentlich oder durch eine Race) trotzdem freigegeben wurde.
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    store = _freigegebener_lauf(tmp_path)
    (store.run_dir / "abgelehnt.json").write_text(
        json.dumps({"von": "Lena", "am": "17.07.2026", "begruendung": "Ton passt nicht"}),
        encoding="utf-8")
    poison_session = FakeSession([])  # jeder Aufruf wuerde IndexError werfen
    monkeypatch.setattr(
        cli, "InstantlySender",
        lambda api_key: InstantlySender(api_key, session=poison_session))
    with pytest.raises(SystemExit, match="abgelehnt"):
        cli.senden(store.run_dir)
    assert poison_session.aufrufe == []

def test_freigeben_verweigert_abgelehnten_lauf(tmp_path):
    # E-Fix 7: Konsistenz mit dem Web-Guard (web.routen.freigabe -
    # ZUSTAND_ERLAUBT_FREIGEBEN schliesst "abgelehnt" aus) - auch die CLI
    # 'freigeben' muss abgelehnt.json respektieren, statt eine bereits
    # abgelehnte Anschreiben-Runde im Nachhinein doch noch freizugeben.
    store = RunStore(tmp_path, "Demo")
    store.save_step("pruefung_ok", [])
    (store.run_dir / "abgelehnt.json").write_text(
        json.dumps({"von": "Lena", "am": "17.07.2026", "begruendung": "Ton passt nicht"}),
        encoding="utf-8")

    with pytest.raises(SystemExit, match="abgelehnt"):
        cli.freigeben(str(store.run_dir))

    assert not (store.run_dir / "FREIGABE.txt").exists()


def test_senden_wiederholt_nach_fehlgeschlagenem_lead_import_ohne_neue_kampagne(
        tmp_path, monkeypatch):
    monkeypatch.setenv("INSTANTLY_API_KEY", "test-key")
    store = _freigegebener_lauf(tmp_path)

    # Erster Versuch: Kampagne wird angelegt, aber der Lead-Import scheitert
    # (z.B. voruebergehender Instantly-Fehler).
    fehlgeschlagene_session = FakeSession([
        FakeResponse(200, {"id": "camp-1"}),
        FakeResponse(500, {}, text="Server-Fehler"),
    ])
    monkeypatch.setattr(
        cli, "InstantlySender",
        lambda api_key: InstantlySender(api_key, session=fehlgeschlagene_session))
    with pytest.raises(RuntimeError):
        cli.senden(store.run_dir)
    versand = store.load_step("versand")
    assert versand["campaign_id"] == "camp-1"
    assert not store.step_done("versand_komplett")

    # Zweiter Versuch: dieselbe campaign_id wird wiederverwendet - kein
    # zweiter Kampagnen-Anlage-Aufruf, nur der Lead-Import laeuft erneut.
    erfolgreiche_session = FakeSession([FakeResponse(200, {})])
    monkeypatch.setattr(
        cli, "InstantlySender",
        lambda api_key: InstantlySender(api_key, session=erfolgreiche_session))
    cli.senden(store.run_dir)
    assert len(erfolgreiche_session.aufrufe) == 1  # nur Lead-Import, keine neue Kampagne
    versand_komplett = store.load_step("versand_komplett")
    assert versand_komplett["campaign_id"] == "camp-1"

def _fake_source_leads(kunde, limit, apify_key, apollo_key):
    """Ersetzt pipeline.sourcing.source_leads: liefert 2 feste Leads (statt
    echter Apify-/Apollo-Aufrufe) plus eine dazu passende Deckungsquote
    (2 von 2 Firmen mit Kontakt -> 100%), damit alles danach (Dedupe,
    Personalisierung, Bericht) unveraendert real durchlaeuft."""
    leads = [
        Lead(first_name="Anna", last_name="Muster", email="anna@firma.de",
             company="Firma GmbH", title="CEO", website="", source="apollo"),
        Lead(first_name="Bob", last_name="Beispiel", email="bob@firma.de",
             company="Firma GmbH", title="CTO", website="", source="apollo"),
    ]
    deckung = {"firmen_gesamt": 2, "firmen_mit_kontakt": 2, "quote_prozent": 100.0}
    return leads, deckung

class _FakeKI:
    """Ersetzt KI: liefert gueltiges JSON fuer personalize() (System-Prompt
    erwaehnt 'JSON') und 'JA' fuer den Qualitaets-Pruefer (jeder andere
    Aufruf)."""
    def frage(self, system, prompt):
        if "JSON" in system:
            return json.dumps({"betreff": "Kurze Anfrage",
                                "mail_1": " ".join(["Wort"] * 50),
                                "follow_up_1": "F1", "follow_up_2": "F2"})
        return "JA"

class _FakeDatetime:
    """Ersetzt datetime in pipeline.run_store: jeder now()-Aufruf springt um
    1 Sekunde weiter, damit zwei lauf()-Aufrufe im selben Test garantiert in
    verschiedenen Laufordnern landen (RunStore-Zeitstempel hat nur
    Sekunden-Aufloesung)."""
    _zeit = datetime(2026, 1, 1, 0, 0, 0)

    @classmethod
    def now(cls):
        aktuelle = cls._zeit
        cls._zeit += timedelta(seconds=1)
        return aktuelle

def test_lauf_personalisiert_end_zu_ende_und_dedupe_greift_erst_im_naechsten_lauf(
        tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "source_leads", _fake_source_leads)
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setattr(cli, "LAEUFE", tmp_path)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cli.lauf("kunden/demo-gmbh.yaml", 10, None)

    laeufe = sorted((tmp_path / "demo-gmbh").glob("*"))
    assert len(laeufe) == 1
    erster_lauf = laeufe[0]
    personalisierung = json.loads(
        (erster_lauf / "personalisierung.json").read_text(encoding="utf-8"))
    assert len(personalisierung["fertig"]) == 2
    erster_dedupe = json.loads((erster_lauf / "dedupe.json").read_text(encoding="utf-8"))
    assert erster_dedupe["verworfen"] == []
    assert (erster_lauf / "freigabe-vorschau.md").exists()
    erste_leads = json.loads((erster_lauf / "leads.json").read_text(encoding="utf-8"))
    assert len(erste_leads["leads"]) == 2
    assert erste_leads["deckung"] == {"firmen_gesamt": 2, "firmen_mit_kontakt": 2,
                                      "quote_prozent": 100.0}
    bericht = (erster_lauf / "bericht.md").read_text(encoding="utf-8")
    assert "Ohne E-Mail übersprungen: 0" in bericht

    # Zweiter, frischer Lauf: jetzt muessen beide Leads aus dem ersten Lauf
    # als "bereits in früherem Lauf angeschrieben" verworfen werden - das
    # beweist, dass Dedupe ueber Laeufe hinweg weiterhin greift.
    cli.lauf("kunden/demo-gmbh.yaml", 10, None)

    laeufe = sorted((tmp_path / "demo-gmbh").glob("*"))
    assert len(laeufe) == 2
    zweiter_dedupe = json.loads((laeufe[1] / "dedupe.json").read_text(encoding="utf-8"))
    assert len(zweiter_dedupe["verworfen"]) == 2
    assert all(v["grund"] == "bereits in früherem Lauf angeschrieben"
               for v in zweiter_dedupe["verworfen"])

def test_lauf_globale_sperrliste_blockt_lead_auch_ohne_eigene_kunden_sperrliste(
        tmp_path, monkeypatch):
    # Task 2: die globale Sperrliste (sperrliste-global.yaml im
    # Projekt-Wurzelordner) muss in 'lauf' greifen, auch wenn der Kunde
    # selbst gar keine eigene sperrliste hat (_TEST_KUNDE_YAML hat keine).
    monkeypatch.setattr(cli, "source_leads", _fake_source_leads)
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    kunde_datei = tmp_path / "test-kunde.yaml"
    kunde_datei.write_text(_TEST_KUNDE_YAML, encoding="utf-8")
    (tmp_path / "sperrliste-global.yaml").write_text(
        yaml.safe_dump(["firma.de"]), encoding="utf-8")

    # cwd fuer die Dauer des Tests auf tmp_path, damit sowohl die
    # kunden-relative Datei als auch lade_globale_sperrliste(Path(".")) im
    # praeparierten Verzeichnis landen statt im echten Projekt-Wurzelordner.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "LAEUFE", Path("laeufe"))

    cli.lauf(str(kunde_datei.name), 10, None)

    laeufe = sorted((tmp_path / "laeufe" / "test-gmbh").glob("*"))
    assert len(laeufe) == 1
    dedupe_stand = json.loads((laeufe[0] / "dedupe.json").read_text(encoding="utf-8"))
    assert dedupe_stand["behalten"] == []
    assert len(dedupe_stand["verworfen"]) == 2
    assert all(v["grund"] == "Domain auf Sperrliste" for v in dedupe_stand["verworfen"])

def test_neu_ab_dedupe_verwendet_von_hand_bearbeitete_leads(tmp_path, monkeypatch):
    # Task 11: --fortsetzen zusammen mit --neu-ab soll den angegebenen
    # Schritt und alle nachgelagerten neu berechnen, damit eine
    # Handbearbeitung von leads.json auch tatsaechlich wirkt.
    monkeypatch.setattr(cli, "source_leads", _fake_source_leads)
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setattr(cli, "LAEUFE", tmp_path)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cli.lauf("kunden/demo-gmbh.yaml", 10, None)
    lauf_dir = sorted((tmp_path / "demo-gmbh").glob("*"))[0]

    # Leads von Hand bearbeiten: eine E-Mail-Adresse austauschen.
    leads_pfad = lauf_dir / "leads.json"
    leads_daten = json.loads(leads_pfad.read_text(encoding="utf-8"))
    leads_daten["leads"][0]["email"] = "neu-bearbeitet@firma.de"
    leads_pfad.write_text(json.dumps(leads_daten), encoding="utf-8")

    cli.lauf("kunden/demo-gmbh.yaml", 10, str(lauf_dir), neu_ab="dedupe")

    personalisierung = json.loads(
        (lauf_dir / "personalisierung.json").read_text(encoding="utf-8"))
    emails = {eintrag["email"] for eintrag in personalisierung["fertig"]}
    assert "neu-bearbeitet@firma.de" in emails
    # leads.json auf der Platte enthaelt tatsaechlich noch die Handbearbeitung
    # (neu_ab="dedupe" loescht leads.json nicht) - von der Platte neu lesen,
    # nicht das In-Memory-dict von oben pruefen.
    leads_nach_lauf = json.loads(leads_pfad.read_text(encoding="utf-8"))
    assert leads_nach_lauf["leads"][0]["email"] == "neu-bearbeitet@firma.de"

def test_neu_ab_widerruft_alte_freigabe(tmp_path, monkeypatch):
    # Sicherheitsluecke aus dem Review: lauf -> freigeben -> lauf
    # --fortsetzen --neu-ab personalisierung -> senden wuerde sonst neu
    # generierte Texte unter der alten Freigabe verschicken.
    from pipeline.approval import is_approved
    monkeypatch.setattr(cli, "source_leads", _fake_source_leads)
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setattr(cli, "LAEUFE", tmp_path)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cli.lauf("kunden/demo-gmbh.yaml", 10, None)
    lauf_dir = sorted((tmp_path / "demo-gmbh").glob("*"))[0]
    store = RunStore.resume(lauf_dir)
    approve(store)
    assert is_approved(store)

    cli.lauf("kunden/demo-gmbh.yaml", 10, str(lauf_dir), neu_ab="personalisierung")

    assert is_approved(store) is False

class _FakeKIEinerLehntAb:
    """Wie _FakeKI, aber der Qualitaets-Pruefer lehnt genau den Lead mit dem
    Titel 'CTO' ab (der Pruefer-Prompt enthaelt den Titel, siehe
    pipeline.quality._regeln/check) - so entsteht garantiert ein
    Nacharbeit-Eintrag mit vorher erfolgreich erzeugtem Text, um zu pruefen,
    dass Task 5 diesen Text mit in nacharbeit ablegt (fuer die aufklappbare
    Anzeige 'Von der Pruefung aussortiert' im Web-Interface)."""
    def frage(self, system, prompt):
        if "JSON" in system:
            return json.dumps({"betreff": "Kurze Anfrage",
                                "mail_1": " ".join(["Wort"] * 50),
                                "follow_up_1": "F1", "follow_up_2": "F2"})
        if "CTO" in prompt:
            return "NEIN, Ton passt nicht zur Zielgruppe"
        return "JA"

def test_lauf_speichert_abgelehnten_text_in_nacharbeit(tmp_path, monkeypatch):
    # Task 5 (Team-Interface, Pruefen & Freigeben): die aufklappbare Ansicht
    # der aussortierten Texte braucht neben dem Grund auch den Text selbst,
    # wenn einer erzeugt wurde (hier: personalize() gelingt, nur check()
    # lehnt ab). nacharbeit-Eintraege muessen deshalb betreff/mail_1/
    # follow_up_1/follow_up_2 zusaetzlich zu email+grund tragen.
    monkeypatch.setattr(cli, "source_leads", _fake_source_leads)
    monkeypatch.setattr(cli, "KI", _FakeKIEinerLehntAb)
    monkeypatch.setattr(cli, "LAEUFE", tmp_path)
    monkeypatch.setattr(run_store_modul, "datetime", _FakeDatetime)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cli.lauf("kunden/demo-gmbh.yaml", 10, None)

    lauf_dir = sorted((tmp_path / "demo-gmbh").glob("*"))[0]
    personalisierung = json.loads(
        (lauf_dir / "personalisierung.json").read_text(encoding="utf-8"))
    assert len(personalisierung["nacharbeit"]) == 1
    eintrag = personalisierung["nacharbeit"][0]
    assert eintrag["email"] == "bob@firma.de"
    assert "Ton passt nicht" in eintrag["grund"]
    assert eintrag["betreff"] == "Kurze Anfrage"
    assert eintrag["mail_1"].startswith("Wort")
    assert eintrag["follow_up_1"] == "F1" and eintrag["follow_up_2"] == "F2"

def test_lauf_fortsetzen_akzeptiert_altes_leads_listenformat(tmp_path, monkeypatch):
    # Vor der "ohne_email"-Zaehlung war leads.json eine reine Liste statt
    # {"leads": [...], "ohne_email": n}. --fortsetzen auf so einem alten
    # Laufordner darf nicht mit TypeError scheitern.
    monkeypatch.setattr(cli, "KI", _FakeKI)
    monkeypatch.setenv("APIFY_API_KEY", "test-key")
    monkeypatch.setenv("APOLLO_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    store = RunStore(tmp_path, "Demo")
    store.save_step("kunde_pfad", {"pfad": "kunden/demo-gmbh.yaml"})
    store.save_step("leads", [
        {"first_name": "Anna", "last_name": "Muster", "email": "anna@firma.de",
         "company": "Firma GmbH", "title": "CEO", "website": "", "source": "apollo"}])

    cli.lauf("kunden/demo-gmbh.yaml", 10, str(store.run_dir))

    personalisierung = store.load_step("personalisierung")
    assert len(personalisierung["fertig"]) == 1

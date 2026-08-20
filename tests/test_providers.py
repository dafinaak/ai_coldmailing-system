"""Anbieter-Register: ehrlicher Status statt vorgetaeuschter Integration."""
from pipeline.providers import PROVIDERS, bereit, uebersicht


def test_nicht_gebaute_anbieter_sind_klar_markiert():
    stand = {z["name"]: z["status"] for z in uebersicht()}
    for name in ("linkedin", "apollo", "clay", "north_data"):
        assert stand[name] == "nicht implementiert"


def test_bereit_liefert_nur_implementierte_mit_zugang(monkeypatch):
    monkeypatch.setenv("APIFY_API_KEY", "x")
    monkeypatch.delenv("HUNTER_API_KEY", raising=False)
    namen = bereit("company_discovery")
    assert "google_maps" in namen
    assert "north_data" not in namen          # nie: nicht implementiert
    assert "hunter" not in bereit("email_verification")


def test_jeder_anbieter_nennt_seine_faehigkeiten():
    for anbieter in PROVIDERS:
        assert anbieter.capabilities

"""Kleiner schreibender Instantly-Zugang für Antworten auf bestehende Mails.

Der Baustein wiederholt nie automatisch: Bei Netzwerkfehlern oder
unvollständigen Antworten ist nicht sicher, ob Instantly bereits gesendet hat.
"""
from __future__ import annotations

import os

import requests

BASIS = "https://api.instantly.ai/api/v2"


class InstantlyAntwortAbgelehnt(RuntimeError):
    """Instantly hat die Anfrage mit einem klaren 4xx-Status abgelehnt."""


class InstantlyAntwortStatusUnklar(RuntimeError):
    """Es ist nicht sicher belegbar, ob Instantly die Mail versendet hat."""


class InstantlyAntworter:
    def __init__(self, api_key: str, session=None):
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def antworten(
        self, *, eaccount: str, reply_to_uuid: str, betreff: str, text: str
    ) -> dict:
        try:
            antwort = self.session.post(
                f"{BASIS}/emails/reply",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "eaccount": eaccount,
                    "reply_to_uuid": reply_to_uuid,
                    "subject": betreff,
                    "body": {"text": text},
                },
                timeout=60,
            )
        except requests.exceptions.RequestException as fehler:
            raise InstantlyAntwortStatusUnklar(
                "Der Versandstatus ist wegen eines Netzwerkfehlers unklar."
            ) from fehler

        if 400 <= antwort.status_code < 500:
            raise InstantlyAntwortAbgelehnt(
                f"Instantly hat die Antwort mit HTTP {antwort.status_code} abgelehnt."
            )
        if antwort.status_code >= 500:
            raise InstantlyAntwortStatusUnklar(
                f"Der Versandstatus ist nach HTTP {antwort.status_code} unklar."
            )
        try:
            daten = antwort.json()
        except ValueError as fehler:
            raise InstantlyAntwortStatusUnklar(
                "Instantly hat keinen auswertbaren Versandnachweis geliefert."
            ) from fehler
        if not isinstance(daten, dict) or not daten.get("id"):
            raise InstantlyAntwortStatusUnklar(
                "Instantly hat keinen vollständigen Versandnachweis geliefert."
            )
        return daten


def geteilten_antworter(app) -> InstantlyAntworter:
    """Liefert einen geteilten, in Tests über app.state ersetzbaren Client."""
    antworter = getattr(app.state, "instantly_antworter", None)
    if antworter is not None:
        return antworter
    with app.state._instantly_antworter_lock:
        antworter = getattr(app.state, "instantly_antworter", None)
        if antworter is None:
            api_key = os.environ.get("INSTANTLY_API_KEY")
            if not api_key:
                raise RuntimeError("INSTANTLY_API_KEY fehlt.")
            antworter = InstantlyAntworter(api_key)
            app.state.instantly_antworter = antworter
        return antworter

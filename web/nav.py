"""Gemeinsame Navigation fuers Team-Interface.

Struktur-Paket (30.07.2026, Leonards Freigabe): Die Leiste ist nach
Wholix-Vorbild in GRUPPEN gegliedert und ausgeduennt:

- Gruppe "CRM": CRM und Antworten (vorher "Postfach" - umbenannt, weil
  das Namenspaar Postfach/Postfaecher eine Verwechslungs-Falle war).
- Gruppe "E-Mail-Kampagne": Dashboard, Kampagnen, Absender (vorher
  "Postfaecher"), Gesperrte Domains - plus "Lesen & Freigeben" NUR,
  wenn tatsaechlich etwas auf Freigabe wartet (der Use Case ruht
  sonst; der Tab taucht mit Zaehler von selbst wieder auf).
- Fusszeile (klein, bei Abmelden): Angebote, So funktioniert's -
  Konfiguration und Anleitung, kein Tagesgeschaeft.
- "Kontakte" (Archiv) ist aus der Leiste raus: Das Archiv ist jetzt
  eine Ansicht IM CRM (Chip "Alle Angeschriebenen"); die alte Route
  /kontakte bleibt erreichbar (Verweise/Lesezeichen brechen nicht).

Der Badge fuer "Lesen & Freigeben" kommt weiterhin aus
web.wartende.wartende_anzahl (Dateisystem-only) und wird auf jeder
Seite berechnet, weil nav_kontext() von jeder Route aufgerufen wird.
"""
from __future__ import annotations

from starlette.requests import Request

from web.wartende import wartende_anzahl

# Flache Liste aller Bereiche mit eigener Route (Schluessel, URL, Label) -
# Quelle fuer Gruppen und Fusszeile; einzelne Eintraege erscheinen je nach
# Zustand (siehe nav_kontext).
NAV_BEREICHE = [
    ("dashboard", "/", "Dashboard"),
    ("kampagnen", "/kampagnen", "Kampagnen"),
    ("postfaecher", "/postfaecher", "Absender"),
    ("pruefen", "/pruefen", "Lesen & Freigeben"),
    ("kontakte", "/kontakte", "Alle Angeschriebenen"),
    ("crm", "/crm", "CRM"),
    ("postfach", "/postfach", "Antworten"),
    ("domains", "/domains", "Gesperrte Domains"),
    ("kunden", "/kunden", "Angebote"),
    ("so-funktionierts", "/so-funktionierts", "So funktioniert's"),
]

_GRUPPE_CRM = ("crm", "postfach")
_GRUPPE_KAMPAGNE = ("dashboard", "kampagnen", "postfaecher", "domains")
_FUSS = ("kunden", "so-funktionierts")


def _eintrag(key: str, request: Request, badge=None) -> dict:
    _, url, label = next(b for b in NAV_BEREICHE if b[0] == key)
    return {"url": url, "label": label, "aktiv": request.url.path == url,
            "badge": badge}


def nav_kontext(request: Request) -> dict:
    """Baut den Navigations-Kontext fuers Layout: Gruppen mit Titel,
    dazu die Fusszeilen-Eintraege. "Lesen & Freigeben" erscheint nur
    mit wartenden Freigaben (dann mit Zaehler)."""
    daten_dir = getattr(request.app.state, "daten_dir", None)
    pruefen_badge = wartende_anzahl(daten_dir) if daten_dir is not None else 0

    kampagne = [_eintrag(k, request) for k in _GRUPPE_KAMPAGNE]
    if pruefen_badge:
        kampagne.insert(2, _eintrag("pruefen", request, badge=pruefen_badge))

    return {
        "gruppen": [
            ("CRM", [_eintrag(k, request) for k in _GRUPPE_CRM]),
            ("E-Mail-Kampagne", kampagne),
        ],
        "fuss": [_eintrag(k, request) for k in _FUSS],
    }

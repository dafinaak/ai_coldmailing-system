"""Gemeinsame Navigation fuers Team-Interface: welche der sieben Bereiche
es gibt, in welcher Reihenfolge, und wie der Kontext fuers Layout-Template
aussieht. Eigenes Modul (statt in web.app verschachtelt), damit sowohl die
Platzhalter-Routen als auch die einzelnen web.routen.*-Module (ab Task 2)
dieselbe Liste verwenden - eine Seite taucht so nur an einer Stelle auf."""
from __future__ import annotations

from starlette.requests import Request

# Die sieben Bereiche der Seitenleiste, in dieser verbindlichen Reihenfolge
# (siehe docs/text-leitfaden-interface.md).
NAV_BEREICHE = [
    ("dashboard", "/", "Dashboard"),
    ("kampagnen", "/kampagnen", "Kampagnen"),
    ("pruefen", "/pruefen", "Prüfen & Freigeben"),
    ("kontakte", "/kontakte", "Kontakte"),
    ("postfach", "/postfach", "Postfach"),
    ("domains", "/domains", "Gesperrte Domains"),
    ("kunden", "/kunden", "Kunden"),
]


def nav_kontext(request: Request) -> list[dict]:
    return [
        {"url": url, "label": label, "aktiv": request.url.path == url, "badge": None}
        for _, url, label in NAV_BEREICHE
    ]

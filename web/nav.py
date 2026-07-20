"""Gemeinsame Navigation fuers Team-Interface: welche der sieben Bereiche
es gibt, in welcher Reihenfolge, und wie der Kontext fuers Layout-Template
aussieht. Eigenes Modul (statt in web.app verschachtelt), damit sowohl die
Platzhalter-Routen als auch die einzelnen web.routen.*-Module (ab Task 2)
dieselbe Liste verwenden - eine Seite taucht so nur an einer Stelle auf.

Seit Task 7 traegt der Badge-Platzhalter (aus Task 1) fuer "Lesen &
Freigeben" die Anzahl wartender Freigaben - auf JEDER Seite, weil
nav_kontext() von jeder Route aufgerufen wird. Die Zaehlung kommt aus
web.wartende.wartende_anzahl (Dateisystem-only, siehe dort) statt hier neu
gebaut zu werden.

Copy-Rework (20.07.2026): "So funktioniert's" ist ein achter, bewusst
unauffaelliger Eintrag unten in der Liste (eigene Route in
web.routen.intro) - die "sieben Bereiche" im Docstring oben bleiben die
fachlichen Kernbereiche, dieser Eintrag ist nur der jederzeit erreichbare
Wieder-Einstieg in die Kurz-Erklaerung.

Baustein 2 (20.07.2026): "Postfächer" kommt als neunter Eintrag dazu,
direkt nach "Kampagnen" (thematisch am naechsten: beide drehen sich um den
Instantly-Versand) - rein lesende Uebersicht des Verbindungs-/Anwaerm-
Status aller Sende-Postfaecher, siehe web.routen.postfaecher."""
from __future__ import annotations

from starlette.requests import Request

from web.wartende import wartende_anzahl

# Die sieben Bereiche der Seitenleiste, in dieser verbindlichen Reihenfolge
# (siehe docs/text-leitfaden-interface.md).
NAV_BEREICHE = [
    ("dashboard", "/", "Dashboard"),
    ("kampagnen", "/kampagnen", "Kampagnen"),
    ("postfaecher", "/postfaecher", "Postfächer"),
    ("pruefen", "/pruefen", "Lesen & Freigeben"),
    ("kontakte", "/kontakte", "Kontakte"),
    ("postfach", "/postfach", "Postfach"),
    ("domains", "/domains", "Gesperrte Domains"),
    ("kunden", "/kunden", "Angebote"),
    ("so-funktionierts", "/so-funktionierts", "So funktioniert's"),
]


def nav_kontext(request: Request) -> list[dict]:
    daten_dir = getattr(request.app.state, "daten_dir", None)
    pruefen_badge = wartende_anzahl(daten_dir) if daten_dir is not None else 0
    return [
        {
            "url": url, "label": label, "aktiv": request.url.path == url,
            "badge": pruefen_badge if (key == "pruefen" and pruefen_badge) else None,
        }
        for key, url, label in NAV_BEREICHE
    ]

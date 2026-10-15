"""IT-Firmen in einer Nicht-IT-Liste erkennen.

Dafina, 15.10.2026: "qka tken zona IT largoj ne fund se sna duhen" - was
an IT in der Zone haengt, kommt am Ende raus.

Das Profil-Urteil haelt sie schon draussen. Das hier ist das Netz
darunter: der Prozess-Prompt ist neu und an echten Firmen nie erprobt,
und in der Rohernte der Zone 32 waren 12 Prozent IT (25 "IT-Berater" und
24 "Softwareentwickler/-hersteller" von 400 Orten).

Drei Regeln, alle aus der Erfahrung dieses Projekts:

  - EINDEUTIGE STAEMME ueberall im Wort. Deutsch baut zusammen:
    "Softwareentwickler", "EDV-Service", "Systemhaus Nord". Wer hier auf
    Wortgrenzen bestuende, faende keinen davon.

  - "IT" NUR IN GROSSBUCHSTABEN. Als Silbe steckt "it" in Qualitaet,
    Sicherheit, Mitarbeiter, Capital - lauter Woerter des Zielprofils.
    Gross geschrieben ist es dagegen immer die Branche: "IT-Berater",
    "BusinessIT". Nicht neben anderen Grossbuchstaben, sonst faengt es
    Abkuerzungen wie "MIT" oder "ITK".

  - DIE KATEGORIE ALLEIN ENTSCHEIDET NICHT (Dafina, 03.09.2026). Google
    vergibt vier bis fuenf Kategorien je Firma; am 31.08. warf eine harte
    Kategorie-Regel 61 Firmen raus, und die Webseite holte 12 echte
    zurueck. Ein klares Urteil der Webseite schlaegt die Kategorie - der
    Fund wird aber trotzdem gemeldet, damit ein Mensch ihn sehen kann.
"""
from __future__ import annotations

import re

# Eindeutige Staemme: ueberall im Wort gesucht, Gross/Klein egal.
IT_STAEMME = (
    "software", "informatik", "systemhaus", "computer", "edv",
    "rechenzentrum", "webhosting", "cybersecurity", "netzwerktechnik",
    "hardware", "it-dienstleist", "it-service", "it-support",
)

# "IT" nur gross und nicht neben anderen Grossbuchstaben.
_IT_GROSS = re.compile(r"(?<![A-ZÄÖÜ])IT(?![A-ZÄÖÜ])")

# "Prozess" im Urteil heisst: die Webseite hat Prozessberatung bestaetigt.
_PROZESS_URTEIL = re.compile(r"prozess|organisationsberatung|refa",
                             re.IGNORECASE)


def _treffer(text: str) -> list:
    text = str(text or "")
    klein = text.lower()
    funde = [stamm for stamm in IT_STAEMME if stamm in klein]
    if _IT_GROSS.search(text):
        funde.append("IT")
    return funde


def ist_it_firma(firma: dict) -> tuple:
    """(ja, grund) - sieht diese Firma nach IT aus?

    `grund` nennt die Fundstellen, auch wenn das Urteil sie ueberstimmt:
    ein stiller Fund waere wertlos, der Mensch soll ihn sehen koennen.
    """
    funde = []
    for kategorie in firma.get("categories") or []:
        for wort in _treffer(kategorie):
            funde.append(f"kategoria {kategorie!r} ({wort})")
    for feld in ("name", "profil_typ"):
        wert = str(firma.get(feld) or "")
        for wort in _treffer(wert):
            funde.append(f"{feld} {wert!r} ({wort})")

    if not funde:
        return False, ""
    grund = "; ".join(funde)

    # Die Webseite hat Prozessberatung bestaetigt - das schlaegt die
    # Kategorie, aber der Fund bleibt sichtbar.
    urteil = str(firma.get("profil_typ") or "")
    if _PROZESS_URTEIL.search(urteil) and not _treffer(urteil):
        return False, grund
    return True, grund

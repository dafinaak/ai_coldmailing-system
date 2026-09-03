"""Sperrlisten-Pruefung an jeder Stelle mit derselben Regel.

Bis 03.09.2026 stand diese Pruefung nur im Dropcontact-Schritt, also VOR
der Bezahlung. Das schuetzt das Guthaben, aber nicht den Empfaenger: die
fertigen Listen der Zonen 33 und 34 enthielten sechs Firmen aus
sperrliste-global.yaml (kisocon, Mibema, netgo tax, BLUVIT, GRAPHISOFT
Kassel, elastify). Ihre Batches liefen am 28.08.2026 - bevor Dafina die
Eintraege am 31.08. anlegte - und der Listenbau fragte die Sperrliste nie
wieder.

Die Projektregel sagt: die Sperrliste wirkt am letzten Tor vor Instantly.
Die fertige Liste IST dieses Tor. Damit beide Stellen dieselbe Wahrheit
erzaehlen, steht die Regel jetzt einmal hier statt zweimal nebeneinander.
"""
from __future__ import annotations

import re


def domain_von(wert) -> str:
    """Nur der Hostname, klein, ohne "www." - so wie die Sperrliste ihn
    schreibt."""
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().lower())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def gesperrte_domains(eintraege) -> set:
    """Die Domains aus der Sperrliste. Eintraege ohne Domain (etwa eine
    einzelne E-Mail) werden uebergangen - sie sagen nichts ueber eine
    ganze Firma aus. Ein fuehrendes "*." faellt weg, weil Subdomains
    ohnehin mitgesperrt sind."""
    return {str(e.get("domain", "")).lower().lstrip("*.")
            for e in (eintraege or []) if e.get("domain")}


def ist_gesperrt(webseite, domains) -> bool:
    """Gilt diese Webseite als gesperrt?

    Getroffen wird die Domain selbst und alles darunter. Ein blosser
    Namensteil reicht NICHT: "nicht-elastify.net" ist eine andere Firma
    als "elastify.net", und eine Sperre auf Verdacht waere schlimmer als
    keine. Ohne Domain wird nicht gesperrt - was wir nicht belegen
    koennen, werfen wir nicht raus."""
    domain = domain_von(webseite)
    if not domain or not domains:
        return False
    return any(domain == d or domain.endswith("." + d) for d in domains)

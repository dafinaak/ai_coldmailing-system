"""Pick companies out of an already collected pool - instantly.

Finding companies is the fast half of our lead work: they were gathered
once (Google Maps, Gelbe Seiten, OpenStreetMap) and sit in a JSON file.
Building the e-mail addresses is the slow half. This module does only
the fast half, so the wizard can show a result the moment somebody
presses a button, and leave the waiting to the background.

What can actually be filtered is limited by what the sources gave us:
location (via postal code), the service categories they were listed
under, and the blocklist. Company size is NOT here - no source we use
delivers an employee count, and a filter that silently matches nothing
is worse than no filter.

Companies whose postal code is missing or unknown are never silently
dropped from a radius search. They come back in their own group so a
human can decide - a quietly shortened list looks exactly like a
complete one.
"""

from __future__ import annotations

import re

from pipeline.plz_geo import entfernung_km, mittelpunkt, punkt_fuer_plz


def _text_der_firma(firma: dict) -> str:
    teile = [str(firma.get("name") or "")]
    teile += [str(k) for k in (firma.get("categories") or [])]
    teile.append(str(firma.get("branche_typ") or ""))
    return " ".join(teile).casefold()


def passt_zum_dienst(firma: dict, dienste) -> bool:
    """True if any of the wanted services shows up in name or categories."""
    begriffe = [str(d).strip().casefold() for d in (dienste or []) if str(d).strip()]
    if not begriffe:
        return True
    text = _text_der_firma(firma)
    return any(b in text for b in begriffe)


def _domain(wert: object) -> str:
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().casefold())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def ist_gesperrt(firma: dict, gesperrte) -> bool:
    """Blocklist check, including '*.bund.de' style patterns."""
    domain = _domain(firma.get("domain") or firma.get("website"))
    if not domain:
        return False
    for eintrag in gesperrte or []:
        muster = str(eintrag).strip().casefold().lstrip("*.")
        if not muster:
            continue
        if domain == muster or domain.endswith("." + muster):
            return True
    return False


def filtern(firmen: list, *, ort: str = "", radius_km: float | None = None,
            dienste=(), gesperrte_domains=(), nur_mit_webseite: bool = True,
            plz_tabelle_pfad: str | None = None) -> dict:
    """Filter a company pool.

    Returns {"treffer", "ohne_ort", "zahlen"}:
      treffer  - companies that match everything asked for
      ohne_ort - match the service, but their location is unknown, so a
                 radius search cannot judge them (shown separately)
      zahlen   - counts for the wizard's result screen
    """
    zentrum = mittelpunkt(ort, plz_tabelle_pfad) if ort else None
    if ort and zentrum is None:
        raise ValueError(
            f"Der Ort '{ort}' wurde nicht gefunden. Bitte eine deutsche "
            f"Postleitzahl (z.B. 30159) oder einen Ortsnamen (z.B. Hannover) "
            f"eingeben.")
    mit_umkreis = zentrum is not None and radius_km is not None

    treffer, ohne_ort = [], []
    zahlen = {"gesamt": len(firmen), "raus_dienst": 0, "raus_gesperrt": 0,
              "raus_ohne_webseite": 0, "raus_umkreis": 0}

    for firma in firmen:
        if nur_mit_webseite and not firma.get("website"):
            zahlen["raus_ohne_webseite"] += 1
            continue
        if ist_gesperrt(firma, gesperrte_domains):
            zahlen["raus_gesperrt"] += 1
            continue
        if not passt_zum_dienst(firma, dienste):
            zahlen["raus_dienst"] += 1
            continue
        if not mit_umkreis:
            treffer.append(firma)
            continue

        punkt = punkt_fuer_plz(firma.get("plz"), plz_tabelle_pfad)
        if punkt is None:
            ohne_ort.append(firma)
            continue
        km = entfernung_km(zentrum, punkt)
        if km <= radius_km:
            treffer.append({**firma, "entfernung_km": round(km, 1)})
        else:
            zahlen["raus_umkreis"] += 1

    treffer.sort(key=lambda f: f.get("entfernung_km", 0))
    zahlen["treffer"] = len(treffer)
    zahlen["ohne_ort"] = len(ohne_ort)
    return {"treffer": treffer, "ohne_ort": ohne_ort, "zahlen": zahlen}


def dienste_vorschlagen(firmen: list, anzahl: int = 15) -> list:
    """The most common categories in the pool - fills the filter chips.

    Better than a hand-written list: it can only offer services that
    really occur, so a chosen filter never comes back empty.
    """
    import collections
    zaehler = collections.Counter()
    for firma in firmen:
        for kategorie in firma.get("categories") or []:
            text = str(kategorie).strip()
            if text and "=" not in text:      # "office=it" ist Maschinen-Kram
                zaehler[text] += 1
    return [name for name, _ in zaehler.most_common(anzahl)]

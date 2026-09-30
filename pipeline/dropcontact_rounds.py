"""Paying Dropcontact only for what we can use (Dafina, 29.09.2026).

Dropcontact refunds a row where it finds no address and charges a row
where it finds one - also a catch-all address, which our rule throws away
because it cannot be checked: the domain takes every address. Measured on
zone 40 (29.09.2026): 8 of 73 people came back catch-all, and two people
were asked twice because their company is on the map with two websites.

Helpers for the zone tool (werkzeuge/zona32-dropcontact.py) and the
register (pipeline/dropcontact_register.py):

  split_rounds    one person on two sites of the same company is asked
                  once; the other site waits for a second round and is
                  asked only when the first gave no usable address
  paid_unusable   the addresses a batch paid for that we cannot send to -
                  kept, so nothing paid for is thrown away; the catch-all
                  ones also close their domain in the register
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

USABLE = "nominative@pro"
CATCH_ALL = ("catch-all", "catch_all")    # the API writes the first, the docs the second

# Words that say what a company does, what legal form it has or which top
# level domain it uses - not which company it is. Place names are added
# from the postal code table (_place_words).
EVERYDAY = frozenset((
    "gmbh", "mbh", "und", "and", "the", "der", "die", "das", "fuer", "ihr",
    "www", "info", "online", "shop", "service", "services", "systems",
    "system", "systemhaus", "solutions", "solution", "computer", "computers",
    "consulting", "consult", "beratung", "technik", "technology", "tech",
    "support", "netzwerk", "netzwerke", "network", "networks", "dienstleister",
    "dienstleistung", "dienstleistungen", "software", "digital", "media",
    "data", "daten", "cloud", "security", "sicherheit", "group", "gruppe",
    "partner", "team", "betriebs", "management", "gesellschaft",
    "international", "germany", "deutschland", "kontakt", "impressum",
    "home", "startseite", "standorte", "unternehmen", "about", "firma",
))


def _plain(text) -> str:
    """Lower case, umlauts written out, accents gone: 'Düsseldorf' -> 'duesseldorf'."""
    text = str(text or "").casefold()
    for umlaut, written in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, written)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _words(text) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", _plain(text)) if w}


@lru_cache(maxsize=1)
def _place_words() -> frozenset:
    """Every word of a German place name - 'duesseldorf', 'neuss', 'main'.
    Two firms that share only their town are not one company."""
    try:
        from pipeline.plz_geo import plz_tabelle
        return frozenset(w for entry in plz_tabelle().values()
                         for w in _words(entry["ort"]))
    except (OSError, KeyError):       # without the table: no place words
        return frozenset()


def domain_of(website_or_email) -> str:
    """'https://www.a.de/x' -> 'a.de', 'anna@a.de' -> 'a.de'."""
    text = str(website_or_email or "").strip().lower()
    if "@" in text and "/" not in text:
        return text.rsplit("@", 1)[1]
    bare = re.sub(r"^https?://", "", text)
    return re.sub(r"^www\.", "", bare).split("/")[0]


def _company_words(request: dict) -> set:
    """What tells this company apart: words of its domain and its name,
    without everyday words, place names and anything shorter than 4."""
    words = _words(domain_of(request.get("website")).replace(".", " ")) \
        | _words(request.get("company"))
    return {w for w in words
            if len(w) >= 4 and w not in EVERYDAY and w not in _place_words()}


def _person(request: dict) -> tuple:
    return (" ".join(_words(request.get("first_name"))),
            " ".join(_words(request.get("last_name"))))


def split_rounds(requests: list) -> tuple:
    """([positions for the first round], {later position: the one it waits for}).

    Two requests are the same person at the same company when the full
    name matches AND the two companies share a word of their own (domain or
    name). A common name alone is not enough: a second Thomas Mueller at
    another company must still be asked."""
    first, later, seen = [], {}, []
    for nr, request in enumerate(requests):
        person, words = _person(request), _company_words(request)
        match = None
        if all(person):
            match = next((i for other, other_words, i in seen
                          if other == person and other_words & words), None)
        if match is None:
            first.append(nr)
            seen.append((person, words, nr))
        else:
            later[nr] = match
    return first, later


def is_catch_all(qualification) -> bool:
    return str(qualification or "").split("@")[0] in CATCH_ALL


def usable(row: dict) -> bool:
    return any(e.get("qualification") == USABLE and e.get("email")
               for e in (row or {}).get("email") or [])


def paid_unusable(sent: list, rows: list) -> list:
    """The address Dropcontact charged for but we cannot send to, one per
    person: catch-all, generic (info@) or private. An invalid address is
    no result - Dropcontact does not charge it, and it is left out."""
    kept = []
    for request, row in zip(sent, rows):
        if usable(row):
            continue
        for entry in (row or {}).get("email") or []:
            qualification = str(entry.get("qualification") or "")
            if entry.get("email") and not qualification.startswith("invalid"):
                kept.append({"first_name": request.get("first_name", ""),
                             "last_name": request.get("last_name", ""),
                             "website": request.get("website", ""),
                             "email": entry["email"],
                             "qualification": qualification})
                break
    return kept

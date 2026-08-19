"""Decision-maker priority for found company contacts.

Oliver's request (19.08.2026): the contact of a company must be the
person most likely to make a purchasing or partnership decision - never
just any employee. When several leaders are found, ONE is marked as the
primary decision-maker, in this order:

  1. CEO / Geschaeftsfuehrer
  2. Owner / Inhaber
  3. Founder / Co-Founder / Gruender
  4. Managing Director / Geschaeftsleitung / Betriebsleitung
  5. any other company leader (Vorstand, Direktor, Prokurist, ...)

The imprint stage sorts its persons through sort_by_priority() before
the paid address building runs, so the first (and often only) paid
lookup goes to the best-ranked person. build_entscheider() turns what
was read and what was verified into the record stored per company -
INCLUDING leaders whose address could not be verified ("ohne_mail"):
a found name must not vanish just because no mailbox was proven.
"""

from __future__ import annotations

# Substring match on a normalised title (casefold, umlauts flattened).
ROLE_GROUPS: tuple = (
    ("ceo", "geschaeftsfuehr", "chief executive"),
    ("inhaber", "owner", "eigentuem"),
    ("gruender", "founder"),
    ("managing director", "geschaeftsleit", "betriebsleit"),
    ("vorstand", "direktor", "director", "leiter", "leader", "executive",
     "prokurist", "head of", "partner"),
)


def _norm(text: object) -> str:
    wert = str(text or "").casefold()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        wert = wert.replace(a, b)
    return wert


def rank_role(rolle: object) -> int:
    """0 = best (CEO group); len(ROLE_GROUPS) = unknown/none."""
    text = _norm(rolle)
    if text:
        for rang, begriffe in enumerate(ROLE_GROUPS):
            if any(b in text for b in begriffe):
                return rang
    return len(ROLE_GROUPS)


def sort_by_priority(personen: list) -> list:
    """Stable sort of {"vorname", "nachname", "rolle", ...} dicts."""
    return sorted(personen or [], key=lambda p: rank_role(p.get("rolle")))


def build_entscheider(gelesene_personen: list, kontakte: list) -> list:
    """The decision-maker record stored per company.

    gelesene_personen: what the imprint reading produced (may lack a
    verified address). kontakte: contacts that DID get a verified
    address (any stage). Returns priority-sorted entries; index 0 is the
    primary decision-maker. Empty list when nothing was found.
    """
    eintraege = []
    gesehen = {}
    for person in sort_by_priority(gelesene_personen):
        eintrag = {
            "vorname": person.get("vorname", ""),
            "nachname": person.get("nachname", ""),
            "name": f"{person.get('vorname', '')} "
                    f"{person.get('nachname', '')}".strip(),
            "rolle": person.get("rolle") or "",
            "linkedin": person.get("linkedin") or None,
            "quelle": "impressum",
            "status": "ohne_mail",
        }
        eintraege.append(eintrag)
        gesehen[_norm(eintrag["name"])] = eintrag

    for kontakt in kontakte or []:
        name = (f"{kontakt.get('first_name', '')} "
                f"{kontakt.get('last_name', '')}").strip()
        if not name:
            continue      # info@-Rueckfall ist keine Person
        bekannt = gesehen.get(_norm(name))
        if bekannt is None:
            bekannt = {"vorname": kontakt.get("first_name", ""),
                       "nachname": kontakt.get("last_name", ""),
                       "name": name,
                       "rolle": kontakt.get("title") or "",
                       "linkedin": None,
                       "quelle": kontakt.get("source", ""),
                       "status": "ohne_mail"}
            eintraege.append(bekannt)
            gesehen[_norm(name)] = bekannt
        bekannt["status"] = "mail_geprueft"
        bekannt["email"] = kontakt.get("email", "")
        if not bekannt.get("rolle") and kontakt.get("title"):
            bekannt["rolle"] = kontakt["title"]

    return sort_by_priority(eintraege)

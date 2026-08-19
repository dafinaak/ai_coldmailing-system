"""Service category families for filters and collection.

Oliver's request (19.08.2026): selecting "Computer Services" must not be
an exact keyword - it stands for the whole family of IT services such a
company may offer (networking, software development, security, cloud and
so on). ONE mapping serves every consumer, so the behaviour cannot
drift apart:

  - step 3 of the campaign form (family choice in the UI),
  - the live inventory counter while typing,
  - the step-4 pool filter (pipeline.firmen_filter.filtern),
  - the paid fresh collection (pipeline.firmen_sammeln).

Two views on purpose:

  expand_for_matching()  broad term list for FREE substring matching
                         against what the directories listed a company
                         under. Being generous costs nothing.
  expand_for_search()    deliberately SHORT list of strong German search
                         queries for the PAID scrapers - every term
                         crawls up to its own result limit, so a broad
                         list here would multiply the bill.

German terms dominate because the directories we search (Google Maps,
Gelbe Seiten, OpenStreetMap) list German companies under German labels;
the English aliases make the family selectable either way.

Standing exclusions: pipeline.listen_fusion.AUSSCHLUESSE (Oliver,
29.07.2026) still removes hosting, plain hardware trade, data centres,
internet providers and automation providers AT COLLECTION TIME. Those
sub-families are therefore left out of the search terms - paying to
scrape companies the fusion would immediately throw away helps nobody.
If Oliver lifts the exclusion, add the terms here and they flow through
everywhere at once.
"""

from __future__ import annotations

_COMPUTER_SERVICES = {
    # How a person may type/select the family itself.
    "aliases": (
        "computer services", "computer service", "computerservice",
        "computer-service", "computerdienste", "it services", "it-services",
        "it service", "it-service", "it dienstleistungen",
        "it-dienstleistungen", "it-dienstleister", "edv-service",
        "edv-dienstleistungen",
    ),
    # Shown in the form so a person sees what the family covers.
    "anzeige": (
        "IT-Service & Support", "IT-Beratung", "Managed IT",
        "Netzwerk & Netzwerktechnik", "IT-Sicherheit & Cybersecurity",
        "Softwareentwicklung", "Web- & App-Entwicklung", "Cloud-Dienste",
        "Systemintegration & DevOps", "IT-Infrastruktur & Server",
        "Datenbanken & Datenmanagement", "ERP- & CRM-Dienste",
        "Microsoft-365-Dienste", "Backup & Datensicherung",
        "Computer-Reparatur & Wartung", "KI & Machine Learning",
        "Digitalisierung",
    ),
    # Free matching against name/categories of already collected firms.
    "match_terms": (
        "computerservice", "computer service", "computer-service",
        "computerdienst", "computer repair", "computerreparatur",
        "edv", "it-dienstleist", "it dienstleist", "it-service",
        "it service", "it-support", "it support", "computer support",
        "it-berat", "it consulting", "it-consulting", "it-beratung",
        "managed service", "managed it", "systemhaus",
        "netzwerk", "network", "systemintegration", "system integration",
        "it-sicherheit", "it security", "cybersecurity", "cyber security",
        "informationssicherheit", "information security",
        "software", "softwareentwicklung", "software development",
        "software engineering", "webentwicklung", "web development",
        "webdesign", "app-entwicklung", "app development",
        "anwendungsentwicklung", "application development",
        "cloud", "devops", "it-infrastruktur", "it infrastructure",
        "server", "datenbank", "database", "datenmanagement",
        "data management", "it-outsourcing", "it outsourcing",
        "it-lösung", "it-loesung", "it solutions", "digitalisierung",
        "digitalization", "erp", "crm", "microsoft 365", "m365",
        "microsoft-365", "backup", "datensicherung", "disaster recovery",
        "hardware-service", "hardware service", "it-wartung",
        "telekommunikation", "telecommunication",
        "ki-", "künstliche intelligenz", "kuenstliche intelligenz",
        "artificial intelligence", "machine learning",
    ),
    # Paid searching: few, strong, German. Order = priority.
    "search_terms": (
        "IT-Dienstleister", "IT-Service", "Computerservice",
        "IT-Systemhaus", "EDV-Dienstleistungen", "IT-Support",
        "Netzwerktechnik", "Softwareentwicklung", "IT-Sicherheit",
        "Cloud-Dienstleistungen",
    ),
}

CATEGORIES: dict[str, dict] = {
    "Computer Services": _COMPUTER_SERVICES,
}


def _key(term: object) -> str:
    return " ".join(str(term or "").casefold().split())


def family_of(term: object) -> str | None:
    """Canonical family name if the term names a family, else None."""
    gesucht = _key(term)
    if not gesucht:
        return None
    for name, familie in CATEGORIES.items():
        if gesucht == _key(name) or gesucht in map(_key, familie["aliases"]):
            return name
    return None


def families() -> dict[str, tuple]:
    """{family name: display subcategories} - for the step-3 form."""
    return {name: familie["anzeige"] for name, familie in CATEGORIES.items()}


def _dedupe(terms) -> list:
    gesehen, ergebnis = set(), []
    for term in terms:
        wert = str(term).strip()
        schluessel = _key(wert)
        if wert and schluessel not in gesehen:
            gesehen.add(schluessel)
            ergebnis.append(wert)
    return ergebnis


def expand_for_matching(dienste) -> list:
    """Selected terms plus, for every family among them, its match terms.

    Non-family terms pass through untouched, so free-text filters keep
    working exactly as before.
    """
    ergebnis = []
    for dienst in dienste or []:
        ergebnis.append(dienst)
        familie = family_of(dienst)
        if familie:
            ergebnis.extend(CATEGORIES[familie]["match_terms"])
    return _dedupe(ergebnis)


def expand_for_search(dienste, max_terms: int = 10) -> list:
    """Search queries for the paid collection.

    A family becomes its short curated query list; plain terms stay as
    they are. Capped, because every query crawls up to its own result
    limit and is billed accordingly.
    """
    ergebnis = []
    for dienst in dienste or []:
        familie = family_of(dienst)
        if familie:
            ergebnis.extend(CATEGORIES[familie]["search_terms"])
        else:
            ergebnis.append(dienst)
    return _dedupe(ergebnis)[:max(1, max_terms)]

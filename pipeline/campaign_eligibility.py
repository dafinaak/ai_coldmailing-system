"""The strict campaign-eligibility rule (Oliver, Phase 1, 20.08.2026).

A contact may be a CAMPAIGN RECIPIENT only if ALL of this holds:

  - a NAMED decision-maker (first and last name are known),
  - the address is a PERSONAL business address - never a company inbox
    like info@, contact@, office@, sales@, support@ ...,
  - the address is VERIFIED by a provider we trust.

General company inboxes stay RECORDED as company information (Oliver
wants every discovered fact kept) - they are simply never sent to.

Enforced in FOUR places, so one missed spot cannot leak a generic
address into a campaign (defence in depth):

  1. lead creation      pipeline.sourcing / pipeline.schnelllauf -
                        a general address never becomes a lead;
  2. text generation    pipeline.__main__.lauf - resumed OLD run
                        folders may still hold such leads on disk;
  3. handover           pipeline.__main__._versand_ausfuehren -
                        approved texts are filtered again;
  4. Instantly import   pipeline.senders.instantly - the final gate
                        REFUSES generic recipients loudly.

Historical run folders and the already-handed-over campaign in
Instantly are never modified - the rule applies to everything that
flows towards Instantly from now on.
"""

from __future__ import annotations

# Local parts that mark a company inbox, not a person. Exact match on
# the part before the "@" (case-insensitive). Deliberately a fixed,
# readable list - predictable beats clever here.
GENERIC_LOCALPARTS = frozenset({
    "info", "contact", "kontakt", "office", "buero", "büro", "sales",
    "vertrieb", "hello", "hallo", "hi", "support", "hilfe", "service",
    "mail", "email", "post", "team", "admin", "webmaster", "marketing",
    "presse", "press", "jobs", "karriere", "bewerbung", "buchhaltung",
    "rechnung", "invoice", "billing", "noreply", "no-reply",
    "newsletter", "anfrage", "kundenservice", "zentrale", "empfang",
    "impressum",
})

# Sources whose personal addresses are verified BY CONSTRUCTION:
# Dropcontact only returns addresses it verified live, Hunter contacts
# are only accepted with verification_status "valid" (see
# pipeline.sourcing._verifizierte_email), Prospeo delivered only
# verified addresses. "impressum" marks the imprint stage, whose
# addresses are always built AND verified by Dropcontact.
# Anything else - including an empty source - fails CLOSED.
VERIFIED_PERSONAL_SOURCES = frozenset(
    {"dropcontact", "hunter", "impressum", "prospeo"})


def is_generic_email(email: object) -> bool:
    """True for company inboxes (info@ ...) and for unusable addresses."""
    adresse = str(email or "").strip().lower()
    if "@" not in adresse:
        return True
    lokal = adresse.split("@", 1)[0]
    return lokal in GENERIC_LOCALPARTS


def _feld(lead: object, name: str) -> str:
    if isinstance(lead, dict):
        return str(lead.get(name) or "")
    return str(getattr(lead, name, "") or "")


def lead_eligibility(lead: object) -> tuple:
    """(kampagnentauglich, grund) fuer einen Lead (Objekt oder dict).

    grund ist "" wenn tauglich, sonst einer von:
      "generic_email"            Sammeladresse oder unbrauchbare Adresse
      "no_named_decision_maker"  kein Vor- UND Nachname bekannt
      "email_not_verified"       Quelle buergt nicht fuer eine Pruefung
    """
    if is_generic_email(_feld(lead, "email")):
        return False, "generic_email"
    if not (_feld(lead, "first_name").strip()
            and _feld(lead, "last_name").strip()):
        return False, "no_named_decision_maker"
    if _feld(lead, "source").strip().lower() not in VERIFIED_PERSONAL_SOURCES:
        return False, "email_not_verified"
    return True, ""


def eligible_leads(leads) -> tuple:
    """(tauglich, aussortiert) - aussortiert als [{email, grund}]."""
    tauglich, aussortiert = [], []
    for lead in leads or []:
        ok, grund = lead_eligibility(lead)
        if ok:
            tauglich.append(lead)
        else:
            aussortiert.append({"email": _feld(lead, "email"),
                                "grund": grund})
    return tauglich, aussortiert

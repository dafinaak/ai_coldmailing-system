"""Provider registry for the waterfall (Oliver's spec, 19.08.2026).

ONE place that answers: which sources exist, what can each one do, and
is it usable right now? The waterfall UI and the CLI read this instead
of guessing - so "LinkedIn not configured" is a shown fact, never a
faked integration.

Rules baked in:
- implemented=False providers are DECLARED ONLY. Nothing in the code
  pretends to call them; they wait for credentials AND a human decision.
- configured() only checks whether the required environment variables
  are present - it never spends money or calls the network.
- Order = the intended waterfall order from Oliver's mail.

History that matters when deciding about the declared ones:
- North Data was evaluated and dropped on 29.07.2026 ("has no emails,
  only names") - it may still be useful for names/roles, Oliver's call.
- Apollo was tried in July and abandoned (broken enrich endpoint).
- Prospeo's account died during their API rework (29.07.2026).
- LinkedIn scraping has terms-of-service implications - needs a human
  decision, not just a key.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    name: str
    # What the source can contribute, in the spec's vocabulary:
    # company_discovery, address, phone, website, decision_makers,
    # email_discovery, email_verification, contact_enrichment,
    # company_details
    capabilities: tuple
    env_keys: tuple = ()
    implemented: bool = True
    hinweis: str = ""

    def configured(self) -> bool:
        return all(os.environ.get(k) for k in self.env_keys)

    def status(self) -> str:
        if not self.implemented:
            return "nicht implementiert"
        if not self.configured():
            return "kein Zugang (.env)"
        return "bereit"


# Waterfall order per Oliver's mail (19.08.2026). "intern" first: the
# existing company pool is always step 1 and costs nothing.
PROVIDERS: tuple = (
    Provider("intern (Bestand)", ("company_discovery", "company_details"),
             hinweis="laeufe/leadquellen/* - immer Stufe 1, kostenlos"),
    Provider("google_maps", ("company_discovery", "address", "phone",
                             "website"),
             env_keys=("APIFY_API_KEY",)),
    Provider("overpass_osm", ("company_discovery", "address", "phone",
                              "website"),
             hinweis="kostenlos, gedrosselt; nur office=it-Eintraege"),
    Provider("gelbe_seiten", ("company_discovery", "address", "phone",
                              "website", "email_discovery"),
             env_keys=("APIFY_API_KEY",)),
    Provider("impressum_ki", ("decision_makers",),
             env_keys=("OPENAI_API_KEY",),
             hinweis="eigene Stufe: Webseiten-Impressum + KI, nur Namen/"
                     "Rollen - Adressen baut immer ein bezahlter Anbieter"),
    Provider("hunter", ("email_discovery", "email_verification",
                        "decision_makers"),
             env_keys=("HUNTER_API_KEY",),
             hinweis="Frei-Kontingent 50 Suchen + 100 Pruefungen/Monat"),
    Provider("dropcontact", ("contact_enrichment", "email_discovery",
                             "email_verification"),
             env_keys=("DROPCONTACT_API_KEY",),
             hinweis="baut + prueft persoenliche Adressen (DSGVO-live)"),
    Provider("linkedin", ("decision_makers", "contact_enrichment"),
             implemented=False,
             hinweis="nicht gebaut: braucht Zugang UND eine Entscheidung "
                     "zu den Nutzungsbedingungen"),
    Provider("apollo", ("company_discovery", "decision_makers",
                        "email_discovery"),
             implemented=False,
             hinweis="im Juli probiert und verworfen (Enrich-Endpunkt "
                     "kaputt) - Neuanlauf nur mit neuem Zugang"),
    Provider("clay", ("contact_enrichment", "email_discovery"),
             implemented=False,
             hinweis="nicht gebaut: kein Konto/Zugang vorhanden"),
    Provider("north_data", ("company_discovery", "decision_makers",
                            "company_details"),
             implemented=False,
             hinweis="am 29.07.2026 gestrichen (keine E-Mails, nur Namen) "
                     "- fuer Namen/Rollen ggf. neu entscheiden"),
    Provider("prospeo", ("decision_makers", "email_discovery"),
             env_keys=("PROSPEO_API_KEY",),
             hinweis="Konto beim API-Umbau des Anbieters gestorben "
                     "(29.07.2026); Baustein existiert noch"),
    Provider("fullenrich", ("company_discovery", "decision_makers",
                            "email_discovery", "phone_discovery"),
             env_keys=("FULLENRICH_API_KEY",),
             hinweis="NUR im Vergleichstest (POC 24.08.2026, Befehl "
                     "'fullenrich-poc'). Nicht Teil der Produktivkaskade, "
                     "solange die 100-Firmen-Messung nicht vorliegt"),
)


def uebersicht() -> list:
    """[{name, faehigkeiten, status, hinweis}] - fuer CLI und Oberflaeche."""
    return [{"name": p.name,
             "faehigkeiten": list(p.capabilities),
             "status": p.status(),
             "hinweis": p.hinweis} for p in PROVIDERS]


def bereit(capability: str) -> list:
    """Names of providers that are implemented, configured and offer the
    capability - the honest answer to "what can the waterfall use NOW"."""
    return [p.name for p in PROVIDERS
            if p.implemented and p.configured()
            and capability in p.capabilities]

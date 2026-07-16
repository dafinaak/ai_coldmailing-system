import time
import requests
from pipeline.models import Lead

# Live-Doku (docs.apollo.io/reference/people-api-search, OpenAPI-Spec-Auszug,
# geprüft 2026-07-16): Base-URL ist https://api.apollo.io/api/v1, der
# People-Search-Pfad ist "/mixed_people/api_search" (nicht "/mixed_people/search"
# wie im Task-Brief-Entwurf). Auth-Header laut Doku "x-api-key" (Groß-/
# Kleinschreibung bei HTTP-Headern egal, daher "X-Api-Key" beibehalten).
# Antwort-Hülle ist bestätigt {"people": [...], "total_entries": ...}.
URL = "https://api.apollo.io/api/v1/mixed_people/api_search"

class ApolloSource:
    def __init__(self, api_key, session=None, wartezeit=5):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit

    def search(self, zielgruppe: dict, limit: int):
        body = {
            "person_titles": zielgruppe.get("titel", []),
            "person_locations": zielgruppe.get("region", []),
            "organization_num_employees_ranges": zielgruppe.get("firmengroesse", []),
            "per_page": min(limit, 100), "page": 1,
        }
        antwort = self._post_mit_wiederholung(body)
        leads = []
        for p in antwort.json().get("people", [])[:limit]:
            # Laut Live-Doku liefert dieser Such-Endpunkt keine E-Mail-Adressen
            # oder Telefonnummern zurück ("This endpoint doesn't return email
            # addresses or phone numbers" — People API Search, docs.apollo.io).
            # E-Mails müssten über People Enrichment nachgeladen werden (nicht
            # Teil dieses Tasks). Bis dahin greift die Brief-Vorgabe "Leads ohne
            # E-Mail werden übersprungen" unverändert.
            if not p.get("email"):
                continue
            org = p.get("organization") or {}
            leads.append(Lead(
                first_name=p.get("first_name", ""),
                # "last_name" ist die Vollform; die Live-Doku zeigt für den
                # Such-Endpunkt zusätzlich ein "last_name_obfuscated"-Feld
                # (z. B. "Do***e") als Datenschutz-Fallback, falls der volle
                # Nachname nicht mitgeliefert wird.
                last_name=p.get("last_name") or p.get("last_name_obfuscated", ""),
                email=p["email"], company=org.get("name", ""), title=p.get("title", ""),
                website=org.get("website_url", ""), source="apollo"))
        return leads

    def _post_mit_wiederholung(self, body):
        for versuch in range(3):
            antwort = self.session.post(
                URL, json=body, timeout=30,
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"})
            if antwort.status_code < 400:
                return antwort
            time.sleep(self.wartezeit * (versuch + 1))
        raise RuntimeError(f"Apollo antwortet dauerhaft mit {antwort.status_code}")

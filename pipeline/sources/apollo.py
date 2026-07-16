import time
import requests
from pipeline.models import Lead

# Live-Doku (docs.apollo.io, OpenAPI-Spec-Auszug, geprüft 2026-07-16):
#
# People API Search (docs.apollo.io/reference/people-api-search):
# Base-URL ist https://api.apollo.io/api/v1, der People-Search-Pfad ist
# "/mixed_people/api_search" (nicht "/mixed_people/search" wie im
# Task-Brief-Entwurf). Auth-Header laut Doku "x-api-key" (Groß-/
# Kleinschreibung bei HTTP-Headern egal, daher "X-Api-Key" beibehalten).
# Antwort-Hülle ist bestätigt {"people": [...], "total_entries": ...}.
# Die Doku sagt ausdrücklich: "This endpoint doesn't return email
# addresses or phone numbers." — deshalb der zweite Schritt unten.
#
# Bulk People Enrichment (docs.apollo.io/reference/bulk-people-enrichment):
# Pfad "/people/bulk_match", bis zu 10 Personen pro Aufruf (details[]-Array,
# hier per "id" aus dem Suchtreffer identifiziert). Liefert standardmäßig
# keine privaten E-Mails; der Query-Parameter "reveal_personal_emails=true"
# schaltet das frei (kann Credits kosten, siehe Doku). "reveal_phone_number"
# bleibt aus, weil das einen webhook_url voraussetzt und hier nicht gebraucht
# wird. Antwort-Hülle bestätigt: {"matches": [...], "status": ..., ...},
# jedes Match-Objekt kann "email" sowie ein volles "organization"-Objekt
# (u. a. "website_url") enthalten.
BASE_URL = "https://api.apollo.io/api/v1"
SUCH_URL = f"{BASE_URL}/mixed_people/api_search"
ANREICHERUNGS_URL = f"{BASE_URL}/people/bulk_match?reveal_personal_emails=true"
ANREICHERUNGS_BATCH_GROESSE = 10

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
        antwort = self._post_mit_wiederholung(SUCH_URL, body)
        treffer = antwort.json().get("people", [])[:limit]
        angereicherte_treffer = self._anreichern(treffer)

        leads = []
        for p in angereicherte_treffer:
            # Erst nach der Anreicherung über bulk_match kann eine E-Mail
            # vorhanden sein (die Such-Antwort selbst liefert nie eine).
            if not p.get("email"):
                continue
            org = p.get("organization") or {}
            leads.append(Lead(
                first_name=p.get("first_name", ""),
                # "last_name" ist die Vollform; die Such-Antwort liefert für
                # nicht angereicherte Treffer stattdessen ein
                # "last_name_obfuscated"-Feld (z. B. "Do***e") als
                # Datenschutz-Fallback.
                last_name=p.get("last_name") or p.get("last_name_obfuscated", ""),
                email=p["email"], company=org.get("name", ""), title=p.get("title", ""),
                website=org.get("website_url", ""), source="apollo"))
        return leads

    def _anreichern(self, treffer):
        """Reichert Suchtreffer über /people/bulk_match mit E-Mail-Adressen
        (und ggf. vollständigerem Namen/Titel/Website) an. Apollo erlaubt
        maximal 10 Personen pro Aufruf, daher wird in Gruppen aufgeteilt."""
        angereichert = []
        for start in range(0, len(treffer), ANREICHERUNGS_BATCH_GROESSE):
            batch = treffer[start:start + ANREICHERUNGS_BATCH_GROESSE]
            ids = [p["id"] for p in batch if p.get("id")]
            if not ids:
                angereichert.extend(batch)
                continue
            body = {"details": [{"id": pid} for pid in ids]}
            antwort = self._post_mit_wiederholung(ANREICHERUNGS_URL, body)
            matches = {m.get("id"): m for m in antwort.json().get("matches", [])}
            for p in batch:
                match = matches.get(p.get("id"))
                if match:
                    p = {**p, **{k: v for k, v in match.items() if v}}
                angereichert.append(p)
        return angereichert

    def _post_mit_wiederholung(self, url, body):
        for versuch in range(3):
            antwort = self.session.post(
                url, json=body, timeout=30,
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"})
            if antwort.status_code < 400:
                return antwort
            time.sleep(self.wartezeit * (versuch + 1))
        raise RuntimeError(f"Apollo antwortet dauerhaft mit {antwort.status_code}")

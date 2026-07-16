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
#
# TODO(verifizieren am echten Konto):
# (a) Die Zuordnung in _anreichern() matcht Suchtreffer und bulk_match-
#     Ergebnisse ausschliesslich ueber die Apollo-"id". Laut Doku ist das
#     der vorgesehene Weg, aber ungetestet ist, ob bulk_match bei manchen
#     Personen (z.B. geloeschte/zusammengefuehrte Datensaetze) die id
#     stillschweigend nicht zurueckliefert - dann wuerde dieser Treffer
#     unangereichert durchgereicht und mangels E-Mail spaeter uebersprungen
#     (stiller Unter-Match statt Fehler). Am echten Konto pruefen, ob das
#     vorkommt und ob ein Fallback (z.B. ueber first_name/last_name/
#     organization) noetig ist.
# (b) "reveal_personal_emails=true" kann laut Doku Credits verbrauchen -
#     wie viele pro aufgeloester Person und ob das auch bei einem "kein
#     Treffer/keine E-Mail vorhanden"-Ergebnis abgerechnet wird, ist am
#     echten Konto noch nicht verifiziert. Vor produktivem Einsatz mit
#     echtem Kontingent gegenpruefen, damit ein Lauf nicht ungeplant
#     Credits verbraucht.
BASE_URL = "https://api.apollo.io/api/v1"
SUCH_URL = f"{BASE_URL}/mixed_people/api_search"
ANREICHERUNGS_URL = f"{BASE_URL}/people/bulk_match?reveal_personal_emails=true"
ANREICHERUNGS_BATCH_GROESSE = 10

class ApolloSource:
    def __init__(self, api_key, session=None, wartezeit=5):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit
        self.uebersprungen_ohne_email = 0

    def search(self, zielgruppe: dict, limit: int):
        self.uebersprungen_ohne_email = 0
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
                self.uebersprungen_ohne_email += 1
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
        """Wiederholt nur bei 429 (Rate-Limit) und 5xx (voruebergehende
        Server-Fehler) - beides Faelle, bei denen ein zweiter Versuch
        sinnvoll sein kann. Andere 4xx-Fehler (z.B. 401 falscher Api-Key,
        422 kaputte Anfrage) sind dauerhaft und werden sofort ohne
        Wiederholung als RuntimeError gemeldet. Nach dem letzten
        fehlgeschlagenen Versuch wird nicht mehr gewartet."""
        letzte_antwort = None
        for versuch in range(3):
            antwort = self.session.post(
                url, json=body, timeout=30,
                headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"})
            if antwort.status_code < 400:
                return antwort
            if antwort.status_code != 429 and antwort.status_code < 500:
                raise RuntimeError(f"Apollo antwortet mit {antwort.status_code} auf {url}")
            letzte_antwort = antwort
            if versuch < 2:
                time.sleep(self.wartezeit * (versuch + 1))
        raise RuntimeError(f"Apollo antwortet dauerhaft mit {letzte_antwort.status_code}")

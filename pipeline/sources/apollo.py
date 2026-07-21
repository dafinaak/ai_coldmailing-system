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
#
# Organization Enrichment (docs.apollo.io/reference/organization-enrichment,
# Kern-Umbau Stufe 2, geprueft 2026-07-21):
# Zweck: pro Firma aus Stufe 1 (Google Maps) die Apollo-Organisation finden
# (fuer organization_id + Mitarbeiterzahl, Grundlage der info@-Regel).
# Passende Felder laut Doku: "domain", "linkedin_url", "name", "website" -
# mindestens eines noetig, hier "domain" bzw. als Fallback "name" (siehe
# _organisation_finden). Antwort-Huelle {"organization": {...}} (oder ohne
# Treffer vermutlich {"organization": null} bei Status 200 - die Doku nennt
# nur "0 Credits bei keinem Treffer", nicht die genaue Fehler-/Leer-Form).
# TODO(verifizieren am echten Konto): (c) HTTP-Methode und exakte URL fuer
# dieses Endpoint ("GET .../organizations/enrich?domain=...", analog zu
# Apollos uebrigen Enrichment-Endpoints) liessen sich aus der Doku-Seite
# nicht statisch auslesen (das "Try it"-Beispiel wird dort per JavaScript
# nachgeladen). GET + Query-Parameter ist die in Apollo-Tutorials und
# -Community-Beispielen durchgaengig verwendete Form und darum hier
# umgesetzt - der Live-Smoke-Test mit dem echten Konto ist die eigentliche
# Verifikation. (d) Ob "organization": null oder ein anderer Status (404/
# 200 mit leerem Objekt) bei fehlendem Treffer zurueckkommt, ebenfalls am
# echten Konto pruefen; _organisation_finden behandelt aktuell nur ein
# fehlendes/"falsy" organization-Feld als "kein Treffer".
# Kostenhinweis: 1 Apollo-Credit pro TATSAECHLICH gefundener Organisation
# (0 bei keinem Treffer) - bei "Domain zuerst, dann Name" also im
# schlechtesten Fall 2 Credits pro Firma ohne Domain-Treffer.
BASE_URL = "https://api.apollo.io/api/v1"
SUCH_URL = f"{BASE_URL}/mixed_people/api_search"
ANREICHERUNGS_URL = f"{BASE_URL}/people/bulk_match?reveal_personal_emails=true"
ANREICHERUNGS_BATCH_GROESSE = 10
ORGANISATION_URL = f"{BASE_URL}/organizations/enrich"

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

    def unternehmen_anreichern(self, firma: dict, kontakt_rollen: list) -> dict:
        """Stufe 2 der Lead-Beschaffung (Kern-Umbau): zu EINER Firma aus
        Stufe 1 (dict mit mindestens "domain"/"name") Kontakte in den
        gewuenschten Rollen suchen - NICHT die alte kriterien-basierte
        Massensuche in search() oben (die bleibt fuer Rueckwaertskompatibilitaet
        stehen). Liefert immer dieselbe Form zurueck, auch ohne Treffer:
        {"kontakte": [...], "mitarbeiterzahl": int|None, "organization_id": str|None,
        "name": str|None} - "kontakte" ist eine Liste aus {"first_name",
        "last_name", "email", "title"}-Dicts (nur Personen MIT E-Mail nach der
        bulk_match-Anreicherung). "mitarbeiterzahl" traegt Apollos
        "estimated_num_employees" der gefundenen Organisation - Grundlage der
        info@-Regel in pipeline.sourcing, die hier bewusst NICHT entschieden
        wird (dieses Modul kennt keine info@-Regel, nur Apollo-Rohdaten).
        "name" ist Apollos KANONISCHER Organisationsname (Lead-Qualitaets-Fix:
        Google-Maps-Titel sind teils verunreinigt, z.B. "IT-Dienstleister
        Hannover - Ihre Helden" statt "Ihre Helden" - Apollos Organisationsname
        ist die sauberere Quelle und wird von pipeline.sourcing bevorzugt
        genutzt, wenn vorhanden)."""
        organisation = self._organisation_finden(firma)
        if not organisation:
            return {"kontakte": [], "mitarbeiterzahl": None, "organization_id": None, "name": None}
        organization_id = organisation.get("id")
        kontakte = (self._kontakte_fuer_organisation(organization_id, kontakt_rollen)
                    if organization_id else [])
        return {"kontakte": kontakte,
                "mitarbeiterzahl": organisation.get("estimated_num_employees"),
                "organization_id": organization_id,
                "name": organisation.get("name")}

    def _organisation_finden(self, firma: dict):
        """Sucht die Apollo-Organisation zur Firma: zuerst ueber die Domain
        (praeziser), bei keinem Treffer als Fallback ueber den Firmennamen -
        wie im Auftrag vorgegeben ("by domain, fall back to name")."""
        for feld, wert in (("domain", firma.get("domain")), ("name", firma.get("name"))):
            if not wert:
                continue
            antwort = self._get_mit_wiederholung(ORGANISATION_URL, {feld: wert})
            organisation = antwort.json().get("organization")
            if organisation:
                return organisation
        return None

    def _kontakte_fuer_organisation(self, organization_id: str, kontakt_rollen: list) -> list:
        body = {"organization_ids": [organization_id], "person_titles": kontakt_rollen,
                "per_page": 100, "page": 1}
        antwort = self._post_mit_wiederholung(SUCH_URL, body)
        treffer = antwort.json().get("people", [])
        angereicherte_treffer = self._anreichern(treffer)
        kontakte = []
        for p in angereicherte_treffer:
            if not p.get("email"):
                continue
            kontakte.append({
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name") or p.get("last_name_obfuscated", ""),
                "email": p["email"], "title": p.get("title", "")})
        return kontakte

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
        return self._mit_wiederholung(url, lambda: self.session.post(
            url, json=body, timeout=30,
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"}))

    def _get_mit_wiederholung(self, url, params):
        return self._mit_wiederholung(url, lambda: self.session.get(
            url, params=params, timeout=30, headers={"X-Api-Key": self.api_key}))

    def _mit_wiederholung(self, url, aufruf):
        """Wiederholt nur bei 429 (Rate-Limit) und 5xx (voruebergehende
        Server-Fehler) - beides Faelle, bei denen ein zweiter Versuch
        sinnvoll sein kann. Andere 4xx-Fehler (z.B. 401 falscher Api-Key,
        422 kaputte Anfrage) sind dauerhaft und werden sofort ohne
        Wiederholung als RuntimeError gemeldet. Nach dem letzten
        fehlgeschlagenen Versuch wird nicht mehr gewartet. Gemeinsam fuer
        POST (_post_mit_wiederholung) und GET (_get_mit_wiederholung)
        genutzt, `aufruf` fuehrt den eigentlichen HTTP-Request aus."""
        letzte_antwort = None
        for versuch in range(3):
            antwort = aufruf()
            if antwort.status_code < 400:
                return antwort
            if antwort.status_code != 429 and antwort.status_code < 500:
                raise RuntimeError(f"Apollo antwortet mit {antwort.status_code} auf {url}")
            letzte_antwort = antwort
            if versuch < 2:
                time.sleep(self.wartezeit * (versuch + 1))
        raise RuntimeError(f"Apollo antwortet dauerhaft mit {letzte_antwort.status_code}")

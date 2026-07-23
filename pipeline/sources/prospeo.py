"""Prospeo-Anbindung fuer den Anbieter-Vergleich (Weg A: Apify -> Prospeo).

Rolle: Prospeo soll BEIDE Schritte alleine koennen, fuer die im bisherigen
Aufbau zwei Anbieter noetig sind (Hunter findet, Dropcontact prueft):
1. entscheider_finden(): aus der Firmen-Domain die Personen der Firma finden
   (Name + Jobtitel + person_id - die Mail bleibt hier noch verdeckt).
2. email_anreichern(): fuer eine gefundene person_id die persoenliche Mail
   aufdecken - bewusst mit only_verified_email=true, damit NUR eine von
   Prospeo selbst als zustellbar gepruefte Adresse zurueckkommt
   (Zuverlaessigkeit zuerst, siehe AGENTS.md).

Live-Doku (prospeo.io/api-docs/*, geprueft 2026-07-23):

Auth: Header "X-KEY: <KEY>" + "Content-Type: application/json"; Host
api.prospeo.io; alle Endpunkte sind POST (nur Account-Info ist GET).

Suche - POST https://api.prospeo.io/search-person
    Body: {"page": 1, "filters": {"company": {"websites": {"include":
          ["<domain>"]}}}}
    Der websites-Vorfilter ist ein reiner API-Filter (nicht im Dashboard),
    max. 500 Domains je Anfrage. Antwort: {"error": false, "free": bool,
    "results": [{"person": {...}, "company": {...}}], "pagination": {...}}
    mit bis zu 25 Personen je Seite. Die E-Mail steht im Personenobjekt,
    ist aber NICHT aufgedeckt (email.revealed == false).
    Credits: 1 Credit je Suchanfrage MIT mindestens einem Treffer; dieselbe
    Ergebnis-Seite ist 30 Tage lang frei ("free": true).

Anreicherung - POST https://api.prospeo.io/enrich-person
    Body: {"only_verified_email": true, "data": {"person_id": "<id>"}}
    Antwort: {"error": false, "free_enrichment": bool, "person": {...,
    "email": {"status": "VERIFIED"|"UNAVAILABLE", "revealed": true,
    "email": "...", "verification_method": "SMTP"|"BOUNCEBAN"}}}
    Credits: 1 Credit je GEFUNDENER Mail; kein Treffer kostet nichts;
    dieselbe Person ist 90 Tage lang frei (free_enrichment == true).

Kein Treffer heisst: HTTP 400 mit {"error": true, "error_code": ...} -
die Suche meldet "NO_RESULTS" (im Messlauf vom 23.07.2026 live belegt),
die Anreicherung laut Doku "NO_MATCH". Beides ist KEIN technischer Fehler
(und kostet keinen Credit), sondern schlicht "Prospeo kennt hier niemanden"
bzw. "keine geprueft zustellbare Mail vorhanden". Alle anderen Fehlercodes
(falscher Key, ungueltige Filter, ...) scheitern laut, wie bei
Hunter/Dropcontact.
"""
import time
import requests

BASE_URL = "https://api.prospeo.io"
SUCH_URL = f"{BASE_URL}/search-person"
ANREICHERN_URL = f"{BASE_URL}/enrich-person"
# Prospeos "kein Treffer"-Codes - bewusst KEIN RuntimeError (siehe Docstring):
# NO_MATCH kommt von der Anreicherung, NO_RESULTS von der Suche.
KEIN_TREFFER_CODES = ("NO_MATCH", "NO_RESULTS")


def _aktuelle_seniority(p: dict) -> str:
    """Liest die Seniority des aktuellen Jobs aus job_history (dort steht sie,
    nicht am Personenobjekt selbst). Bevorzugt den Eintrag, dessen job_key dem
    current_job_key entspricht; sonst den ersten als aktuell markierten Job."""
    jobs = p.get("job_history") or []
    aktuelle = [j for j in jobs if j.get("current")]
    for job in aktuelle:
        if job.get("job_key") and job.get("job_key") == p.get("current_job_key"):
            return job.get("seniority") or ""
    return (aktuelle[0].get("seniority") or "") if aktuelle else ""


class ProspeoSource:
    def __init__(self, api_key, session=None, wartezeit=2.0, max_versuche=3):
        self.api_key = api_key
        self.session = session or requests.Session()
        self.wartezeit = wartezeit
        self.max_versuche = max_versuche

    @property
    def _headers(self):
        return {"Content-Type": "application/json", "X-KEY": self.api_key}

    def _post(self, url: str, body: dict) -> dict | None:
        """POST mit Wiederholen bei 429/5xx (wie HunterSource). Gibt das
        JSON zurueck - oder None beim dokumentierten NO_MATCH (kein Treffer).
        Jeder andere Fehler (4xx, error==true mit anderem Code, dauerhaft
        5xx) scheitert laut."""
        for versuch in range(1, self.max_versuche + 1):
            antwort = self.session.post(url, json=body, headers=self._headers, timeout=30)
            daten = antwort.json() if antwort.status_code != 204 else {}
            daten = daten or {}
            if antwort.status_code < 400:
                if daten.get("error"):
                    if daten.get("error_code") in KEIN_TREFFER_CODES:
                        return None
                    raise RuntimeError(
                        f"Prospeo meldet Fehler auf {url}: "
                        f"{daten.get('error_code') or 'unbekannt'}")
                return daten
            if antwort.status_code == 400 and daten.get("error_code") in KEIN_TREFFER_CODES:
                return None
            if antwort.status_code == 429 or antwort.status_code >= 500:
                if versuch < self.max_versuche:
                    time.sleep(self.wartezeit)
                    continue
            raise RuntimeError(
                f"Prospeo antwortet mit {antwort.status_code} auf {url}: "
                f"{getattr(antwort, 'text', '')}")
        raise RuntimeError(
            f"Prospeo antwortet nach {self.max_versuche} Versuchen weiter mit "
            f"{antwort.status_code} auf {url}")

    def entscheider_finden(self, domain: str) -> list:
        """Findet die Personen einer Firma ueber den Domain-Vorfilter der
        Personensuche. Jeder Eintrag: {"person_id", "first_name", "last_name",
        "title", "seniority"} - die Mail ist hier noch verdeckt und wird erst
        in email_anreichern() aufgedeckt. Leere Liste, wenn Prospeo die Firma
        oder ihre Personen nicht kennt (NO_MATCH bzw. leere results)."""
        if not domain:
            return []
        daten = self._post(SUCH_URL, {
            "page": 1,
            "filters": {"company": {"websites": {"include": [domain]}}}})
        if daten is None:
            return []
        personen = []
        for treffer in daten.get("results") or []:
            p = treffer.get("person") or {}
            # Ohne Namen ist die Person fuer eine persoenliche Ansprache
            # wertlos (gleiche Regel wie bei Hunter).
            if not (p.get("first_name") and p.get("last_name")):
                continue
            personen.append({
                "person_id": p.get("person_id", ""),
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "title": p.get("current_job_title", "") or "",
                "seniority": _aktuelle_seniority(p),
            })
        return personen

    def email_anreichern(self, person_id: str) -> dict | None:
        """Deckt fuer eine person_id aus der Suche die persoenliche Mail auf -
        nur, wenn Prospeo sie selbst als zustellbar geprueft hat
        (only_verified_email). Gibt {"email", "status", "verification_method",
        "schon_bezahlt"} zurueck oder None, wenn es keine geprueft
        zustellbare Adresse gibt (NO_MATCH - kostet keinen Credit).
        "schon_bezahlt" (free_enrichment) heisst: dieselbe Person wurde in den
        letzten 90 Tagen schon angereichert, dieser Aufruf war gratis."""
        if not person_id:
            return None
        daten = self._post(ANREICHERN_URL, {
            "only_verified_email": True, "data": {"person_id": person_id}})
        if daten is None:
            return None
        email = ((daten.get("person") or {}).get("email")) or {}
        if not email.get("email"):
            return None
        return {"email": email["email"],
                "status": email.get("status", ""),
                "verification_method": email.get("verification_method", ""),
                "schon_bezahlt": bool(daten.get("free_enrichment"))}

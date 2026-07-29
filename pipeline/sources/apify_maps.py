"""Stufe 1 der Lead-Beschaffung: Firmen ueber Google Maps finden (Apify).

Live-Doku (apify.com/compass/crawler-google-places, apify.com/compass/crawler-
google-places/input-schema und .../api, geprueft 2026-07-21):

Actor: "Google Maps Scraper" von Compass (Maintainer: Apify selbst,
518K Nutzer, 4.7 Sterne) - Store-Slug "compass/crawler-google-places".
Im API-Pfad ersetzt Apify den Slash durch eine Tilde: "compass~crawler-
google-places" (Apify-Konvention fuer ALLE Actor-API-Aufrufe, nicht
actor-spezifisch).

Genutzter Endpunkt: "Run Actor synchronously and get dataset items"
    POST https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items?token=<TOKEN>
Bewusst diese (dokumentierte) synchrone Variante statt des im Auftrag
skizzierten Drei-Schritt-Ablaufs (POST .../runs -> Status pollen -> GET
.../dataset/items): beide Wege sind auf derselben API-Referenz-Seite
gelistet, die synchrone Variante blockiert einfach bis der Actor fertig
ist und liefert die Dataset-Eintraege direkt als JSON-Liste zurueck -
bei den hier genutzten kleinen `limit`s (einzelner Suchbegriff, Team-
Alltag statt Massen-Laeufe) unproblematisch. Bei sehr grossen Laeufen
muesste man wegen des drohenden HTTP-Timeouts auf die asynchrone
Variante wechseln.

Eingabe-Felder (Input-Schema-Seite):
- "searchStringsArray": Liste der Suchbegriffe (hier genau einer - die
  Kombination aus Dienstleistung+Region steckt schon in Kunde.maps_suche,
  z.B. "IT-Dienstleister Hannover"; ein separates "locationQuery"-Feld
  ist deshalb nicht noetig).
- "maxCrawledPlacesPerSearch": Obergrenze der Ergebnisse (hier: `limit`).
- "language": Sprache der Ergebnis-Details ("de" fuer deutsche Kunden).

Ausgabe (ein Dataset-Eintrag pro Firma; bestaetigtes Beispiel-JSON aus der
Doku): u.a. "title" (Firmenname), "website", "address", "categoryName"
(Hauptkategorie). Eine zusaetzliche "categories"-Liste (mehrere Kategorien)
wird, falls vorhanden, mit uebernommen - in der Doku nicht mit eigenem
Beispiel belegt, deshalb per .get() defensiv gelesen statt vorausgesetzt;
fehlt sie, wird auf eine Einzelliste aus "categoryName" zurueckgefallen.

TODO(verifizieren am echten Konto): Token-/Compute-Kosten laut Pricing-Seite
"from $1.50 / 1.000 gescrapte Orte" (Free-Tier-Konditionen koennen
abweichen). Beim Live-Smoke-Test (kleines `limit`) den tatsaechlichen
Verbrauch in der Apify-Konsole gegenpruefen, damit klar ist, wie weit
das begrenzte Free-Konto-Guthaben von Leonard reicht.
"""
import requests
from urllib.parse import urlparse

ACTOR_ID = "compass~crawler-google-places"
LAUF_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"


def _domain_aus_website(website: str) -> str:
    if not website:
        return ""
    netloc = urlparse(website).netloc.lower()
    if not netloc:  # z.B. schemenlose URL ohne "https://"
        netloc = website.split("/")[0].lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


class ApifyMapsSource:
    def __init__(self, api_key, session=None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def _pruefen(self, antwort, was):
        if antwort.status_code >= 400:
            raise RuntimeError(
                f"Apify antwortet mit {antwort.status_code} bei {was}: "
                f"{getattr(antwort, 'text', '')}")
        return antwort.json()

    def _gebietslauf_abrufen(self, body, schlaf, poll_sekunden=30) -> list:
        """Asynchroner Ablauf fuer lange Gebiets-Raster (30-60 min): Lauf
        starten -> Status abfragen bis fertig -> Dataset abholen. Der
        Sync-Endpunkt (run-sync-get-dataset-items) reisst bei solchen
        Laufzeiten an der Verbindungs-Zeitgrenze (bekannte
        Einschraenkung, siehe Kopf-Doku)."""
        start = self._pruefen(self.session.post(
            f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={self.api_key}",
            json=body, timeout=60), "Lauf-Start")["data"]
        lauf_id, dataset_id = start["id"], start["defaultDatasetId"]
        while True:
            stand = self._pruefen(self.session.get(
                f"https://api.apify.com/v2/actor-runs/{lauf_id}?token={self.api_key}",
                timeout=60), "Status")["data"]
            status = stand.get("status")
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify-Gebietslauf endete mit {status}")
            schlaf(poll_sekunden)
        eintraege = self._pruefen(self.session.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={self.api_key}&clean=true",
            timeout=300), "Dataset")
        if not isinstance(eintraege, list):
            raise RuntimeError(
                f"Apify liefert unerwartetes Format (keine Liste): {eintraege!r}")
        return eintraege

    def search_gebiet(self, suchbegriffe, gebiet_geojson, limit_pro_suche,
                      schlaf=None) -> list:
        """Gebiets-Raster fuer das Leadquellen-Fundament (Bauplan
        29.07.2026): Der Actor rastert ein GeoJSON-Gebiet
        ("customGeolocation", siehe Actor-Doku) selbst ab - Olivers
        Vorgabe "nach Postleitregionen" loesen wir als Umriss ueber den
        Regionen plus PLZ-Feinfilter in der Fusion. Liefert das
        Fusions-Format (inkl. plz/telefon/quelle); "email" kennt Maps
        nicht, das Feld bleibt leer."""
        import time
        body = {"searchStringsArray": list(suchbegriffe),
                "customGeolocation": gebiet_geojson,
                "maxCrawledPlacesPerSearch": limit_pro_suche,
                "language": "de"}
        firmen = []
        for e in self._gebietslauf_abrufen(body, schlaf or time.sleep):
            website = e.get("website") or ""
            kategorien = e.get("categories")
            if not kategorien:
                kategorien = [e["categoryName"]] if e.get("categoryName") else []
            firmen.append({
                "name": e.get("title", ""),
                "website": website,
                "domain": _domain_aus_website(website),
                "address": e.get("address", ""),
                "plz": e.get("postalCode") or "",
                "telefon": e.get("phone") or "",
                "vorhandene_email": "",
                "categories": kategorien,
                "quelle": "maps",
            })
        return firmen

    def search(self, suchbegriff: str, limit: int) -> list:
        body = {"searchStringsArray": [suchbegriff],
                "maxCrawledPlacesPerSearch": limit, "language": "de"}
        url = f"{LAUF_URL}?token={self.api_key}"
        antwort = self.session.post(url, json=body, timeout=120)
        if antwort.status_code >= 400:
            raise RuntimeError(
                f"Apify antwortet mit {antwort.status_code} auf {LAUF_URL}: {antwort.text}")
        eintraege = antwort.json()
        if not isinstance(eintraege, list):
            raise RuntimeError(
                f"Apify liefert unerwartetes Format (keine Liste) auf {LAUF_URL}: {eintraege!r}")

        firmen = []
        for eintrag in eintraege[:limit]:
            website = eintrag.get("website") or ""
            kategorien = eintrag.get("categories")
            if not kategorien:
                kategorien = [eintrag["categoryName"]] if eintrag.get("categoryName") else []
            firmen.append({
                "name": eintrag.get("title", ""),
                "website": website,
                "domain": _domain_aus_website(website),
                "address": eintrag.get("address", ""),
                "categories": kategorien,
            })
        return firmen

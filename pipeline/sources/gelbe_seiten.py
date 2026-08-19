"""Fundament-Quelle Gelbe Seiten (Bauplan Leadquellen-Fundament, Schritt 1).

Actor: "Gelbe Seiten Scraper - German Business Directory (PPR)" von
plowdata (Store-Slug "plowdata/gelbe-seiten-ppr") - gewaehlt am
29.07.2026 als der meistgenutzte (86 Nutzer) und frischeste (Update
27.07.2026) der drei Store-Kandidaten; Bezahlmodell PAY_PER_EVENT
(je Ergebnis, Cent-Bereich - Verbrauch nach Laeufen in der
Apify-Konsole gegenpruefen).

Eingabe (Input-Schema + Mini-Lauf am 29.07.2026 verifiziert):
- "query": Suchbegriff (z. B. "IT-Dienstleister")
- "location": Ort/Region (z. B. "Hannover")
- "maxPages": Anzahl Ergebnis-Seiten (ca. 10 Eintraege je Seite)

Ausgabe je Eintrag (Mini-Lauf beobachtet): "name", "address" (mit PLZ),
"phone", "website", "email", "industries" (Liste). Nicht jeder Eintrag
hat website/email - solche Firmen bleiben drin (Fusion/Bericht weisen
sie aus), denn Telefon/Adresse sind fuer Olivers Anruf/Brief-Liste
weiter nuetzlich.

Wie alle Einzelquellen ist dieser Dritt-Scraper KEIN Fundament fuer
sich allein (Projektregel): Das Fundament ist die Fusion mehrerer
Quellen; bricht dieser Actor, laufen die anderen weiter.
"""
import re
import requests

from pipeline.firmen_filter import ort_aus_adresse
from pipeline.sources.apify_maps import _domain_aus_website

ACTOR_ID = "plowdata~gelbe-seiten-ppr"
LAUF_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"

_PLZ = re.compile(r"\b(\d{5})\b")


def _plz_aus_adresse(adresse: str) -> str:
    treffer = _PLZ.search(adresse or "")
    return treffer.group(1) if treffer else ""


class GelbeSeitenQuelle:
    def __init__(self, api_key, session=None):
        self.api_key = api_key
        self.session = session or requests.Session()

    def search(self, suchbegriff: str, ort: str, max_seiten: int = 1) -> list:
        body = {"query": suchbegriff, "location": ort, "maxPages": max_seiten}
        url = f"{LAUF_URL}?token={self.api_key}"
        antwort = self.session.post(url, json=body, timeout=300)
        if antwort.status_code >= 400:
            raise RuntimeError(
                f"Apify antwortet mit {antwort.status_code} auf {LAUF_URL}: "
                f"{antwort.text}")
        eintraege = antwort.json()
        if not isinstance(eintraege, list):
            raise RuntimeError(
                f"Apify liefert unerwartetes Format (keine Liste) auf "
                f"{LAUF_URL}: {eintraege!r}")

        firmen = []
        for e in eintraege:
            website = e.get("website") or ""
            adresse = e.get("address") or ""
            plz = _plz_aus_adresse(adresse)
            firmen.append({
                "name": e.get("name", ""),
                "website": website,
                "domain": _domain_aus_website(website),
                "address": adresse,
                "plz": plz,
                "ort": ort_aus_adresse(adresse, plz),
                "telefon": e.get("phone") or "",
                "vorhandene_email": e.get("email") or "",
                "categories": list(e.get("industries") or []),
                "quelle": "gelbe_seiten",
            })
        return firmen

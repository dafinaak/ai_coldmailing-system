"""Fundament-Quelle OpenStreetMap via Overpass-API (Bauplan
Leadquellen-Fundament, Schritt 2).

Overpass ist die freie Abfrage-Schnittstelle von OpenStreetMap
(https://overpass-api.de/api/interpreter, POST mit Formular-Feld
"data"). Kostenlos, aber gedrosselt: Die Betreiber bitten um sparsame,
nacheinander gestellte Abfragen - deshalb EINE Sammel-Abfrage pro
Lauf (alle PLZ-Regionen in einem Rutsch) statt vieler kleiner, und ein
grosszuegiges Server-Timeout in der Abfrage selbst.

Abfrage-Logik (Live-Befund 29.07.2026): Die naheliegende Suche ueber
PLZ-Gebiete (area[boundary=postal_code][postal_code~...]) laeuft beim
Server in die Zeitueberschreitung (504) - das Muster-Matching ueber
alle PLZ-Flaechen Deutschlands ist die teuerste Abfrageform. Deshalb
stattdessen: EIN Koordinaten-Rechteck ueber der Zielregion (schnell,
weil Overpass raeumlich indexiert), und die PLZ-Feinfilterung passiert
danach bei uns: Eintraege mit fremder PLZ fliegen raus, Eintraege OHNE
PLZ-Angabe bleiben drin (das Rechteck buergt grob fuers Gebiet; der
Fusionsbericht weist sie aus). Gesucht wird nach IT-Merkmalen
(Standard: office=it - die OSM-Kategorie fuer IT-Dienstleister;
bewusst NICHT shop=computer, das ist ueberwiegend der von Oliver
ausgeschlossene Computerhandel).

Nicht jeder OSM-Eintrag hat Webseite/Mail - solche Firmen bleiben
drin (Telefon/Adresse nutzt Olivers Anruf/Brief-Liste); Eintraege ganz
ohne Namen werden verworfen.
"""
import time

import requests

from pipeline.sources.apify_maps import _domain_aus_website

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Oeffentlicher Ausweich-Server derselben Datenbasis (kumi.systems
# betreibt einen der grossen freien Overpass-Spiegel). Der Gratis-Dienst
# ist lastabhaengig: 504 "ueberlastet" kam am 29.07.2026 live fuer eine
# Abfrage, die eine Stunde vorher sauber lief.
OVERPASS_MIRRORS = (OVERPASS_URL,
                    "https://overpass.kumi.systems/api/interpreter")
STANDARD_MERKMALE = (("office", "it"),)
# Overpass-Etikette verlangt eine identifizierende Kennung; ohne sie
# lehnt der Server ab (406, live beobachtet 29.07.2026 - gleiche Falle
# wie Cloudflare vor der Instantly-API).
KENNUNG = {"User-Agent": "AI-Coldmailing-Leadsuche/1.0 (internes Tool)"}


# Rechteck (Sued, West, Nord, Ost) ueber den Postleitregionen 30+31
# (Hannover, Hildesheim, Hameln, Peine und Umland) - bewusst grosszuegig;
# die PLZ-Feinfilterung uebernimmt der Code danach.
BBOX_PLR_30_31 = (51.7, 8.9, 52.7, 10.6)


def _abfrage_bauen(bbox, merkmale) -> str:
    s, w, n, o = bbox
    bloecke = []
    for schluessel, wert in merkmale:
        for typ in ("node", "way"):
            bloecke.append(f'  {typ}["{schluessel}"="{wert}"]({s},{w},{n},{o});')
    return ('[out:json][timeout:180];\n'
            "(\n" + "\n".join(bloecke) + "\n);\n"
            "out center tags;\n")


def _tag(tags: dict, *namen) -> str:
    for name in namen:
        wert = tags.get(name)
        if wert:
            return wert
    return ""


def _adresse(tags: dict) -> str:
    strasse = " ".join(t for t in (tags.get("addr:street"),
                                   tags.get("addr:housenumber")) if t)
    ort = " ".join(t for t in (tags.get("addr:postcode"),
                               tags.get("addr:city")) if t)
    return ", ".join(t for t in (strasse, ort) if t)


class OverpassQuelle:
    def __init__(self, session=None, urls=OVERPASS_MIRRORS, runden=2,
                 wartezeit=30, schlaf=time.sleep):
        self.session = session or requests.Session()
        self.urls = tuple(urls)
        self.runden = runden
        self.wartezeit = wartezeit
        self.schlaf = schlaf

    def _abrufen(self, abfrage):
        """Versucht Haupt- und Ausweich-Server im Wechsel, mit Wartezeit
        zwischen den Versuchen. Behandelt Fehler-Antworten (5xx/429) UND
        abgerissene Verbindungen (Timeout, live 29.07.2026) gleich: naechster
        Versuch. Erst wenn alle scheitern, wird laut abgebrochen."""
        letzte, letzter_abriss = None, None
        for nr, url in enumerate(self.urls * self.runden):
            if nr:
                self.schlaf(self.wartezeit)
            try:
                antwort = self.session.post(url, data={"data": abfrage},
                                            headers=KENNUNG, timeout=240)
            except requests.exceptions.RequestException as fehler:
                letzter_abriss = fehler
                continue
            if antwort.status_code < 400:
                return antwort
            letzte = antwort
        if letzte is not None:
            raise RuntimeError(
                f"Overpass antwortet mit {letzte.status_code}: "
                f"{(getattr(letzte, 'text', '') or '')[:200]}")
        raise RuntimeError(f"Overpass nicht erreichbar: {letzter_abriss}")

    def search(self, plz_praefixe, bbox, merkmale=STANDARD_MERKMALE) -> list:
        abfrage = _abfrage_bauen(tuple(bbox), tuple(merkmale))
        antwort = self._abrufen(abfrage)
        elemente = (antwort.json() or {}).get("elements") or []

        praefixe = tuple(plz_praefixe)
        firmen = []
        for e in elemente:
            tags = e.get("tags") or {}
            name = tags.get("name")
            if not name:
                continue
            plz = tags.get("addr:postcode", "")
            # fremde PLZ raus; ohne PLZ bleibt drin (Rechteck buergt grob)
            if plz and not plz.startswith(praefixe):
                continue
            website = _tag(tags, "website", "contact:website")
            firmen.append({
                "name": name,
                "website": website,
                "domain": _domain_aus_website(website),
                "address": _adresse(tags),
                "plz": plz,
                "telefon": _tag(tags, "phone", "contact:phone"),
                "vorhandene_email": _tag(tags, "email", "contact:email"),
                "categories": [f"{k}={tags[k]}" for k, _ in
                               (("office", None),) if tags.get(k)],
                "quelle": "overpass",
            })
        return firmen

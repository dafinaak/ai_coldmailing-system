"""Impressum-Stufe der Kaskade (Bauplan 2026-07-27, von Oliver freigegeben).

Aufgabe: Wenn die Daten-Anbieter keinen Entscheider kennen, steht der
Geschaeftsfuehrer deutscher Firmen per Gesetz im Impressum der eigenen
Webseite. Diese Stufe findet die Impressum-Seite, laesst die vorhandene KI
NUR die Namen (und eine ggf. abweichende Mail-Domain) herauslesen - die
E-Mail selbst baut und prueft danach IMMER der bezahlte Anbieter
(Dropcontact). Projektregel: Der selbst gebaute Teil liefert Namen als
Bonus, nie ungepruefte Adressen (siehe AGENTS.md).

Die Pflicht-Sonderfaelle aus den Messlaeufen vom 23./27.07.2026:
- JavaScript-Seiten liefern per HTTP nur eine Huelle -> Rueckfall auf
  Browser-Rendering (headless Chrome), Fall it-blickwinkel.de.
- Manche Firmen mailen ueber eine ANDERE Domain als die Webseite
  (Fall it-hannover.de -> hannover-edv.de); steht sie im Impressum, wird
  sie an Dropcontact weitergegeben.
- "Geschaeftsfuehrer" in Kundenstimmen/Bewertungen meint einen KUNDEN,
  nicht den Chef der Firma (Fall ihre-helden.de) - Anweisung an die KI.
- Die Lead-Liste enthielt einen Firmennamen im Geschaeftsfuehrer-Feld
  (Fall "VR Immobilien & Service") - Personen-Validierung wirft alles
  raus, was nach Firma statt Mensch aussieht.
- Abgekuerzte Vornamen ("G. Hellberg") sind fuer Dropcontact wertlos und
  werden verworfen.
"""
import json
import re
import subprocess
import html as html_modul
from urllib.parse import urljoin, urlparse

STANDARD_PFADE = ("/impressum", "/impressum/", "/impressum.html",
                  "/de/impressum", "/imprint", "/legal")
# Kuerzere Texte sind praktisch immer JavaScript-Huellen oder Fehlerseiten.
MIN_TEXTLAENGE = 300
# Woerter, die einen "Namen" als Firma statt Person entlarven (Kleinschreibung).
FIRMEN_WOERTER = {"gmbh", "mbh", "ag", "kg", "ug", "gbr", "ohg", "e.k.", "ek",
                  "co", "co.", "&", "und", "holding", "verwaltungs",
                  "verwaltungsgesellschaft", "systemhaus", "service",
                  "services", "solutions", "immobilien", "group", "gruppe",
                  "consulting", "partner", "team"}
CHROME_PFAD = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

SYSTEM_AUFTRAG = """Du liest deutsche Impressums-Seiten und gibst NUR JSON zurueck.

Regeln:
- Nimm ausschliesslich Personen, die im Impressums-/Anbieterkennzeichnungs-Teil
  als Inhaber, Geschaeftsfuehrer, vertretungsberechtigt oder "vertreten durch"
  genannt sind.
- Ignoriere Kundenstimmen, Bewertungen, Referenzen und Zitate komplett - ein
  "Geschaeftsfuehrer" in einer Kundenbewertung ist ein Kunde, NICHT der Chef
  dieser Firma.
- Firmennamen (GmbH, GbR, Verwaltungsgesellschaft usw.) sind keine Personen.
  Bei einer GmbH & Co. KG nimm den Geschaeftsfuehrer der Verwaltungs-GmbH.
- Vor- und Nachname muessen ausgeschrieben sein; abgekuerzte Vornamen nicht
  uebernehmen.
- "mail_domain": Nur wenn im Impressum eine E-Mail-Adresse mit einer ANDEREN
  Domain als der Webseiten-Domain steht, gib diese Domain an - sonst null.

Antwortformat (nur dieses JSON, kein weiterer Text):
{"personen": [{"vorname": "...", "nachname": "..."}], "mail_domain": "..." }"""


def _html_zu_text(roh: str) -> str:
    roh = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', roh, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', html_modul.unescape(re.sub(r'<[^>]+>', ' ', roh))).strip()


def _chrome_rendern(url: str) -> str | None:
    """Rueckfall fuer JavaScript-Seiten: laesst den Browser die Seite fertig
    aufbauen und liefert den Text. None, wenn kein Chrome installiert ist
    oder das Rendern scheitert - dann bleibt die Firma eben ohne Impressum."""
    import os
    if not os.path.exists(CHROME_PFAD):
        return None
    try:
        lauf = subprocess.run(
            [CHROME_PFAD, "--headless", "--disable-gpu", "--dump-dom",
             "--virtual-time-budget=8000", url],
            capture_output=True, text=True, timeout=45)
        return _html_zu_text(lauf.stdout) if lauf.returncode == 0 else None
    except Exception:
        return None


def _ist_personenname(vorname: str, nachname: str) -> bool:
    """Verwirft Firmennamen und abgekuerzte Vornamen (siehe Docstring)."""
    if not vorname or not nachname:
        return False
    if len(vorname.replace(".", "")) < 2 or vorname.endswith("."):
        return False
    woerter = {w.strip(".,").lower() for w in f"{vorname} {nachname}".split()}
    if woerter & FIRMEN_WOERTER:
        return False
    return len(f"{vorname} {nachname}".split()) <= 4


class ImpressumQuelle:
    def __init__(self, ki, session=None, renderer=None):
        import requests
        self.ki = ki
        self.session = session or requests.Session()
        # renderer ist injizierbar (Tests); Standard: headless Chrome.
        self.renderer = renderer if renderer is not None else _chrome_rendern

    def _seite_holen(self, url: str) -> str:
        try:
            antwort = self.session.get(
                url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
                timeout=20)
        except Exception:
            return ""
        if antwort.status_code >= 400:
            return ""
        return getattr(antwort, "text", "") or ""

    def _kandidaten(self, website: str):
        basis = website.rstrip("/")
        domain = urlparse(website).netloc or basis.split("//")[-1]
        for pfad in STANDARD_PFADE:
            yield f"https://{domain}{pfad}" if domain else basis + pfad
        # Rueckfall: Impressum-Link auf der Startseite suchen.
        start_html = self._seite_holen(website)
        for treffer in re.finditer(r'href="([^"]*impressum[^"]*)"', start_html, re.I):
            yield urljoin(website + "/", treffer.group(1))

    def impressum_text(self, website: str) -> str | None:
        """Findet und liest die Impressum-Seite: erst die ueblichen Adressen,
        dann die Link-Suche auf der Startseite, zuletzt Browser-Rendering
        fuer JavaScript-Seiten. None, wenn nichts Brauchbares gefunden wird."""
        if not website:
            return None
        zu_kurze = []
        gesehen = set()
        for url in self._kandidaten(website):
            if url in gesehen:
                continue
            gesehen.add(url)
            text = _html_zu_text(self._seite_holen(url))
            if not text:
                continue
            if len(text) >= MIN_TEXTLAENGE and "impressum" in text.lower():
                return text
            zu_kurze.append(url)
        # JavaScript-Huellen: dieselben Adressen noch einmal im Browser rendern.
        if self.renderer:
            for url in zu_kurze[:3]:
                gerendert = self.renderer(url)
                if gerendert and len(gerendert) >= MIN_TEXTLAENGE \
                        and "impressum" in gerendert.lower():
                    return gerendert
        return None

    def entscheider_lesen(self, text: str, firmenname: str, domain: str = "",
                          hinweis_name: str = "") -> dict:
        """Laesst die KI Geschaeftsfuehrer-Namen und eine ggf. abweichende
        Mail-Domain aus dem Impressums-Text lesen. Gibt {"personen": [...],
        "mail_domain": str|None} zurueck - nach der Personen-Validierung
        (Firmennamen und abgekuerzte Vornamen fliegen raus)."""
        hinweis = (f"\n\nHinweis aus unserer Vorab-Liste (pruefe, ob diese Person "
                   f"tatsaechlich im Impressum steht): {hinweis_name}") if hinweis_name else ""
        prompt = (f"Firma: {firmenname}\nWebseiten-Domain: {domain}{hinweis}\n\n"
                  f"Impressums-Text:\n{text[:6000]}")
        antwort = self.ki.frage(SYSTEM_AUFTRAG, prompt)
        treffer = re.search(r"\{.*\}", antwort, re.S)
        if not treffer:
            return {"personen": [], "mail_domain": None}
        try:
            daten = json.loads(treffer.group(0))
        except json.JSONDecodeError:
            return {"personen": [], "mail_domain": None}
        personen = []
        for p in daten.get("personen") or []:
            vor = (p.get("vorname") or "").strip()
            nach = (p.get("nachname") or "").strip()
            if _ist_personenname(vor, nach):
                personen.append({"vorname": vor, "nachname": nach})
        mail_domain = (daten.get("mail_domain") or "").strip().lower() or None
        return {"personen": personen, "mail_domain": mail_domain}

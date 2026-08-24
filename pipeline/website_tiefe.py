"""Webseiten-Lesen in die Tiefe, mit Zwischenspeicher.

Warum es das braucht: `pipeline/website.py` holt NUR die Startseite. Der
Audit vom 21.08.2026 hat gezeigt, dass genau daran die
Automatisierungs-Pruefung scheitert - die meisten Belege stehen auf
/leistungen/, /loesungen/ oder /digitalisierung/, also auf
Unterseiten, die die Startseite nie zu sehen bekommt. Von 3 bestaetigten
Fehlurteilen kamen alle 3 aus Unterseiten.

Dieser Baustein holt die Startseite, liest daraus die Links, waehlt die
inhaltlich passenden Unterseiten aus und liest sie mit. Ergebnis ist ein
Text MIT Quellenangabe je Abschnitt, damit der Klassifizierer sagen
kann, WO er etwas gefunden hat.

Zwischenspeicher: je Domain eine JSON-Datei mit Zeitstempel. Innerhalb
der TTL wird nicht neu geholt. Die TTL ist einstellbar; korrekt geht vor
sparsam, deshalb ist der Standard mit 14 Tagen kurz genug, dass ein
Relaunch der Webseite nicht monatelang unbemerkt bleibt.
"""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

KOPFZEILEN = {"User-Agent": "Mozilla/5.0 (kompatibel; Recherche-Bot)"}
ZEIT_LIMIT = 15
CACHE_ORDNER = "daten/webseiten-cache"
STANDARD_TTL_TAGE = 14

# Pfadstuecke, hinter denen erfahrungsgemaess das Leistungsangebot steht.
# Reihenfolge = Priorität: was eine Firma anbietet, steht eher unter
# "leistungen" als unter "ueber-uns".
INTERESSANTE_PFADE = (
    "leistung", "service", "dienstleistung", "loesung", "solution",
    "produkt", "product", "angebot", "beratung", "consulting",
    "kompetenz", "capabilit", "was-wir", "portfolio",
    "digitalisierung", "automatis", "automation",
    "ueber-uns", "ueber_uns", "about", "unternehmen",
)

# Diese nie mitlesen - kosten Zeit und tragen nichts zur Frage bei.
UNINTERESSANT = (
    "impressum", "datenschutz", "privacy", "agb", "kontakt", "contact",
    "karriere", "career", "job", "blog", "news", "presse", "login",
    "warenkorb", "cart", "shop", "cookie", "sitemap", "faq",
)

_TAG = re.compile(r"(?s)<(script|style|noscript|svg)[^>]*>.*?</\1>", re.I)
_HTML = re.compile(r"(?s)<[^>]+>")
_LEER = re.compile(r"\s+")
_LINK = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\']', re.I)


def sichtbarer_text(html: str) -> str:
    ohne_tags = _HTML.sub(" ", _TAG.sub(" ", html or ""))
    import html as html_modul
    return _LEER.sub(" ", html_modul.unescape(ohne_tags)).strip()


def _cache_pfad(daten_dir, domain) -> Path:
    schluessel = hashlib.sha1(domain.encode("utf-8")).hexdigest()[:16]
    return Path(daten_dir) / CACHE_ORDNER / f"{schluessel}.json"


def _domain_von(url) -> str:
    netz = urlparse(str(url or "")).netloc or str(url or "")
    return netz.replace("www.", "").split("/")[0].strip().lower()


def links_auswaehlen(html: str, basis_url: str, max_seiten: int = 4) -> list:
    """Die inhaltlich passendsten Unterseiten - hoechstens max_seiten.

    Nur gleiche Domain, keine Dateien, keine Impressum-/Rechts-Seiten.
    Sortiert nach der Reihenfolge in INTERESSANTE_PFADE, damit
    /leistungen/ vor /ueber-uns/ gelesen wird."""
    basis_domain = _domain_von(basis_url)
    gefunden = {}
    for treffer in _LINK.finditer(html or ""):
        roh = treffer.group(1).strip()
        if not roh or roh.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        voll = urljoin(basis_url, roh)
        if _domain_von(voll) != basis_domain:
            continue
        pfad = urlparse(voll).path.lower()
        if not pfad or pfad == "/":
            continue
        if pfad.rsplit(".", 1)[-1] in (
                "pdf", "jpg", "jpeg", "png", "gif", "zip", "doc", "docx",
                "xls", "xlsx", "mp4", "svg", "webp"):
            continue
        if any(schlecht in pfad for schlecht in UNINTERESSANT):
            continue
        for rang, stueck in enumerate(INTERESSANTE_PFADE):
            if stueck in pfad:
                voll_ohne_anker = voll.split("#")[0]
                if voll_ohne_anker not in gefunden:
                    gefunden[voll_ohne_anker] = rang
                break
    sortiert = sorted(gefunden.items(), key=lambda p: (p[1], len(p[0])))
    return [url for url, _ in sortiert[:max_seiten]]


def _seite_holen(url: str, session=None) -> str:
    hole = (session or requests).get
    try:
        antwort = hole(url, timeout=ZEIT_LIMIT, headers=KOPFZEILEN)
        if getattr(antwort, "status_code", 0) >= 400:
            return ""
        return antwort.text or ""
    except Exception:      # noqa: BLE001 - eine tote Seite ist ein
        # normales Ergebnis, kein Programmfehler
        return ""


def seiten_lesen(website: str, daten_dir=".", *, max_seiten: int = 4,
                 ttl_tage: float = STANDARD_TTL_TAGE, session=None,
                 jetzt=time.time, cache: bool = True) -> dict:
    """{"text", "seiten": [{"url","zeichen"}], "status", "geholt_am"}.

    status: "ok"            - Text von mindestens einer Seite
            "leer"          - erreichbar, aber praktisch ohne Text
            "nicht_erreichbar" - Startseite nicht ladbar
            "keine_webseite"   - gar keine Adresse hinterlegt

    Der Aufrufer soll bei allem ausser "ok" NICHT auf "keine
    Automatisierung" schliessen (Auftrag Punkt 24)."""
    website = (website or "").strip()
    if not website:
        return {"text": "", "seiten": [], "status": "keine_webseite",
                "geholt_am": None}
    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    domain = _domain_von(website)
    pfad = _cache_pfad(daten_dir, domain)
    if cache and pfad.exists():
        try:
            gespeichert = json.loads(pfad.read_text(encoding="utf-8"))
            alter_tage = (jetzt() - gespeichert.get("geholt_am", 0)) / 86400
            if alter_tage < ttl_tage:
                gespeichert["aus_cache"] = True
                return gespeichert
        except (ValueError, OSError):
            pass

    start_html = _seite_holen(website, session)
    if not start_html.strip():
        ergebnis = {"text": "", "seiten": [], "status": "nicht_erreichbar",
                    "geholt_am": jetzt()}
        _cache_schreiben(pfad, ergebnis, cache)
        return ergebnis

    teile, seiten = [], []
    start_text = sichtbarer_text(start_html)
    if start_text:
        teile.append(f"[Quelle: {website}]\n{start_text[:6000]}")
        seiten.append({"url": website, "zeichen": len(start_text)})

    for unterseite in links_auswaehlen(start_html, website, max_seiten):
        text = sichtbarer_text(_seite_holen(unterseite, session))
        if len(text) < 200:
            continue
        teile.append(f"[Quelle: {unterseite}]\n{text[:6000]}")
        seiten.append({"url": unterseite, "zeichen": len(text)})

    gesamt = "\n\n".join(teile)
    ergebnis = {
        "text": gesamt,
        "seiten": seiten,
        "status": "ok" if len(gesamt.strip()) >= 300 else "leer",
        "geholt_am": jetzt(),
    }
    _cache_schreiben(pfad, ergebnis, cache)
    return ergebnis


def _cache_schreiben(pfad: Path, ergebnis: dict, cache: bool):
    if not cache:
        return
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps(ergebnis, ensure_ascii=False),
                        encoding="utf-8")
    except OSError:
        pass

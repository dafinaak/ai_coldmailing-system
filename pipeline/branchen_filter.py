"""Branchen-Pruefung nach Olivers Profil (Auftrag 30.07.2026).

Anlass: Die erste Paket-Liste enthielt Branchenfremde (Augenarzt,
Zeitarbeit, Baufinanzierung, Gebaeudereinigung ...), Rechenzentren,
Software-Produktfirmen, Niederlassungen und moegliche Automations-
Wettbewerber. Der alte Filter (Schluesselwoerter in Name/Kategorie,
pipeline/listen_fusion.py) ist dafuer zu grob: Er kann nicht sehen,
WAS eine Firma tatsaechlich anbietet.

Zwei Stufen:

1. Harte Regeln (kostenlos, ohne Netz): Niederlassungen/Filialen
   (Olivers Vorgabe "nur die Zentrale") und klar branchenfremde
   Kategorien. Diese Faelle brauchen kein KI-Urteil.
2. KI-Urteil je Firma: Name, Kategorien und der sichtbare Text der
   Firmen-Webseite gehen an das Modell, das nach Olivers Profil
   entscheidet - inklusive der Frage, ob die Firma SELBST Automationen
   anbietet (Wettbewerber).

Zuverlaessigkeit zuerst: Was die KI nicht eindeutig als passend
bezeichnet, gilt als NICHT passend (typ "unsicher") und wird im Bericht
aufgefuehrt - lieber eine Firma zu wenig anschreiben als eine falsche.
"""
import json
import re

AUSSCHLUSS_GRUENDE = ("niederlassung", "branchenfremd", "unsicher")

# Olivers Vorgabe: bei Filialisten/Niederlassungen nur die Zentrale.
_NIEDERLASSUNG = re.compile(
    r"\b(niederlassung|filiale|zweigstelle|zweigniederlassung|standort)\b",
    re.IGNORECASE)

# Kategorien/Namensteile, die eine Firma ohne KI-Rueckfrage disqualifizieren.
# Alle aus der echten Fehlerliste vom 30.07.2026 abgeleitet.
_FREMD = (
    "zeitarbeit", "personaldienst", "personalmanagement", "immobilien",
    "lebensmittel", "biomarkt", "supermarkt", "spielwaren", "spielzeug",
    "möbel", "verlag", "buchhandlung", "reinigung", "gebäudeservice",
    "baufinanzier", "finanzberat", "versicherung", "steuerberat",
    "buchhaltungs", "coworking", "arzt", "ärzt", "klinik", "augenlaser",
    "zahn", "apotheke", "restaurant", "café", "hotel", "friseur",
    "fitness", "schule", "kindergarten", "bäckerei", "metzger",
    "autohaus", "kfz", "reifen", "grosshändler", "großhändler",
    "einzelhandel", "baumarkt", "garten", "veranstaltungsservice",
    "eventmanagement", "reisebüro", "logistik", "spedition",
)


def _text_von(firma: dict) -> str:
    return " ".join([firma.get("name", "")] +
                    [str(k) for k in firma.get("categories") or []]).lower()


def harter_ausschluss(firma: dict):
    """Gibt den Ausschlussgrund zurueck oder None, wenn die Firma die
    harten Regeln uebersteht (dann entscheidet die KI)."""
    if _NIEDERLASSUNG.search(firma.get("name", "")):
        return "niederlassung"
    text = _text_von(firma)
    if any(wort in text for wort in _FREMD):
        return "branchenfremd"
    return None


SYSTEM_PROMPT = """Du prüfst, ob eine Firma zum Zielprofil einer
B2B-Kampagne passt. Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{"passt": true|false, "typ": "<kurze Einordnung>", "grund": "<ein Satz>"}

ZIELPROFIL (passt = true), nur wenn die Firma als Dienstleister die IT
ihrer Geschäftskunden betreut:
- IT-Dienstleister, IT-Systemhaus, IT-Service, IT-Support
- typische Merkmale: Betreuung/Wartung von IT-Infrastruktur, Netzwerke,
  Server, Arbeitsplätze, Managed Services, IT-Betreuung für Firmen

AUSSCHLÜSSE (passt = false), auch wenn "IT" im Namen steht:
- reiner Computerhandel: Verkauf von Hardware oder Software als Ware
- Software-Hersteller/Produktfirmen (eigenes Produkt statt Betreuung)
- Rechenzentren, Colocation
- reine Elektro-/Leitungs-Installationsunternehmen
- Hoster, Webhosting, Internet-Provider, Internet-Dienstleister
- Firmen, die SELBST Automationen anbieten (Prozessautomatisierung,
  Workflow-Automation, RPA, Systemintegration als Automations-Angebot,
  KI-Automatisierung) - das sind Wettbewerber
- Webdesign-/Marketing-/Werbeagenturen ohne IT-Betreuung
- alles Branchenfremde (Handel, Handwerk, Beratung, Medizin, Bildung ...)

Im Zweifel passt = false. Sei streng: Nur klar erkennbare
IT-Dienstleister mit Betreuungsgeschäft bekommen true."""


ZWEITE_CHANCE_SYSTEM = """Du prüfst einen GRENZFALL nach. Diese Firma wurde
zuvor als Software-Hersteller, Software-Entwickler oder als Berater ohne
klaren Betreuungsfokus eingeordnet und deshalb ausgeschlossen. Jetzt
zählt nur EINE Frage:

Betreut diese Firma die IT ANDERER Unternehmen als Dienstleistung?
Also: Managed Services, IT-Support, Wartung, Systembetreuung,
Netzwerk-/Server-Betrieb, Hotline, Systemhaus-Leistungen - egal ob
zusätzlich zu eigenen Softwareprodukten.

passt = true, wenn solche Betreuungsleistungen erkennbar angeboten werden.
passt = false, wenn die Firma ausschließlich eigene Produkte verkauft
oder entwickelt, reiner Händler ist, oder wenn sie SELBST Automationen /
Prozessautomatisierung / RPA / KI-Automatisierung anbietet
(Wettbewerber), oder wenn nichts Belastbares erkennbar ist.

Antworte AUSSCHLIESSLICH mit:
{"passt": true|false, "typ": "<kurze Einordnung>", "grund": "<ein Satz>"}"""


def firma_bewerten(firma: dict, webtext: str, ki, system=None) -> dict:
    """Bewertet EINE Firma. Gibt {"passt", "typ", "grund", "quelle"}.
    Mit system=ZWEITE_CHANCE_SYSTEM laeuft die Grenzfall-Nachpruefung."""
    grund = harter_ausschluss(firma)
    if grund:
        return {"passt": False, "typ": grund,
                "grund": f"Harte Regel: {grund}", "quelle": "regel"}

    kategorien = ", ".join(str(k) for k in firma.get("categories") or []) or "keine"
    webseite_teil = (f"Text der Webseite (Auszug):\n{webtext[:3500]}"
                     if webtext.strip() else
                     "Kein Text von der Webseite verfügbar (keine Webseite "
                     "erreichbar) - urteile nur nach Name und Kategorien.")
    prompt = (f"Firma: {firma.get('name', '')}\n"
              f"Kategorien (aus Verzeichnissen): {kategorien}\n"
              f"Webseite: {firma.get('website') or 'keine'}\n\n"
              f"{webseite_teil}")

    antwort = ki.frage(system or SYSTEM_PROMPT, prompt)
    treffer = re.search(r"\{.*\}", antwort or "", re.S)
    if not treffer:
        return {"passt": False, "typ": "unsicher",
                "grund": "KI-Antwort nicht lesbar", "quelle": "ki"}
    try:
        daten = json.loads(treffer.group(0))
    except ValueError:
        return {"passt": False, "typ": "unsicher",
                "grund": "KI-Antwort nicht lesbar", "quelle": "ki"}
    return {"passt": bool(daten.get("passt")),
            "typ": str(daten.get("typ") or "unbekannt"),
            "grund": str(daten.get("grund") or ""),
            "quelle": "ki"}

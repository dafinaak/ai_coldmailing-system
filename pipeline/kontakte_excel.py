"""Aus einem fertigen Lauf eine Excel-Tabelle zum Herunterladen bauen.

Der Lauf schreibt drei Dateien, jede mit einem eigenen Blickwinkel:
leads.json (wer erreichbar ist), firmen.json (wie es jeder Firma
ergangen ist) und personalisierung.json (welcher Text fertig ist). Zum
Weitergeben braucht ein Mensch daraus EINE Tabelle.

Drei Blätter, weil drei verschiedene Leute etwas anderes damit tun:

  Kontakte       - wer angeschrieben wird, mit Anrede und Text-Stand
  Anruf & Brief  - Firmen ohne brauchbare Adresse, mit Telefonnummer
                   und dem Grund; die verschwinden sonst lautlos
  Zur Kontrolle  - alles, wo ein Blick eines Menschen hilft

Nichts wird hier neu berechnet oder nachgeschlagen - die Tabelle zeigt
genau das, was im Laufordner steht.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl

from pipeline.anrede_spalte import baue_anrede
from pipeline.firmen_filter import ort_mit_plz

AUSGANG_TEXT = {
    "info_ungueltig": "info@-Adresse geprüft und nicht zustellbar",
    "kein_entscheider": "keine Person auf der Webseite gefunden",
    "keine_webseite": "keine Webseite hinterlegt",
    "fehler": "Fehler bei der Suche (später erneut versuchen)",
}
# "Ort" statt "PLZ": in der Spalte steht seit 18.08.2026 "30161 Hannover"
# statt nur der Zahl - wer die Liste zum Anrufen benutzt, will den Ort
# lesen koennen (das Feld "ort" ist bei den gesammelten Firmen leer, der
# Name kommt aus der Adresszeile, siehe pipeline.firmen_filter).
KOPF_KONTAKTE = ["Nr", "Firma", "Person", "Anrede", "E-Mail", "Telefon",
                 "Ort", "Webseite", "Betreff", "Text", "Hinweis"]


def _domain(wert: object) -> str:
    ohne = re.sub(r"^https?://", "", str(wert or "").strip().casefold())
    return re.sub(r"^www\.", "", ohne).split("/")[0]


def _laden(lauf_dir: Path, name: str, standard):
    pfad = Path(lauf_dir) / name
    if not pfad.exists():
        return standard
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return standard


def _firma_zu_lead(lead: dict, firmen: list) -> dict:
    """Find the company a contact belongs to.

    Matched over the domain first: the company name in a lead is the
    cleaned-up version and does not always equal the one in firmen.json.
    """
    ziel = _domain(lead.get("website")) or _domain(lead.get("email", "").split("@")[-1])
    for firma in firmen:
        if ziel and ziel in (_domain(firma.get("website")), _domain(firma.get("domain"))):
            return firma
    name = str(lead.get("company", "")).casefold()
    for firma in firmen:
        if name and str(firma.get("name", "")).casefold().startswith(name[:18]):
            return firma
    return {}


def _texte_nach_mail(personalisierung: dict) -> dict:
    texte = {}
    for gruppe in ("fertig", "nacharbeit"):
        for eintrag in personalisierung.get(gruppe) or []:
            adresse = str(eintrag.get("email", "")).casefold()
            if adresse:
                texte[adresse] = {**eintrag, "gruppe": gruppe}
    return texte


def mappe_bauen(lauf_dir) -> openpyxl.Workbook:
    lauf_dir = Path(lauf_dir)
    leads = (_laden(lauf_dir, "leads.json", {}) or {}).get("leads") or []
    firmen = _laden(lauf_dir, "firmen.json", []) or []
    texte = _texte_nach_mail(_laden(lauf_dir, "personalisierung.json", {}) or {})
    # Aussortierte Adressen (Doppelt, Sperrliste, schon angeschrieben) stehen
    # weiter in leads.json und damit auch in dieser Liste. Ohne ihren Grund
    # standen sie hier mit "noch kein Text" - das liest sich, als käme der
    # Text noch, dabei geht diese Adresse bewusst gar nicht raus
    # (gefunden am 17.08.2026 an einer echten Mappe).
    verworfen = {str(v.get("email", "")).casefold(): str(v.get("grund", ""))
                 for v in (_laden(lauf_dir, "dedupe.json", {}) or {}).get("verworfen") or []}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kontakte"
    ws.append(KOPF_KONTAKTE)

    kontrolle = []
    nummer = 0
    for lead in leads:
        firma = _firma_zu_lead(lead, firmen)
        person = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip()
        mail = str(lead.get("email", ""))
        hinweise = []

        if person:
            anrede, grund = baue_anrede(person)
            if grund != "maennlich":
                hinweise.append(grund)
        else:
            # Sammeladresse: die Anrede ohne Namen, wie am 11.08.2026 entschieden.
            anrede = "zusammen"
            hinweise.append("Sammeladresse info@ - Anrede ohne Namen")

        hinweise += [str(n) for n in lead.get("notizen") or []]
        mail_domain = _domain(mail.split("@")[-1])
        firmen_domain = _domain(firma.get("domain") or firma.get("website"))
        if mail_domain and firmen_domain and mail_domain != firmen_domain:
            hinweise.append(f"Mail-Domain {mail_domain} weicht von "
                            f"{firmen_domain} ab")

        text = texte.get(mail.casefold(), {})
        stand = {"fertig": "fertig", "nacharbeit": "Nacharbeit nötig"}.get(
            text.get("gruppe"), "noch kein Text")
        if text.get("gruppe") == "nacharbeit" and text.get("grund"):
            hinweise.append(f"Text: {text['grund']}")
        # Aussortiert gewinnt: diese Adresse bekommt keinen Text, weil sie
        # nicht rausgehen soll - nicht, weil noch etwas fehlt.
        grund_verworfen = verworfen.get(mail.casefold())
        if grund_verworfen:
            stand = "geht nicht raus"
            hinweise.append(grund_verworfen)

        nummer += 1
        ws.append([nummer, firma.get("name") or lead.get("company"), person,
                   anrede, mail, firma.get("telefon"), ort_mit_plz(firma),
                   firma.get("website") or lead.get("website"),
                   text.get("betreff"), stand, " | ".join(hinweise)])
        if hinweise:
            kontrolle.append([firma.get("name") or lead.get("company"),
                              person or mail, " | ".join(hinweise)])

    _blatt_anruf_brief(wb, firmen)

    blatt = wb.create_sheet("Zur Kontrolle")
    blatt.append(["Firma", "Person / Adresse", "Warum auf dieser Liste"])
    for reihe in kontrolle:
        blatt.append(reihe)
    return wb


def _blatt_anruf_brief(wb: openpyxl.Workbook, firmen: list) -> None:
    """Companies without a usable address - never silently dropped."""
    blatt = wb.create_sheet("Anruf & Brief")
    blatt.append(["Firma", "Warum keine E-Mail", "Telefon", "Ort", "Webseite"])
    for firma in firmen:
        ausgang = firma.get("ausgang")
        if ausgang in (None, "mit_entscheider", "info_fallback"):
            continue
        # Der genaue Grund des Laufs gewinnt ueber den Sammelbegriff: bei
        # "fehler" stand hier sonst "später erneut versuchen", auch wenn in
        # Wahrheit das Pruef-Kontingent leer war - dann versucht es die
        # Person am Telefon vergeblich noch einmal (siehe
        # pipeline.sourcing.fehler_satz).
        grund = firma.get("fehler_grund") or AUSGANG_TEXT.get(ausgang, ausgang)
        blatt.append([firma.get("name"), grund,
                      firma.get("telefon"), ort_mit_plz(firma),
                      firma.get("website")])


def schreiben(lauf_dir, ziel) -> Path:
    ziel = Path(ziel)
    mappe_bauen(lauf_dir).save(ziel)
    return ziel

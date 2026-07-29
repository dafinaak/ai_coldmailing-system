"""Fusion der Fundament-Quellen zu EINER Firmenliste (Bauplan
Leadquellen-Fundament, Schritt 3; Olivers Vorgaben vom 29.07.2026).

Aufgaben:
- Duplikate erkennen: zuerst ueber die Domain (staerkstes Merkmal),
  fuer Firmen ohne Webseite ueber Namenskern + PLZ (grob, wie die
  bestehende Dubletten-Logik im Grosslauf - lieber einmal zu viel
  fusioniert und im Bericht sichtbar als doppelt angeschrieben).
- Reichste Daten behalten: Leere Felder werden aus spaeteren Quellen
  aufgefuellt; jede Firma merkt sich ihre Quellen ("quellen").
- Olivers Ausschluesse: Computerhandel, Rechenzentren, Elektro-/
  Leitungs-Installation, Hoster, Internet-Dienstleister, Automations-
  Dienstleistung - erkannt ueber Schluesselwoerter in Name und
  Kategorien. Aussortiertes wird im Bericht GELISTET (mit Grund),
  nie still verworfen.
- Fremde PLZ (ausserhalb der Ziel-Praefixe) fliegen raus und werden
  gezaehlt; Firmen OHNE PLZ bleiben drin.

Ausgabe im firmen.json-Format der Pipeline (kompatibel zu
listen_import/grosslauf), plus Bericht als Zahlenwerk.
"""
from pipeline.grosslauf import _namenskern

# Olivers Ausschluss-Liste als Schluesselwoerter (kleingeschrieben,
# Teilstring-Abgleich gegen Name + Kategorien). Bewusst konservativ
# gehalten; der Bericht listet jeden Ausschluss samt Grund, damit ein
# Mensch Fehlgriffe zurueckholen kann.
AUSSCHLUESSE = {
    "Computerhandel": ("computerhandel", "computer-handel", "pc-handel",
                       "hardwarehandel", "softwarehandel", "computershop"),
    "Rechenzentrum": ("rechenzentr",),
    "Elektro-Installation": ("elektro",),
    "Hosting": ("hosting", "hoster"),
    "Internet-Dienstleister": ("internetagentur", "internet-dienstleist",
                               "internetdienstleist", "provider"),
    "Automations-Dienstleistung": ("automation", "automatisierung"),
}

FELDER_AUFFUELLEN = ("website", "domain", "address", "plz", "telefon",
                     "vorhandene_email", "gf_name_liste")


def _ausschluss_grund(f: dict):
    text = " ".join([f.get("name", "")] +
                    [str(k) for k in f.get("categories") or []]).lower()
    for grund, woerter in AUSSCHLUESSE.items():
        if any(w in text for w in woerter):
            return grund
    return None


def _schluessel(f: dict) -> str:
    if f.get("domain"):
        return f"domain:{f['domain']}"
    return f"name:{_namenskern(f.get('name', ''))}|{f.get('plz', '')}"


def _verschmelzen(ziel: dict, neu: dict) -> None:
    for feld in FELDER_AUFFUELLEN:
        if not ziel.get(feld) and neu.get(feld):
            ziel[feld] = neu[feld]
    for kat in neu.get("categories") or []:
        if kat not in ziel["categories"]:
            ziel["categories"].append(kat)
    quelle = neu.get("quelle", "?")
    if quelle not in ziel["quellen"]:
        ziel["quellen"].append(quelle)


def fusionieren(listen, plz_praefixe) -> tuple:
    """Nimmt mehrere Quellen-Listen (je im Quellen-Bausteine-Format) und
    gibt (firmen, bericht) zurueck."""
    praefixe = tuple(plz_praefixe)
    je_quelle, fusioniert = {}, {}
    fremde_plz = 0
    ausgeschlossen = []

    for liste in listen:
        for f in liste:
            quelle = f.get("quelle", "?")
            je_quelle[quelle] = je_quelle.get(quelle, 0) + 1
            plz = f.get("plz") or ""
            if plz and not plz.startswith(praefixe):
                fremde_plz += 1
                continue
            grund = _ausschluss_grund(f)
            if grund:
                ausgeschlossen.append({"name": f.get("name", ""),
                                       "domain": f.get("domain", ""),
                                       "grund": grund, "quelle": quelle})
                continue
            schluessel = _schluessel(f)
            if schluessel in fusioniert:
                _verschmelzen(fusioniert[schluessel], f)
            else:
                fusioniert[schluessel] = {
                    "name": f.get("name", ""),
                    "website": f.get("website", ""),
                    "domain": f.get("domain", ""),
                    "address": f.get("address", ""),
                    "categories": list(f.get("categories") or []),
                    "plz": f.get("plz", ""),
                    "telefon": f.get("telefon", ""),
                    "vorhandene_email": f.get("vorhandene_email", ""),
                    "gf_name_liste": f.get("gf_name_liste", ""),
                    "ausserhalb_region": False,
                    "quellen": [f.get("quelle", "?")],
                }

    firmen = list(fusioniert.values())
    for f in firmen:
        f["quelle"] = "+".join(f["quellen"])
    gesamt_roh = sum(je_quelle.values())
    bericht = {
        "je_quelle": je_quelle,
        "einzigartig": len(firmen),
        "ueberschneidungen": gesamt_roh - fremde_plz - len(ausgeschlossen)
                             - len(firmen),
        "fremde_plz": fremde_plz,
        "ausgeschlossen": ausgeschlossen,
        "ohne_webseite": sum(1 for f in firmen if not f["domain"]),
    }
    return firmen, bericht

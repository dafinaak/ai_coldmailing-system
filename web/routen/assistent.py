"""The six-step campaign wizard ("E-Mails schreiben lassen").

Rebuilt after the Wholix screens, with our own engine underneath. The
two steps that differ are the ones our data cannot serve the same way:

  Step 3  Wholix filters a bought contact database by job title,
          seniority and installed software. We filter the companies we
          collected ourselves, and can only offer what those sources
          actually deliver: where a company sits, what it was listed
          under, and the blocklist.
  Step 4  Wholix answers instantly because it looks up ready-made
          contacts. We answer instantly too - but only about COMPANIES,
          which are already on disk. The e-mail addresses are built
          afterwards, in the background, while step 5 is being filled
          in. That is the whole reason the waiting is not visible.

Every step writes its values to a draft file the moment it is
submitted, so a closed tab costs nothing.

The wizard stops at the approval table. It never talks to Instantly and
never sends: the existing approval route does that, with its own
guards, after a human has read every text.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pipeline import assistent_entwurf as entwuerfe
from pipeline.config import lade_globale_sperrlisten_eintraege
from pipeline.firmen_filter import dienste_vorschlagen, filtern, ort_mit_plz
from pipeline.service_categories import families
from web import auth
from web.nav import nav_kontext

router = APIRouter()

SCHRITTE = [
    ("Campaign Setup", "Grunddaten der Kampagne"),
    ("USP & ICP prüfen", "Angebot und Zielkunde bestätigen"),
    ("Firmen-Filter", "Umkreis und Leistung wählen"),
    ("Suchergebnis", "Gefundene Firmen prüfen"),
    ("Versand-Einstellungen", "Postfach, Menge, Zeiten"),
    ("E-Mails erzeugen", "Texte schreiben lassen"),
]
SPRACHEN = [("de", "Deutsch"), ("en", "English (US)")]
RADIUS_STUFEN = [10, 25, 50, 100, 250]
WOCHENTAGE = [("mo", "Mo"), ("di", "Di"), ("mi", "Mi"), ("do", "Do"),
              ("fr", "Fr"), ("sa", "Sa"), ("so", "So")]


def _daten_dir(request: Request) -> Path:
    return Path(request.app.state.daten_dir)


def _firmen_bestand(daten_dir: Path) -> list:
    """Alle bisher gesammelten Firmen, ueber alle Sammlungen hinweg.

    Liest bewusst von der Platte statt zu sammeln: das ist die Haelfte der
    Arbeit, die schon bezahlt und erledigt ist.

    Jede Sammlung liegt in einem eigenen Ordner unter laeufe/leadquellen/.
    Die aeltere wird dabei NIE ueberschrieben - eine kaputte Fusion darf
    nicht den ganzen Bestand beschaedigen (aktuell 1.481 Firmen, rund
    sieben Dollar Sammelkosten). Nach aussen ist es trotzdem EIN Bestand,
    weil hier zusammengefuehrt wird.

    Kennt eine spaetere Sammlung dieselbe Firma, ergaenzt sie die
    fehlenden Felder - Webseite, Telefon, PLZ. Vorher gewann schlicht der
    erste Fund und alles Spaetere flog weg: eine neue Sammlung konnte den
    Bestand also nur vergroessern, nie auffrischen (17.08.2026, auf
    Nachfrage: "vetem me i shtu edhe te rejat aty me u bo update").
    Gefuellte Felder bleiben unangetastet - ergaenzen, nicht ueberschreiben.
    """
    bestand: list = []
    nach_schluessel: dict = {}
    wurzel = daten_dir / "laeufe" / "leadquellen"
    for pfad in sorted(wurzel.glob("*/firmen.json")) if wurzel.exists() else []:
        try:
            firmen = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for firma in firmen if isinstance(firmen, list) else []:
            schluessel = (firma.get("domain") or firma.get("name") or "").lower()
            if not schluessel:
                continue
            bekannt = nach_schluessel.get(schluessel)
            if bekannt is None:
                kopie = dict(firma)
                nach_schluessel[schluessel] = kopie
                bestand.append(kopie)
            else:
                _firma_ergaenzen(bekannt, firma)
    return bestand


# Felder, die eine spaetere Sammlung nachtragen darf, wenn sie fehlen.
# Bewusst ohne "name": der Name ist der Schluessel zur Wiedererkennung und
# soll sich nicht unter der Hand aendern.
_ERGAENZBAR = ("website", "domain", "plz", "telefon", "address",
               "vorhandene_email", "gf_name_liste", "ort")


def _firma_ergaenzen(bekannt: dict, neu: dict) -> None:
    """Leere Felder auffuellen, Kategorien und Quellen sammeln."""
    for feld in _ERGAENZBAR:
        if not bekannt.get(feld) and neu.get(feld):
            bekannt[feld] = neu[feld]
    kategorien = bekannt.setdefault("categories", [])
    for kat in neu.get("categories") or []:
        if kat not in kategorien:
            kategorien.append(kat)
    # Alte Saetze tragen "quelle" (eine), neuere "quellen" (mehrere). Beim
    # ersten Zusammenfuehren die eigene Quelle mit uebernehmen, sonst geht
    # sie verloren, sobald eine zweite Sammlung dieselbe Firma kennt.
    if not bekannt.get("quellen") and bekannt.get("quelle"):
        bekannt["quellen"] = [bekannt["quelle"]]
    quellen = bekannt.setdefault("quellen", [])
    neue_quellen = list(neu.get("quellen") or [])
    if neu.get("quelle"):
        neue_quellen.append(neu["quelle"])
    for quelle in neue_quellen:
        if quelle and quelle not in quellen:
            quellen.append(quelle)


def _entwurf_oder_start(request: Request, kennung: str):
    entwurf = entwuerfe.laden(_daten_dir(request), kennung)
    if entwurf is None:
        return None, RedirectResponse("/assistent", status_code=303)
    return entwurf, None


def _seite(request: Request, entwurf: dict, schritt: int, extra: dict | None = None,
           fehler: str | None = None, status_code: int = 200):
    inhalt = {
        "nutzer": auth.aktueller_nutzer(request),
        "nav": nav_kontext(request),
        "entwurf": entwurf,
        "d": entwurf["daten"],
        "schritt": schritt,
        "schritte": SCHRITTE,
        "hoechster_schritt": entwurf.get("hoechster_schritt", 1),
        "fehler": fehler,
    }
    inhalt.update(extra or {})
    return request.app.state.templates.TemplateResponse(
        request, f"assistent_{schritt}.html", inhalt, status_code=status_code)


def _weiter(kennung: str, schritt: int) -> RedirectResponse:
    return RedirectResponse(f"/assistent/{kennung}/{schritt}", status_code=303)


@router.get("/assistent")
def starten(request: Request):
    """Always begins a fresh draft - the campaign list offers old ones."""
    entwurf = entwuerfe.anlegen(_daten_dir(request))
    return _weiter(entwurf["kennung"], 1)


@router.post("/assistent/{kennung}/abbrechen")
def abbrechen(request: Request, kennung: str):
    entwuerfe.loeschen(_daten_dir(request), kennung)
    return RedirectResponse("/kampagnen", status_code=303)


# ---------------------------------------------------------------- Schritt 1

@router.get("/assistent/{kennung}/1")
def schritt_1(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung
    return _seite(request, entwurf, 1,
                  {"sprachen": SPRACHEN, "postfaecher": _postfaecher(request)})


@router.post("/assistent/{kennung}/1")
def schritt_1_speichern(
        request: Request, kennung: str,
        name: str = Form(""), sprache: str = Form("de"),
        anzahl_leads: str = Form("50"), beschreibung: str = Form(""),
        verkaeufer_url: str = Form(""), absender_email: str = Form(""),
        referenz_1: str = Form(""), referenz_2: str = Form(""),
        anweisungen: str = Form("")):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    fehlend = [beschriftung for wert, beschriftung in (
        (name, "Kampagnen-Name"), (verkaeufer_url, "Verkäufer-Webseite"),
        (absender_email, "Absender-Adresse")) if not wert.strip()]
    if fehlend:
        entwurf["daten"].update(_werte_1(locals()))
        return _seite(request, entwurf, 1,
                      {"sprachen": SPRACHEN, "postfaecher": _postfaecher(request)},
                      fehler=f"Bitte ausfüllen: {', '.join(fehlend)}.",
                      status_code=400)

    entwuerfe.schritt_speichern(_daten_dir(request), kennung, 1, _werte_1(locals()))
    return _weiter(kennung, 2)


def _werte_1(w: dict) -> dict:
    try:
        anzahl = max(1, min(2000, int(str(w["anzahl_leads"]).strip() or 50)))
    except ValueError:
        anzahl = 50
    return {
        "name": w["name"].strip(), "sprache": w["sprache"],
        "anzahl_leads": anzahl, "beschreibung": w["beschreibung"].strip(),
        "verkaeufer_url": _mit_schema(w["verkaeufer_url"]),
        "absender_email": w["absender_email"].strip(),
        "referenz_1": _mit_schema(w["referenz_1"]),
        "referenz_2": _mit_schema(w["referenz_2"]),
        "anweisungen": w["anweisungen"].strip(),
    }


def _mit_schema(url: str) -> str:
    wert = str(url or "").strip()
    if wert and not wert.startswith(("http://", "https://")):
        return "https://" + wert
    return wert


# ---------------------------------------------------------------- Schritt 2

@router.get("/assistent/{kennung}/2")
def schritt_2(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    hinweis = None
    if not entwurf["daten"].get("usp"):
        vorschlag, hinweis = _usp_icp_vorschlag(
            entwurf["daten"].get("verkaeufer_url"),
            _kampagnen_zweck(entwurf["daten"]))
        if vorschlag:
            entwurf = entwuerfe.schritt_speichern(
                _daten_dir(request), kennung, 2, vorschlag)
    return _seite(request, entwurf, 2, {"hinweis": hinweis})


@router.post("/assistent/{kennung}/2")
async def schritt_2_speichern(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    formular = await request.form()
    usp = []
    for nummer in range(20):
        titel = str(formular.get(f"usp_titel_{nummer}") or "").strip()
        if titel:
            usp.append({
                "titel": titel,
                "erklaerung": str(formular.get(f"usp_text_{nummer}") or "").strip(),
            })
    icp = {gruppe: str(formular.get(f"icp_{gruppe}") or "").strip()
           for gruppe in ("firmografisch", "technografisch", "verhalten",
                          "entscheider")}

    if not usp:
        entwurf["daten"]["icp"] = icp
        return _seite(request, entwurf, 2,
                      fehler="Bitte mindestens einen USP eintragen - er trägt "
                             "die spätere E-Mail.", status_code=400)

    entwuerfe.schritt_speichern(_daten_dir(request), kennung, 2,
                                {"usp": usp, "icp": icp})
    return _weiter(kennung, 3)


def _kampagnen_zweck(daten: dict) -> str:
    """Was in Schritt 1 ueber Zweck und Ton gesagt wurde, als ein Text.

    Ohne das sieht die KI beim USP/ICP-Vorschlag NUR die Verkaeufer-Seite
    und beschreibt deren gewoehnlichen Endkunden. Bei einer Partner-
    Kampagne ist das der falsche Empfaenger - der Zielkunde kam am
    14.08.2026 als "mittelständische Unternehmen, die Automation suchen"
    zurueck, obwohl angeschrieben werden sollten die IT-Dienstleister, die
    das Angebot ihren eigenen Kunden weitergeben.
    """
    teile = [
        (daten.get("name") or "").strip(),
        (daten.get("beschreibung") or "").strip(),
        (daten.get("anweisungen") or "").strip(),
    ]
    return "\n".join(t for t in teile if t)


def _usp_icp_vorschlag(url: str | None, kampagnen_zweck: str = ""):
    """Let the AI read the seller's page. Failure is a hint, not a wall."""
    if not url:
        return None, ("Ohne Verkäufer-Webseite kann nichts vorgeschlagen "
                      "werden - bitte von Hand ausfüllen.")
    try:
        from pipeline.ki import KI
        from pipeline.offer import draft_usp_icp
        from pipeline.website import fetch_text

        text = fetch_text(url)
        if not text:
            return None, (f"Die Seite {url} war nicht lesbar - bitte von Hand "
                          f"ausfüllen.")
        return draft_usp_icp(text, KI(), kampagnen_zweck), None
    except Exception as fehler:      # noqa: BLE001
        # Kein erfundener Inhalt: lieber leere Felder und ein ehrlicher
        # Hinweis als ein Vorschlag, den niemand geprueft hat.
        return None, (f"Der Vorschlag hat nicht geklappt ({fehler}). Bitte von "
                      f"Hand ausfüllen.")


# ---------------------------------------------------------------- Schritt 3

@router.get("/assistent/{kennung}/3")
def schritt_3(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung
    bestand = _firmen_bestand(_daten_dir(request))
    return _seite(request, entwurf, 3, {
        "dienste_vorschlaege": dienste_vorschlagen(bestand),
        "radius_stufen": RADIUS_STUFEN,
        "bestand_gesamt": len(bestand),
        "familien": families(),
    })


@router.post("/assistent/{kennung}/3")
async def schritt_3_speichern(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    formular = await request.form()
    ort = str(formular.get("ort") or "").strip()
    dienste = [d.strip() for d in formular.getlist("dienste") if d.strip()]
    eigene = str(formular.get("dienst_eigen") or "").strip()
    if eigene:
        dienste += [t.strip() for t in eigene.split(",") if t.strip()]
    try:
        radius = int(str(formular.get("radius_km") or "50"))
    except ValueError:
        radius = 50

    # Nur das genaue Wort "neu" sammelt - alles andere nutzt den Bestand.
    # Bewusst so herum: ein verlorener Formularwert darf nie Geld ausgeben
    # (gleiches Prinzip wie beim Probe-/Echt-Versand in Schritt 5).
    quelle = "neu" if str(formular.get("firmen_quelle") or "") == "neu" else "bestand"
    werte = {"ort": ort, "radius_km": radius, "dienste": dienste,
             "ohne_ort_mitnehmen": bool(formular.get("ohne_ort_mitnehmen")),
             "firmen_quelle": quelle}
    daten_dir = _daten_dir(request)
    entwuerfe.schritt_speichern(daten_dir, kennung, 3, werte)

    if quelle == "neu":
        anzahl = int(entwurf["daten"].get("anzahl_leads") or 50)
        fehler = _sammlung_starten(daten_dir, kennung, werte, anzahl)
        if fehler:
            return _seite(request, entwurf, 3, {
                "dienste_vorschlaege": dienste_vorschlagen(_firmen_bestand(daten_dir)),
                "radius_stufen": RADIUS_STUFEN,
                "bestand_gesamt": len(_firmen_bestand(daten_dir)),
                "familien": families(),
            }, fehler=fehler, status_code=400)
    return _weiter(kennung, 4)


def _sammlung_stand(daten_dir: Path, entwurf: dict) -> dict | None:
    """Stand der Sammlung dieses Entwurfs - None, wenn keine bestellt war."""
    if entwurf["daten"].get("firmen_quelle") != "neu":
        return None
    from web.sammelmanager import status

    stand = status(daten_dir, entwurf["kennung"])
    # "unbekannt" heisst: bestellt, aber kein Job-Ordner da. Das ist kein
    # Wartezustand, sondern ein Fehlstart - dann lieber den Bestand zeigen
    # als ewig auf etwas zu warten, das nie laeuft.
    return None if stand["zustand"] == "unbekannt" else stand


def _sammlung_starten(daten_dir: Path, kennung: str, werte: dict,
                      anzahl: int) -> str | None:
    """Sammlung im Hintergrund anstossen. Fehlertext oder None.

    Laeuft absichtlich schon HIER los, nicht erst in Schritt 4: so sammelt
    sie, waehrend die naechste Seite gelesen wird - derselbe Trick, mit dem
    die Adress-Suche ihre Minuten unsichtbar macht.

    Die gewuenschte Zahl aus Schritt 1 ist das Sammel-Ziel; ein leeres
    Ortsfeld heisst ganz Deutschland (so steht es am Feld) - dann laeuft
    die Sammlung Region fuer Region, bis das Ziel erreicht ist.
    """
    from web.sammelmanager import SammelFehler, starte

    try:
        starte(daten_dir, kennung, werte["ort"], werte["radius_km"],
               werte["dienste"], ziel_anzahl=anzahl,
               deutschlandweit=not str(werte.get("ort") or "").strip())
    except SammelFehler as fehler:
        return str(fehler)
    except Exception as fehler:      # noqa: BLE001
        return f"Die Sammlung konnte nicht starten: {fehler}"
    return None


# ---------------------------------------------------------------- Schritt 4

@router.get("/assistent/{kennung}/4")
def schritt_4(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    daten_dir = _daten_dir(request)

    # Laeuft fuer diesen Entwurf noch eine Sammlung, hat der Bestand die
    # neuen Firmen noch nicht - dann waere jede Zahl auf dieser Seite
    # falsch. Also warten statt ein leeres Ergebnis zeigen.
    sammlung = _sammlung_stand(daten_dir, entwurf)
    if sammlung and sammlung["zustand"] == "laeuft":
        return _seite(request, entwurf, 4, {"sammlung": sammlung})

    bestand = _firmen_bestand(daten_dir)
    try:
        ergebnis = filtern(
            bestand,
            ort=entwurf["daten"].get("ort", ""),
            radius_km=entwurf["daten"].get("radius_km"),
            dienste=entwurf["daten"].get("dienste") or [],
            gesperrte_domains=_gesperrte(daten_dir))
    except ValueError as fehler:
        return _seite(request, entwurf, 3, {
            "dienste_vorschlaege": dienste_vorschlagen(bestand),
            "radius_stufen": RADIUS_STUFEN,
            "bestand_gesamt": len(bestand),
            "familien": families(),
        }, fehler=str(fehler), status_code=400)

    gewuenscht = int(entwurf["daten"].get("anzahl_leads") or 50)
    auswahl = list(ergebnis["treffer"])
    if entwurf["daten"].get("ohne_ort_mitnehmen"):
        auswahl += ergebnis["ohne_ort"]
    abgewaehlt = set(entwurf["daten"].get("abgewaehlt") or [])

    from pipeline.guthaben import stand as guthaben_stand

    return _seite(request, entwurf, 4, {
        "zahlen": ergebnis["zahlen"],
        "gewuenscht": gewuenscht,
        "firmen": auswahl[:gewuenscht],
        "ohne_ort": ergebnis["ohne_ort"],
        "abgewaehlt": abgewaehlt,
        "bestand_gesamt": len(bestand),
        "sammlung": sammlung,
        "guthaben": guthaben_stand(daten_dir),
    })


@router.post("/assistent/{kennung}/4")
async def schritt_4_speichern(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    formular = await request.form()
    abgewaehlt = set(str(w) for w in formular.getlist("abgewaehlt"))
    gewaehlt = [str(w) for w in formular.getlist("firma") if w not in abgewaehlt]
    if not gewaehlt:
        return RedirectResponse(f"/assistent/{kennung}/4?leer=1", status_code=303)

    daten_dir = _daten_dir(request)
    entwurf = entwuerfe.schritt_speichern(daten_dir, kennung, 4, {
        "abgewaehlt": sorted(abgewaehlt),
        "firmen_domains": gewaehlt,
    })

    # Ab hier laeuft die Adress-Suche im Hintergrund weiter, waehrend
    # Schritt 5 ausgefuellt wird - das ist der ganze Trick, mit dem die
    # Minuten Wartezeit unsichtbar werden.
    fehler = _lauf_starten(request, entwurf, gewaehlt)
    if fehler:
        return _seite(request, entwurf, 4, _schritt_4_inhalt(request, entwurf),
                      fehler=fehler, status_code=400)
    return _weiter(kennung, 5)


def _lauf_starten(request: Request, entwurf: dict, domains: list) -> str | None:
    """Write customer file + company list, then start the normal pipeline.

    Deliberately the SAME subprocess the old route starts. The wizard
    only prepares its input; every guard downstream (blocklist, test
    recipients, approval before handover) stays exactly where it is.
    """
    from web.laufmanager import Laufmanager, LaufBereitsAktiv, LaufmanagerFehler

    daten_dir = _daten_dir(request)
    daten = entwurf["daten"]
    gewuenscht = set(domains)
    firmen = [f for f in _firmen_bestand(daten_dir)
              if (f.get("domain") or f.get("name")) in gewuenscht]

    firmen_pfad = daten_dir / "entwuerfe" / f"{entwurf['kennung']}-firmen.json"
    firmen_pfad.write_text(json.dumps(firmen, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    kunde_datei = _kunde_schreiben(daten_dir, entwurf)
    # Merken, WELCHE Kundendatei zu diesem Entwurf gehoert: Schritt 5 kommt
    # erst NACH diesem Punkt und muss seine Antworten nachtragen koennen
    # (siehe _versand_einstellungen_nachtragen).
    entwuerfe.schritt_speichern(daten_dir, entwurf["kennung"], 4,
                                {"kunde_datei": kunde_datei})

    try:
        lauf_dir = Laufmanager(daten_dir).starte(
            kunde_datei, len(firmen),
            firmen_datei=str(firmen_pfad.relative_to(daten_dir)))
    except LaufBereitsAktiv:
        return ("Für diesen Kunden läuft schon eine Suche. Bitte warten, bis "
                "sie fertig ist.")
    except LaufmanagerFehler as fehler:
        return str(fehler)

    entwuerfe.schritt_speichern(daten_dir, entwurf["kennung"], 4, {
        "kunde_datei": kunde_datei,
        "lauf_slug": lauf_dir.parent.name,
        "lauf_ts": lauf_dir.name,
        "firmen_anzahl": len(firmen),
    })
    return None


def _kunde_schreiben(daten_dir: Path, entwurf: dict) -> str:
    """Turn the wizard's answers into a normal customer file.

    Nothing wizard-specific is invented here: the same fields the rest
    of the pipeline already reads, so a campaign made in the wizard is
    indistinguishable from one made by hand.
    """
    import re

    import yaml

    daten = entwurf["daten"]
    usp_text = "\n".join(
        f"- {u['titel']}: {u.get('erklaerung', '')}".rstrip(": ")
        for u in daten.get("usp") or [])
    icp = daten.get("icp") or {}

    inhalt = {
        "name": daten.get("name") or f"Kampagne {entwurf['kennung']}",
        "webseite": daten.get("verkaeufer_url", ""),
        "angebot": usp_text or daten.get("beschreibung", ""),
        "tonalitaet": "ruhig, erklärend, keine Superlative, keine Ausrufezeichen",
        # "absender" ist der NAME, der unter den Mails steht - er geht in die
        # Textgenerierung. Hier stand vorher die Postfach-Adresse, die Mails
        # waren damit mit einer E-Mail-Adresse statt mit einem Menschen
        # unterschrieben. Erste Zeile der Signatur aus Schritt 5 ist der Name;
        # ohne Signatur bleibt als Notnagel die Adresse.
        "absender": (str(daten.get("signatur") or "").strip().splitlines() or [""])[0]
                    or daten.get("versand_postfach") or daten.get("absender_email", ""),
        "zielgruppe": {
            "titel": ["Geschäftsführer", "Inhaber"],
            "region": [daten.get("ort") or "Deutschland"],
            "firmengroesse": ["alle"],
        },
        # Schritt 5 fragt ABSTAENDE ("nach Mail 1 sieben Tage warten, dann
        # noch einmal sieben"), die Kundendatei will die Tage AB START
        # (Tag 7, Tag 14). Also aufaddieren - sonst steht dort [7, 7] und
        # der Lauf bricht ab, weil die Liste aufsteigend sein muss.
        "follow_up_tage": [
            daten.get("abstand_1_2", 7),
            daten.get("abstand_1_2", 7) + daten.get("abstand_2_3", 7),
        ],
        # Sicherheitsnetz fuer den Probe-Versand: solange versand_modus auf
        # "test" steht, darf diese Kampagne nur an die eigene Adresse gehen.
        "test_empfaenger": [daten.get("absender_email")] if daten.get("absender_email") else [],
        # Schritt 5 (14.08.2026). Vorher blieben diese Antworten im Entwurf
        # liegen und kamen nie bei Instantly an - die Kampagne wurde ohne
        # Absender-Postfach und mit fest eingebautem Zeitplan angelegt.
        "versand_postfach": daten.get("versand_postfach", ""),
        "tageslimit": daten.get("tageslimit", 20),
        "zeit_von": daten.get("zeit_von", "08:00"),
        "zeit_bis": daten.get("zeit_bis", "19:00"),
        "wochentage": daten.get("wochentage") or ["mo", "di", "mi", "do", "fr"],
        "signatur": daten.get("signatur", ""),
        "versand_modus": "echt" if daten.get("versand_modus") == "echt" else "test",
        "maps_suche": f"(Assistent {entwurf['kennung']})",
        "kontakt_rollen": ["Geschäftsführer", "Inhaber"],
        "anbieter_reihenfolge": ["impressum"],
        # Olivers Regel (19.08.2026): Automatisierungs-Anbieter sind
        # Wettbewerber - neue Formular-Kampagnen pruefen das immer, VOR
        # jedem bezahlten Schritt. Alte Kunden-Dateien bleiben unberuehrt.
        "wettbewerber_pruefung": True,
        "anweisungen": daten.get("anweisungen", ""),
    }

    ordner = daten_dir / "kunden"
    ordner.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", str(inhalt["name"]).casefold()).strip("-")
    slug = slug or entwurf["kennung"]
    # Eine bestehende Kundendatei wird NIE ueberschrieben: zwei Kampagnen
    # duerfen denselben Namen tragen, aber "Demo GmbH" im Assistenten darf
    # nicht die gepflegte kunden/demo-gmbh.yaml zerschiessen.
    dateiname = f"kunden/{slug}.yaml"
    if (daten_dir / dateiname).exists():
        dateiname = f"kunden/{slug}-{entwurf['kennung']}.yaml"
    (daten_dir / dateiname).write_text(
        yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    return dateiname


def _schritt_4_inhalt(request: Request, entwurf: dict) -> dict:
    """Rebuild step 4's view data after a failed start."""
    bestand = _firmen_bestand(_daten_dir(request))
    ergebnis = filtern(bestand, ort=entwurf["daten"].get("ort", ""),
                       radius_km=entwurf["daten"].get("radius_km"),
                       dienste=entwurf["daten"].get("dienste") or [],
                       gesperrte_domains=_gesperrte(_daten_dir(request)))
    gewuenscht = int(entwurf["daten"].get("anzahl_leads") or 50)
    auswahl = list(ergebnis["treffer"])
    if entwurf["daten"].get("ohne_ort_mitnehmen"):
        auswahl += ergebnis["ohne_ort"]
    return {"zahlen": ergebnis["zahlen"], "gewuenscht": gewuenscht,
            "firmen": auswahl[:gewuenscht], "ohne_ort": ergebnis["ohne_ort"],
            "abgewaehlt": set(entwurf["daten"].get("abgewaehlt") or []),
            "bestand_gesamt": len(bestand)}


def _gesperrte(daten_dir: Path) -> list:
    eintraege = lade_globale_sperrlisten_eintraege(daten_dir) or []
    domains = []
    for eintrag in eintraege:
        domains.append(eintrag.get("domain") if isinstance(eintrag, dict)
                       else eintrag)
    return [d for d in domains if d]


def _postfaecher(request: Request) -> list:
    """Absender-Postfaecher aus Instantly - leere Liste heisst "von Hand".

    Postfaecher mit ausgeschaltetem Warmup stehen HINTEN und tragen einen
    Warnhinweis. Grund (gemessen am 17.08.2026): Von den Postfaechern mit
    Warmup kam eine Antwort aus einem echten Outlook an, von denen ohne
    Warmup nicht - und zwar auf DERSELBEN Domain. Warmup laeuft nur, wenn
    ein Postfach auch empfangen kann; ist es aus, ist das Postfach oft nur
    zum Senden eingerichtet. Wer so eines waehlt, verliert jede Antwort
    lautlos - genau das ist der echten Kampagne mit 277 Empfaengern
    passiert.

    Bewusst kein Ausblenden: welches Postfach benutzt wird, entscheidet der
    Mensch. Er soll es nur sehen.
    """
    leser = getattr(request.app.state, "instantly_leser", None)
    if leser is None:
        return []
    try:
        stand = leser.postfaecher() or {}
    except Exception:      # noqa: BLE001 - a dead API must not block the wizard
        return []
    eintraege = stand.get("postfaecher") if isinstance(stand, dict) else stand
    gut, fraglich = [], []
    for eintrag in eintraege or []:
        if not isinstance(eintrag, dict):
            if eintrag:
                gut.append({"adresse": str(eintrag), "hinweis": ""})
            continue
        adresse = eintrag.get("email")
        if not adresse:
            continue
        if eintrag.get("warmup") == "an" and eintrag.get("status") == "verbunden":
            gut.append({"adresse": str(adresse), "hinweis": ""})
        else:
            fraglich.append({
                "adresse": str(adresse),
                "hinweis": "Warmup aus - empfängt vermutlich keine Antworten",
            })
    return gut + fraglich


# ---------------------------------------------------------------- Schritt 5

@router.get("/assistent/{kennung}/5")
def schritt_5(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung
    return _seite(request, entwurf, 5, {
        "postfaecher": _postfaecher(request),
        "wochentage": WOCHENTAGE,
    })


@router.post("/assistent/{kennung}/5")
async def schritt_5_speichern(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    formular = await request.form()

    def zahl(feld, standard, kleinste, groesste):
        try:
            return max(kleinste, min(groesste, int(str(formular.get(feld) or standard))))
        except ValueError:
            return standard

    tage = [k for k, _ in WOCHENTAGE if formular.get(f"tag_{k}")]
    werte = {
        "versand_postfach": str(formular.get("versand_postfach") or "").strip(),
        "tageslimit": zahl("tageslimit", 20, 1, 500),
        "zeit_von": str(formular.get("zeit_von") or "08:00"),
        "zeit_bis": str(formular.get("zeit_bis") or "19:00"),
        "wochentage": tage or ["mo", "di", "mi", "do", "fr"],
        "abstand_1_2": zahl("abstand_1_2", 7, 1, 60),
        "abstand_2_3": zahl("abstand_2_3", 7, 1, 60),
        "signatur": str(formular.get("signatur") or "").strip(),
        # Probe oder echter Versand (14.08.2026). Bewusst so herum geprueft:
        # NUR das genaue Wort "echt" oeffnet den Versand an die gefundenen
        # Firmen, alles andere - auch ein fehlendes Feld oder ein Tippfehler
        # - bleibt Probe. Ein verlorener Formularwert darf niemals als
        # "an alle senden" gelesen werden.
        "versand_modus": ("echt" if str(formular.get("versand_modus") or "").strip()
                          == "echt" else "test"),
    }
    if not werte["versand_postfach"]:
        entwurf["daten"].update(werte)
        return _seite(request, entwurf, 5,
                      {"postfaecher": _postfaecher(request),
                       "wochentage": WOCHENTAGE},
                      fehler="Bitte ein Absender-Postfach wählen.",
                      status_code=400)

    entwuerfe.schritt_speichern(_daten_dir(request), kennung, 5, werte)
    _versand_einstellungen_nachtragen(_daten_dir(request), entwurf, werte)
    return _weiter(kennung, 6)


def _versand_einstellungen_nachtragen(daten_dir: Path, entwurf: dict,
                                       werte: dict) -> None:
    """Schritt 5 in die schon geschriebene Kundendatei nachtragen.

    Die Kundendatei entsteht in Schritt 4, weil dort die Suche startet -
    Schritt 5 wird erst DANACH ausgefuellt. Ohne dieses Nachtragen standen
    Postfach, Signatur und Versandart also leer in der Datei, obwohl sie im
    Formular beantwortet waren: die Kampagne wurde wieder ohne Absender
    angelegt, und "Echter Versand" konnte gar nicht ankommen (gefunden am
    17.08.2026 an einer echten Kampagne mit 17 Empfaengern).

    Nur diese Felder werden angefasst; alles andere in der Datei bleibt, wie
    es ist. Fehlt die Datei, passiert nichts - dann gibt es auch keinen Lauf.
    """
    import yaml

    pfad = daten_dir / str(entwurf["daten"].get("kunde_datei") or "")
    if not entwurf["daten"].get("kunde_datei") or not pfad.is_file():
        return
    try:
        inhalt = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return

    inhalt["versand_postfach"] = werte.get("versand_postfach", "")
    inhalt["tageslimit"] = werte.get("tageslimit", 20)
    inhalt["zeit_von"] = werte.get("zeit_von", "08:00")
    inhalt["zeit_bis"] = werte.get("zeit_bis", "19:00")
    inhalt["wochentage"] = werte.get("wochentage") or ["mo", "di", "mi", "do", "fr"]
    inhalt["signatur"] = werte.get("signatur", "")
    inhalt["versand_modus"] = "echt" if werte.get("versand_modus") == "echt" else "test"
    # Der Name unter den Mails: erste Zeile der Signatur, sonst das Postfach.
    name = (str(werte.get("signatur") or "").strip().splitlines() or [""])[0]
    if name or werte.get("versand_postfach"):
        inhalt["absender"] = name or werte["versand_postfach"]

    pfad.write_text(yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


# ---------------------------------------------------------------- Schritt 6

@router.get("/assistent/{kennung}/6")
def schritt_6(request: Request, kennung: str):
    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung
    daten = entwurf["daten"]
    slug, ts = daten.get("lauf_slug"), daten.get("lauf_ts")
    return _seite(request, entwurf, 6, {
        "anzahl_firmen": daten.get("firmen_anzahl")
                         or len(daten.get("firmen_domains") or []),
        "lauf_slug": slug,
        "lauf_ts": ts,
        # Der Lauf laeuft schon seit Schritt 4; hier wird nur sein Stand
        # gezeigt. Dieselbe Status-Datei wie die alte Fortschritts-Seite.
        "status_url": f"/auftraege/{slug}/{ts}/status.json" if slug and ts else None,
        "freigabe_url": f"/pruefen/{slug}/{ts}" if slug and ts else None,
        "excel_url": f"/assistent/{kennung}/kontakte.xlsx" if slug and ts else None,
    })


@router.get("/assistent/{kennung}/kontakte.xlsx")
def kontakte_excel(request: Request, kennung: str):
    """Die fertigen Kontakte als Excel-Datei zum Herunterladen.

    Wird bei jedem Abruf frisch aus dem Laufordner gebaut, nicht
    zwischengespeichert: eine Datei von gestern neben einem Lauf von
    heute waere schlimmer als gar keine.
    """
    import io

    from fastapi.responses import Response

    from pipeline.kontakte_excel import mappe_bauen

    entwurf, umleitung = _entwurf_oder_start(request, kennung)
    if umleitung:
        return umleitung

    daten = entwurf["daten"]
    slug, ts = daten.get("lauf_slug"), daten.get("lauf_ts")
    if not (slug and ts):
        return _seite(request, entwurf, 6, {
            "anzahl_firmen": 0, "lauf_slug": None, "lauf_ts": None,
            "status_url": None, "freigabe_url": None, "excel_url": None},
            fehler="Für diesen Entwurf wurde noch keine Suche gestartet.",
            status_code=400)

    lauf_dir = _daten_dir(request) / "laeufe" / slug / ts
    if not lauf_dir.exists():
        return _seite(request, entwurf, 6, {
            "anzahl_firmen": 0, "lauf_slug": slug, "lauf_ts": ts,
            "status_url": None, "freigabe_url": None, "excel_url": None},
            fehler="Der Laufordner wurde nicht gefunden.", status_code=404)

    puffer = io.BytesIO()
    mappe_bauen(lauf_dir).save(puffer)
    dateiname = f"kontakte-{slug}-{ts}.xlsx"
    return Response(
        puffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument."
                   "spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{dateiname}"'})


@router.get("/assistent/{kennung}/bestand-zahl")
def bestand_zahl(request: Request, kennung: str, ort: str = "",
                 radius_km: int = 50, dienste: str = ""):
    """Wie viele Firmen hat der Bestand fuer diesen Ort und Umkreis?

    Schritt 3 fragt das waehrend des Tippens ab. Vorher musste man erst
    weiterklicken, um zu sehen, dass der Bestand fuer diese Stadt leer ist -
    und stand dann in Schritt 4 vor einer Null, ohne zu wissen warum
    (17.08.2026, auf Wunsch: "sapo shkruash qytetin, të të tregojë sa firma
    ka baza për atë zonë").

    Antwortet immer mit 200 und einem Text, den die Seite direkt anzeigen
    kann - ein unbekannter Ort ist hier kein Fehler, sondern eine Auskunft.
    """
    daten_dir = _daten_dir(request)
    liste = [d.strip() for d in dienste.split(",") if d.strip()]
    try:
        ergebnis = filtern(_firmen_bestand(daten_dir), ort=ort,
                           radius_km=radius_km, dienste=liste,
                           gesperrte_domains=_gesperrte(daten_dir))
    except ValueError as fehler:
        return JSONResponse({"bekannt": False, "treffer": None,
                             "text": str(fehler)})
    treffer = len(ergebnis["treffer"])
    ohne_ort = len(ergebnis["ohne_ort"])
    if treffer:
        text = f"Im Bestand sind {treffer} passende Firmen für diese Angaben."
        if ohne_ort:
            text += f" Dazu {ohne_ort} ohne bekannte Postleitzahl."
    else:
        text = ("Im Bestand ist für diese Angaben keine einzige Firma. "
                "Ohne neues Sammeln bleibt der nächste Schritt leer.")
    return JSONResponse({"bekannt": True, "treffer": treffer,
                         "ohne_ort": ohne_ort, "text": text})

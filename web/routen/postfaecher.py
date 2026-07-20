"""Route fuer den Postfaecher-Bereich (Baustein 2): rein lesende Uebersicht
aller Instantly-Sende-Postfaecher mit Verbindungs- und Anwaerm-Status, damit
das Team Postfach-Probleme im eigenen Werkzeug sieht statt extra in
Instantly nachzuschauen (siehe docs/instantly-api-machbarkeit.md Punkt 4).

Instantly ist ueber request.app.state.instantly_leser fakebar - gleiches
Muster wie web.routen.kampagnen/postfach. Diese Route liest NUR
(web.instantly_leser.InstantlyLeser.postfaecher, nur GET) - kein Knopf zum
Neu-Verbinden/Reparieren: das geht laut Machbarkeits-Check nicht
vollstaendig ohne den Login-Schritt bei Google/Microsoft direkt in
Instantly (Gap 1 dort), deshalb bewusst nur ein ehrlicher Hinweis-Satz statt
einer Aktion, die es hier gar nicht geben kann. Kein POST-Endpunkt in
diesem Modul (Read-only, Plan Baustein 2)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from web import auth
from web.nav import nav_kontext

router = APIRouter()

# Wortwoertlich aus docs/text-leitfaden-interface.md ("Postfaecher").
POSTFAECHER_HINWEIS = ("Hier siehst du, ob eure Postfächer bei Instantly verbunden sind und "
                        "wie weit sie aufgewärmt sind.")
NUR_LESEN_HINWEIS = ("Ein Postfach neu verbinden oder reparieren geht nur in Instantly — "
                     "hier siehst du nur den Stand.")
PROBLEM_BANNER_TITEL = "Verbindungsproblem bei einem Postfach"
PROBLEM_BANNER_TEXT = "Ein Postfach hat gerade ein Problem — bitte in Instantly neu verbinden."

# v4-Muster: echter Instantly-Deep-Link statt Mock-Domain (siehe
# web.routen.kampagnen/postfach fuer dasselbe Prinzip) - fuehrt zur
# Postfach-Verwaltung in Instantly, wo Neu-Verbinden/Reparieren tatsaechlich
# passiert.
INSTANTLY_LINK = "https://app.instantly.ai/app/accounts"
INSTANTLY_KNOPF_TEXT = "In Instantly öffnen ↗"

# status ("verbunden"/"pausiert"/"verbindungsfehler"/"unbekannt", siehe
# web.instantly_leser._POSTFACH_STATUS_TEXT) -> Chip. Farben wortwoertlich
# aus web.routen.kampagnen._CHIP uebernommen (dieselbe "laut bei echtem
# Problem"-Sprache soll im ganzen Interface gleich aussehen).
_STATUS_CHIP = {
    "verbunden": {"text": "VERBUNDEN", "bg": "#1F7A46", "fg": "#FFFFFF"},
    "pausiert": {"text": "PAUSIERT", "bg": "#EAF0F6", "fg": "#2E5A82"},
    "verbindungsfehler": {"text": "VERBINDUNGSFEHLER", "bg": "#F9E9E4", "fg": "#B03320"},
}
_STATUS_CHIP_UNBEKANNT = {"text": "UNBEKANNT", "bg": "#ECEAE1", "fg": "#6E6A5C"}

# warmup ("an"/"aus"/"gesperrt"/"problem"/"unbekannt", siehe
# web.instantly_leser._POSTFACH_WARMUP_TEXT) -> Anzeige-Text (Plan Baustein 2:
# "an/aus/aufwärmen"-Sprache, siehe docs/text-leitfaden-interface.md).
_WARMUP_TEXT = {
    "an": "Aufwärmen läuft",
    "aus": "Aufwärmen aus",
    "gesperrt": "Aufwärmen gesperrt",
    "problem": "Aufwärmen: Problem",
    "unbekannt": "Aufwärmen unbekannt",
}


def _hole_leser(request: Request):
    """Gleiches Muster wie web.routen.kampagnen/postfach._hole_leser: Tests
    faken app.state.instantly_leser, sonst der GETEILTE InstantlyLeser der
    App (IMPORTANT Review-Fund, siehe web.instantly_leser.geteilten_leser -
    EIN Objekt fuer alle Requests, sonst ist der 60s-Cache nie wirksam)."""
    leser = getattr(request.app.state, "instantly_leser", None)
    if leser is not None:
        return leser
    from web.instantly_leser import geteilten_leser

    return geteilten_leser(request.app)


def postfaecher_stand(request: Request) -> dict:
    """Holt den Postfaecher-Stand fehlertolerant - oeffentlich (kein "_"-
    Praefix), damit web.routen.dashboard._postfach_probleme denselben,
    sicheren Zugriff nutzt statt _hole_leser()/postfaecher() selbst
    aufzurufen (Review-Fund/Regression, siehe unten).

    Fehlt INSTANTLY_API_KEY (z.B. ein Aufbau ganz ohne Schluessel) UND ist
    kein app.state.instantly_leser gesetzt, wirft schon das BAUEN des
    Lesers (web.instantly_leser.geteilten_leser: ein bloßer
    os.environ[...]-Zugriff) ein KeyError - VOR jedem HTTP-Aufruf, also
    bevor InstantlyLeser.postfaecher() seine eigene Fehlertoleranz (siehe
    dort: faengt nur RequestException/RuntimeError/ValueError/KeyError aus
    einem tatsaechlichen API-Aufruf ab) ueberhaupt greifen lassen kann.
    Das ist kein Instantly-AUSFALL, sondern ein fehlendes Konto-Setup -
    wird hier trotzdem wie ein Ausfall behandelt (degradiert statt
    abzustuerzen): weder die Postfaecher-Seite noch das Dashboard sollen
    deswegen einen 500er zeigen, sondern den ehrlichen 'Live-Stand gerade
    nicht erreichbar'-Zustand (bzw. auf dem Dashboard: die Zeile bleibt
    einfach abwesend)."""
    try:
        leser = _hole_leser(request)
        return leser.postfaecher()
    except KeyError:
        return {"postfaecher": [], "erreichbar": False, "stand": None}


def postfach_problem_zeilen(stand: dict) -> list[dict]:
    """Reine Aufbereitung (kein Netzwerk-Zugriff) - baut aus einem bereits
    abgerufenen InstantlyLeser.postfaecher()-Ergebnis die Liste der
    Postfaecher mit Verbindungsfehler. Oeffentlich (kein "_"-Praefix), damit
    web.routen.dashboard denselben, schon abgerufenen Stand fuer die
    laute Dashboard-Zeile wiederverwenden kann (Plan Baustein 2: "reuse the
    shared leser instance; don't add per-render heavy calls") statt
    postfaecher() ein zweites Mal aufzurufen."""
    return [p for p in stand.get("postfaecher", []) if p["status"] == "verbindungsfehler"]


def _live_stand_hinweis(stand: dict) -> str | None:
    """Gleiches Wording wie web.routen.kampagnen._live_stand_hinweis, hier
    bewusst eigenstaendig (statt importiert) - postfaecher() liefert EIN
    Ergebnis (kein dict je ID), die dortige Funktion erwartet eine Liste von
    Ergebnissen."""
    if stand.get("erreichbar"):
        return None
    if stand.get("stand") is not None:
        return f"Live-Stand gerade nicht erreichbar — Stand von {stand['stand'].strftime('%H:%M')}."
    return "Live-Stand gerade nicht erreichbar — noch kein Stand abgerufen."


def _zeilen(stand: dict) -> list[dict]:
    zeilen = []
    for p in stand.get("postfaecher", []):
        chip = _STATUS_CHIP.get(p["status"], _STATUS_CHIP_UNBEKANNT)
        zeilen.append({
            "email": p["email"],
            "chip_text": chip["text"], "chip_bg": chip["bg"], "chip_fg": chip["fg"],
            "warmup_text": _WARMUP_TEXT.get(p["warmup"], _WARMUP_TEXT["unbekannt"]),
            "daily_limit": p["daily_limit"] if p["daily_limit"] is not None else "–",
        })
    return zeilen


@router.get("/postfaecher")
# Bewusst KEIN `async def` - IMPORTANT Review-Fund: postfaecher_stand(request)
# ruft ueber InstantlyLeser.postfaecher() einen synchronen, blockierenden
# HTTP-Aufruf auf (siehe web.instantly_leser). Als Koroutine wuerde das den
# Event-Loop fuer ALLE gleichzeitigen Nutzer blockieren (gleicher Grund wie
# web/routen/kampagnen.py). Als normale `def`-Funktion fuehrt FastAPI die
# Route stattdessen in einem Threadpool aus.
def postfaecher_liste(request: Request):
    stand = postfaecher_stand(request)
    problem_zeilen = postfach_problem_zeilen(stand)

    return request.app.state.templates.TemplateResponse(
        request, "postfaecher.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "postfaecher_hinweis": POSTFAECHER_HINWEIS,
            "nur_lesen_hinweis": NUR_LESEN_HINWEIS,
            "problem_banner_titel": PROBLEM_BANNER_TITEL,
            "problem_banner_text": PROBLEM_BANNER_TEXT,
            "hat_problem": len(problem_zeilen) > 0,
            "postfaecher": _zeilen(stand),
            "postfaecher_leer": stand.get("erreichbar") and not stand.get("postfaecher"),
            "live_stand_hinweis": _live_stand_hinweis(stand),
            "stand_text": stand["stand"].strftime("%H:%M") if stand.get("stand") else None,
            "instantly_link": INSTANTLY_LINK,
            "instantly_knopf_text": INSTANTLY_KNOPF_TEXT,
        },
    )

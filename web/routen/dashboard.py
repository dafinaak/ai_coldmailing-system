"""Route fuers Dashboard (Task 7) - die Startseite ('/'). Baut absichtlich
NICHTS neu zusammen, was Task 5/6 schon koennen: die wartenden Freigaben
kommen aus web.wartende.wartende_laeufe (Task 5-Logik, ab Task 7 geteilt),
die lokale Lauf-Aggregation + der Live-Stand-Abruf aus
web.routen.kampagnen._alle_laeufe/_stand_fuer/_kampagnen_zeilen_aus_stand
(Task 6). Instantly wird GENAU EINMAL pro Seitenaufruf abgefragt (ueber
_stand_fuer, das den 60s-Cache von web.instantly_leser.InstantlyLeser
nutzt) - dieser eine stand_by_id-Datensatz speist Kachel 'Aktive
Kampagnen', die Konto-Problem-Zeilen UND die Kampagnen-Kurzliste. Ein
zweiter Abruf pro Kachel wuerde bei kaltem Cache + ausgefallener API die
Seite unnoetig lange blockieren (siehe InstantlyLeser._hole_frisch: 3
sequentielle GETs je Kampagne, Timeout 20s)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request

from web import auth
from web.nav import nav_kontext
from web.routen import kampagnen as kampagnen_routen
from web.routen.auftraege import _lade_meta
from web.wartende import wartende_laeufe

router = APIRouter()

DASH_HINWEIS = "Hier siehst du auf einen Blick, was läuft und was auf dich wartet."

KEIN_WERT = "–"


def _aktive_kampagnen_kachel(request: Request, mit_kampagne: list[dict]) -> tuple[dict, int | str]:
    """Ein einziger Instantly-Abruf (_stand_fuer, siehe Modul-Docstring) fuer
    die Kachel 'Aktive Kampagnen'. Ohne Kampagnen ist das ehrlich 0 (kein
    unbekannter Zustand, es gibt schlicht keine); gibt es Kampagnen, aber zu
    KEINER einzigen je einen erfolgreichen Abruf (auch nicht aus dem
    Cache), ist der Wert unbekannt statt einer erfundenen 0 - dann zeigt die
    Kachel KEIN_WERT."""
    stand_by_id = kampagnen_routen._stand_fuer(request, mit_kampagne)
    if not mit_kampagne:
        return stand_by_id, 0
    bekannt = any(s.get("status") is not None for s in stand_by_id.values())
    if not bekannt:
        return stand_by_id, KEIN_WERT
    aktive = sum(1 for s in stand_by_id.values() if s.get("status") == "aktiv")
    return stand_by_id, aktive


def _angehalten_banner(daten_dir, angehaltene: list[dict]) -> dict | None:
    """v4-Wortlaut ('Angehalten: Anschreiben für <Kunde> (gestartet
    <Datum>)') mit einem Link zur Fortschrittsseite des Auftrags statt
    einem direkten Fortsetzen-Knopf hier (Plan Task 7: 'Fortsetzen link to
    the run's progress page') - der eigentliche Fortsetzen-Knopf lebt
    bereits dort (auftrag_fortschritt.html, Task 4)."""
    if not angehaltene:
        return None
    erste = angehaltene[0]
    lauf_dir = Path(daten_dir) / "laeufe" / erste["slug"] / erste["ts"]
    meta = _lade_meta(lauf_dir)
    fehler = erste["fehler"] or {}
    titel = f"Angehalten: Anschreiben für {erste['kunde_name']}"
    if meta.get("gestartet_am"):
        titel += f" (gestartet {meta['gestartet_am']})"
    text = f"{fehler.get('was', '')} {fehler.get('nicht', '')}".strip()
    return {
        "titel": titel,
        "text": text,
        "link": f"/auftraege/{erste['slug']}/{erste['ts']}",
    }


def _kontoproblem_zeilen(mit_kampagne: list[dict], stand_by_id: dict) -> list[dict]:
    """Konto-Stoerungen (Account Suspended/Unhealthy/Bounce Protect, siehe
    web.instantly_leser) sind KEIN normaler Zustand - eigene, laute Zeile
    auf dem Dashboard statt nur im Kampagnen-Bereich zu verstecken (Plan
    Task 7: 'also surface kontoproblem campaigns as a loud line')."""
    zeilen = []
    for eintrag in mit_kampagne:
        stand = stand_by_id.get(eintrag["campaign_id"], {})
        if stand.get("status") != "kontoproblem":
            continue
        zeilen.append({
            "slug": eintrag["slug"], "ts": eintrag["ts"],
            "kunde_name": eintrag["kunde_name"],
            "name": stand.get("name") or f"[TEST] {eintrag['kunde_name']}",
        })
    return zeilen


@router.get("/")
# Bewusst KEIN `async def` - IMPORTANT Review-Fund: _aktive_kampagnen_kachel
# ruft ueber _stand_fuer synchron InstantlyLeser.kampagnen_stand auf
# (blockierende HTTP-Aufrufe bei kaltem Cache, siehe Modul-Docstring). Als
# Koroutine wuerde das den Event-Loop fuer ALLE gleichzeitigen Nutzer
# blockieren (gleicher Grund wie web/routen/auftraege.py). Als normale
# `def`-Funktion fuehrt FastAPI die Route stattdessen in einem Threadpool
# aus.
def dashboard(request: Request):
    daten_dir = request.app.state.daten_dir
    laeufe = kampagnen_routen._alle_laeufe(daten_dir)
    wartende = wartende_laeufe(daten_dir)

    mit_kampagne = [l for l in laeufe if l["campaign_id"]]
    stand_by_id, aktive_anzahl = _aktive_kampagnen_kachel(request, mit_kampagne)
    live_stand_hinweis = kampagnen_routen._live_stand_hinweis(list(stand_by_id.values()))

    dash_kampagnen = kampagnen_routen._kampagnen_zeilen_aus_stand(mit_kampagne[:4], stand_by_id)
    kontoproblem = _kontoproblem_zeilen(mit_kampagne, stand_by_id)

    angehaltene = [l for l in laeufe if l["zustand"] == "angehalten"]
    angehalten_banner = _angehalten_banner(daten_dir, angehaltene)

    kacheln = [
        {
            "wert": len(wartende), "label": "Warten auf deine Freigabe",
            "sub": "Das ist deine Aufgabe", "link": "/pruefen",
            "hervorgehoben": len(wartende) > 0,
        },
        {
            "wert": aktive_anzahl, "label": "Aktive Kampagnen",
            "sub": "Instantly versendet", "link": "/kampagnen",
        },
        # TODO(verifizieren am echten Konto): InstantlyLeser.kampagnen_stand
        # (Task 6) liefert aktuell keinen "heute versendet"-Zaehler, nur die
        # Gesamtsumme seit Kampagnenstart (emails_sent_count) - ein
        # erfundener Wert waere hier schlimmer als ein ehrlicher Platzhalter.
        {
            "wert": KEIN_WERT, "label": "Heute versendet",
            "sub": "Mails über alle Kampagnen", "link": "/kampagnen",
        },
        # TODO(Task 9 Postfach): echte Neu-Zaehlung. InstantlyLeser.
        # kampagnen_stand()["antworten"] (Task 6) ist der LIFETIME-
        # reply_count der Kampagne, nicht "neu seit dem letzten Besuch" -
        # das hier auszugeben waere irrefuehrend (Reviewer-Fix 1), deshalb
        # bis Task 9 der gleiche ehrliche Platzhalter wie 'Heute versendet'.
        {
            "wert": KEIN_WERT, "label": "Neue Antworten",
            "sub": "Im Postfach lesen", "link": "/postfach",
        },
    ]

    return request.app.state.templates.TemplateResponse(
        request, "dashboard.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "dash_hinweis": DASH_HINWEIS,
            "kacheln": kacheln,
            "angehalten_banner": angehalten_banner,
            "kontoproblem": kontoproblem,
            "wartende": wartende,
            "dash_kampagnen": dash_kampagnen,
            "live_stand_hinweis": live_stand_hinweis,
        },
    )

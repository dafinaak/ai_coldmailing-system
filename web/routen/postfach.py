"""Route fuer den Postfach-Bereich (Task 9): rein lesende Sicht auf
Konversationen aus Instantly, gruppiert nach Kontakt. EIN Screen (wie in
docs/design/Poleposition-v4.dc.html, istPostfach-Block: Liste links,
gewaehlte Konversation rechts, KEIN eigener Detail-Screen) - die Auswahl
laeuft ueber den Query-Parameter "kontakt" statt client-seitigem State,
weil dieses Interface serverseitig rendert (siehe Plan Task 9: nur EIN
Template `postfach.html`, anders als Kampagnen mit zwei Templates).

Instantly ist ueber request.app.state.instantly_leser fakebar - gleiches
Muster wie web.routen.kampagnen/freigabe. EIN Abruf je Seitenaufruf
(InstantlyLeser.emails_stand, 60s-Cache) speist sowohl die
Konversationsliste (instantly_leser.konversationen_aus_email_stand, reine
Aufbereitung ohne Netzwerk) als auch den ehrlichen "Live-Stand gerade
nicht erreichbar"-Hinweis (web.routen.kampagnen._live_stand_hinweis,
wiederverwendet statt dupliziert - exakt das Muster aus
web.routen.dashboard). Kampagnen-IDs kommen aus
web.routen.kampagnen._alle_laeufe (Quelle der Wahrheit: lokale
Laufordner, kein eigener Weg, Kampagnen zu finden).

Kein Antwortfeld, keine POST-Route - der Bereich ist bewusst rein lesend
(Plan Task 9: "Read-only: no POST routes, no reply field")."""
from __future__ import annotations

import os

from fastapi import APIRouter, Request

from web import auth
from web.instantly_leser import konversationen_aus_email_stand
from web.kontakte import sammle_kontakte
from web.nav import nav_kontext
from web.routen import kampagnen as kampagnen_routen

router = APIRouter()

# Wortwoertlich aus der v4-Vorlage (istPostfach-Block) - Kopfsatz der Seite.
POSTFACH_HINWEIS = ("Alle Gespräche an einem Ort: unsere Mails und die Antworten darauf. "
                     "Antworten schreibst du in Instantly.")

# Plan Task 9 (woertlich aus dem Aufgabenbrief): ehrlicher Hinweis statt
# stiller Leere, wenn Instantly erreichbar ist, aber (noch) keine einzige
# Nachricht liefert - unterscheidet sich bewusst vom "nicht erreichbar"-Fall
# unten (web.routen.kampagnen._live_stand_hinweis): hier hat die API
# geantwortet, es gibt schlicht (noch) nichts zu zeigen.
KEINE_ANTWORTEN_HINWEIS = "Antworten siehst du derzeit nur in Instantly."

# v4 zeigt als Platzhalter nur "https://app.instantly.ai" (Mock-Domain ohne
# echten Pfad). Wie schon in kampagne_detail.html (Task 6, echter
# Kampagnen-Deep-Link statt Mock-Domain) verlinken wir hier bewusst auf den
# ECHTEN Instantly-Unibox-Pfad statt die Platzhalter-Domain zu uebernehmen -
# der Knopf soll tatsaechlich zum Antworten fuehren, nicht nur zur Startseite.
INSTANTLY_LINK = "https://app.instantly.ai/app/unibox"

# Wortwoertlich aus der v4-Vorlage.
INSTANTLY_KNOPF_TEXT = "In Instantly antworten ↗"


def _hole_leser(request: Request):
    """Gleiches Muster wie web.routen.kampagnen._hole_leser (bewusst
    dupliziert statt importiert - dieses Modul soll nicht von einer
    privaten Funktion eines anderen web.routen.*-Moduls fuer seinen
    zentralen Instantly-Zugriff abhaengen, nur fuer die reine
    Lauf-Aggregation unten)."""
    leser = getattr(request.app.state, "instantly_leser", None)
    if leser is not None:
        return leser
    from web.instantly_leser import InstantlyLeser

    return InstantlyLeser(os.environ["INSTANTLY_API_KEY"])


def _kontakt_info_je_email(daten_dir) -> dict[str, dict]:
    """email (klein/getrimmt, wie web.kontakte.sammle_kontakte sie schon
    liefert) -> {"name", "firma"} - fuer die Anreicherung der
    Konversationsliste, wenn der Kontakt lokal bekannt ist (Plan Task 9:
    "firma if derivable from local contacts data ... filesystem-only; else
    just email"). Dateisystem-only, kein Instantly-Zugriff."""
    return {k["email"]: {"name": k.get("name", ""), "firma": k.get("firma", "")}
            for k in sammle_kontakte(daten_dir)}


def _format_zeit(zeit) -> str:
    return zeit.strftime("%d.%m.%Y, %H:%M") if zeit else "—"


def _konversations_zeilen(konversationen: list[dict], kontakt_info: dict,
                           ausgewaehlte_email: str | None) -> list[dict]:
    zeilen = []
    for k in konversationen:
        info = kontakt_info.get(k["kontakt_email"], {})
        zeilen.append({
            "kontakt_email": k["kontakt_email"],
            "name": info.get("name") or k["kontakt_email"],
            "firma": info.get("firma", ""),
            "betreff": k["betreff"],
            "letzte_zeit": _format_zeit(k["letzte_zeit"]),
            "richtung_letzte": k["richtung_letzte"],
            "aktiv": k["kontakt_email"] == ausgewaehlte_email,
        })
    return zeilen


def _nachrichten_zeilen(nachrichten: list[dict], kontakt_name: str) -> list[dict]:
    """"wer" ist "Wir" bei gesendeten Nachrichten, sonst der (lokal
    bekannte, sonst die E-Mail-Adresse als) Kontaktname - fuer die
    optisch unterscheidbare Chronologie im Detailbereich (Plan Task 9:
    "sent vs received visually distinct per v4")."""
    return [
        {
            "richtung": m["richtung"],
            "wer": "Wir" if m["richtung"] == "gesendet" else kontakt_name,
            "zeit": _format_zeit(m["zeit"]),
            "betreff": m["betreff"],
            "text": m["text"],
        }
        for m in nachrichten
    ]


@router.get("/postfach")
async def postfach(request: Request):
    daten_dir = request.app.state.daten_dir
    laeufe = kampagnen_routen._alle_laeufe(daten_dir)
    campaign_ids = sorted({l["campaign_id"] for l in laeufe if l["campaign_id"]})

    leser = _hole_leser(request)
    stand_by_id = leser.emails_stand(campaign_ids)
    konversationen = konversationen_aus_email_stand(stand_by_id)
    live_stand_hinweis = kampagnen_routen._live_stand_hinweis(list(stand_by_id.values()))

    gewuenscht = (request.query_params.get("kontakt") or "").strip().lower()
    treffer = next((k for k in konversationen if k["kontakt_email"] == gewuenscht), None)
    ausgewaehlt = treffer or (konversationen[0] if konversationen else None)

    kontakt_info = _kontakt_info_je_email(daten_dir)
    zeilen = _konversations_zeilen(
        konversationen, kontakt_info, ausgewaehlt["kontakt_email"] if ausgewaehlt else None)

    detail = None
    if ausgewaehlt is not None:
        info = kontakt_info.get(ausgewaehlt["kontakt_email"], {})
        kontakt_name = info.get("name") or ausgewaehlt["kontakt_email"]
        detail = {
            "kontakt_email": ausgewaehlt["kontakt_email"],
            "name": kontakt_name,
            "firma": info.get("firma", ""),
            "betreff": ausgewaehlt["betreff"],
            "letzte_zeit": _format_zeit(ausgewaehlt["letzte_zeit"]),
            "nachrichten": _nachrichten_zeilen(ausgewaehlt["nachrichten"], kontakt_name),
        }

    return request.app.state.templates.TemplateResponse(
        request, "postfach.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "postfach_hinweis": POSTFACH_HINWEIS,
            "konversationen": zeilen,
            "konversationen_leer": len(zeilen) == 0,
            # Nur zeigen, wenn ueberhaupt Kampagnen abgefragt wurden UND die
            # Abfrage erreichbar war UND trotzdem nichts zurueckkam - ohne
            # jede Kampagne (campaign_ids leer) waere der Satz irrefuehrend
            # ("siehst du derzeit nur in Instantly" setzt voraus, dass es
            # ueberhaupt etwas geben KOENNTE), dann bleibt es beim
            # neutralen Leer-Kasten-Text im Template.
            "keine_antworten_hinweis": (
                KEINE_ANTWORTEN_HINWEIS
                if (campaign_ids and not live_stand_hinweis and not zeilen) else None),
            "live_stand_hinweis": live_stand_hinweis,
            "detail": detail,
            "instantly_link": INSTANTLY_LINK,
            "instantly_knopf_text": INSTANTLY_KNOPF_TEXT,
        },
    )

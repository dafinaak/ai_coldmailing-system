"""Postfach: Instantly-Konversationen lesen und sicher darauf antworten.

Die Auswahl bleibt serverseitig über ``kontakt``. Eine Antwort ist nur auf
eine tatsächlich gelesene, eingegangene Instantly-Mail möglich. Ein kurz
gültiger, signierter und atomar nur einmal nutzbarer Beleg bindet den
Versand an Kontakt und Mail-ID.
"""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from web import auth
from web.antwort_freigabe import (
    AntwortFreigabeBenutzt,
    AntwortFreigabeUngueltig,
    AntwortTextUngueltig,
    erstelle_antwort_freigabe,
    erstelle_versandhinweis,
    pruefe_antwort_freigabe,
    pruefe_versandhinweis,
    validiere_antworttext,
    verbrauche_antwort_freigabe,
)
from web.instantly_antworter import (
    InstantlyAntwortAbgelehnt,
    InstantlyAntwortStatusUnklar,
    geteilten_antworter,
)
from web.instantly_leser import konversationen_aus_email_stand
from web.kontakte import sammle_kontakte
from web.nav import nav_kontext
from web.routen import kampagnen as kampagnen_routen

router = APIRouter()

# Wortwoertlich aus der v4-Vorlage (istPostfach-Block) - Kopfsatz der Seite.
POSTFACH_HINWEIS = (
    "Alle Gespräche an einem Ort: unsere Mails und die Antworten darauf."
)

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
INSTANTLY_KNOPF_TEXT = "In Instantly öffnen ↗"


def _hole_leser(request: Request):
    """Gleiches Muster wie web.routen.kampagnen._hole_leser (bewusst
    dupliziert statt importiert - dieses Modul soll nicht von einer
    privaten Funktion eines anderen web.routen.*-Moduls fuer seinen
    zentralen Instantly-Zugriff abhaengen, nur fuer die reine
    Lauf-Aggregation unten). Nutzt genau wie dort den GETEILTEN
    InstantlyLeser der App (IMPORTANT Review-Fund, siehe
    web.instantly_leser.geteilten_leser), sonst ist der 60s-Cache nie
    wirksam."""
    leser = getattr(request.app.state, "instantly_leser", None)
    if leser is not None:
        return leser
    from web.instantly_leser import geteilten_leser

    return geteilten_leser(request.app)


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


def _antwortziel(
    konversation: dict | None, reply_to_uuid: str | None = None
) -> dict | None:
    """Findet nur eine belegte, eingegangene Instantly-Mail als Ziel."""
    if not konversation:
        return None
    for nachricht in reversed(konversation["nachrichten"]):
        if nachricht.get("richtung") != "empfangen":
            continue
        if reply_to_uuid is not None and nachricht.get("id") != reply_to_uuid:
            continue
        if all(
            isinstance(nachricht.get(feld), str)
            and bool(nachricht[feld].strip())
            for feld in ("id", "eaccount", "campaign_id")
        ):
            return nachricht
    return None


def _antwort_betreff(betreff: str) -> str:
    bereinigt = (betreff or "").strip()
    if bereinigt.casefold().startswith("re:"):
        return bereinigt
    return f"Re: {bereinigt or '(ohne Betreff)'}"


def _lade_postfach(request: Request, gewuenscht: str | None = None):
    daten_dir = request.app.state.daten_dir
    laeufe = kampagnen_routen._alle_laeufe(daten_dir)
    campaign_ids = sorted({l["campaign_id"] for l in laeufe if l["campaign_id"]})

    leser = _hole_leser(request)
    stand_by_id = leser.emails_stand(campaign_ids)
    konversationen = konversationen_aus_email_stand(stand_by_id)
    live_stand_hinweis = kampagnen_routen._live_stand_hinweis(list(stand_by_id.values()))

    if gewuenscht is None:
        gewuenscht = request.query_params.get("kontakt") or ""
    gewuenscht = gewuenscht.strip().casefold()
    treffer = next((k for k in konversationen if k["kontakt_email"] == gewuenscht), None)
    ausgewaehlt = treffer or (konversationen[0] if konversationen else None)
    return (
        daten_dir,
        campaign_ids,
        leser,
        konversationen,
        live_stand_hinweis,
        ausgewaehlt,
    )


def _render_postfach(
    request: Request,
    *,
    daten_dir,
    campaign_ids,
    konversationen,
    live_stand_hinweis,
    ausgewaehlt,
    status_code: int = 200,
    antwort_text: str = "",
    antwort_fehler: str | None = None,
    antwort_unsicher: bool = False,
):
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
        ziel = _antwortziel(ausgewaehlt)
        if ziel is not None and not antwort_unsicher:
            detail["antwort"] = {
                "konto": ziel["eaccount"],
                "token": erstelle_antwort_freigabe(
                    request.app.state.serializer,
                    kontakt=ausgewaehlt["kontakt_email"],
                    reply_to_uuid=ziel["id"],
                ),
            }

    kontakt = ausgewaehlt["kontakt_email"] if ausgewaehlt else ""
    antwort_erfolg = pruefe_versandhinweis(
        request.app.state.serializer,
        request.query_params.get("versand") or "",
        kontakt=kontakt,
    )

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
            "antwort_text": antwort_text,
            "antwort_fehler": antwort_fehler,
            "antwort_unsicher": antwort_unsicher,
            "antwort_erfolg": antwort_erfolg,
        },
        status_code=status_code,
    )


@router.get("/postfach")
# Der Instantly-Abruf ist synchron und läuft deshalb im FastAPI-Threadpool.
def postfach(request: Request):
    (
        daten_dir,
        campaign_ids,
        _,
        konversationen,
        live_stand_hinweis,
        ausgewaehlt,
    ) = _lade_postfach(request)
    return _render_postfach(
        request,
        daten_dir=daten_dir,
        campaign_ids=campaign_ids,
        konversationen=konversationen,
        live_stand_hinweis=live_stand_hinweis,
        ausgewaehlt=ausgewaehlt,
    )


@router.post("/postfach/antworten")
def postfach_antworten(
    request: Request,
    kontakt: str = Form(...),
    antwort_token: str = Form(...),
    antwort_text: str = Form(""),
):
    kontakt = kontakt.strip().casefold()
    (
        daten_dir,
        campaign_ids,
        leser,
        konversationen,
        live_stand_hinweis,
        ausgewaehlt,
    ) = _lade_postfach(request, kontakt)

    def fehler_anzeigen(
        meldung: str, status_code: int, *, text: str = "", unsicher: bool = False
    ):
        return _render_postfach(
            request,
            daten_dir=daten_dir,
            campaign_ids=campaign_ids,
            konversationen=konversationen,
            live_stand_hinweis=live_stand_hinweis,
            ausgewaehlt=ausgewaehlt,
            status_code=status_code,
            antwort_text=text,
            antwort_fehler=meldung,
            antwort_unsicher=unsicher,
        )

    try:
        text = validiere_antworttext(antwort_text)
        freigabe = pruefe_antwort_freigabe(
            request.app.state.serializer, antwort_token
        )
    except (AntwortTextUngueltig, AntwortFreigabeUngueltig) as fehler:
        return fehler_anzeigen(str(fehler), 400, text=antwort_text)

    if freigabe["kontakt"] != kontakt:
        return fehler_anzeigen(
            "Kontakt und Antwortfreigabe passen nicht zusammen.",
            400,
            text=antwort_text,
        )
    ziel = _antwortziel(ausgewaehlt, freigabe["reply_to_uuid"])
    if (
        ziel is None
        or ausgewaehlt is None
        or ausgewaehlt["kontakt_email"] != kontakt
    ):
        return fehler_anzeigen(
            "Das belegte Antwortziel wurde nicht gefunden.",
            400,
            text=antwort_text,
        )

    # Die Konfiguration wird vor dem einmaligen Verbrauch geprüft. Danach
    # gibt es genau einen Versandversuch und bewusst keine Wiederholung.
    try:
        antworter = geteilten_antworter(request.app)
    except RuntimeError:
        return fehler_anzeigen(
            "Instantly ist für Antworten noch nicht eingerichtet.",
            503,
            text=antwort_text,
        )
    try:
        verbrauche_antwort_freigabe(daten_dir, freigabe["nonce"])
    except AntwortFreigabeBenutzt:
        return fehler_anzeigen(
            "Diese Antwortfreigabe wurde bereits benutzt. Bitte prüfe den "
            "Verlauf in Instantly, bevor du erneut sendest.",
            409,
            text=antwort_text,
            unsicher=True,
        )

    try:
        versand = antworter.antworten(
            eaccount=ziel["eaccount"],
            reply_to_uuid=ziel["id"],
            betreff=_antwort_betreff(ziel.get("betreff", "")),
            text=text,
        )
    except InstantlyAntwortAbgelehnt:
        return fehler_anzeigen(
            "Instantly hat die Antwort nicht angenommen. "
            "Es wurde kein erfolgreicher Versand bestätigt.",
            502,
            text=antwort_text,
        )
    except InstantlyAntwortStatusUnklar:
        return fehler_anzeigen(
            "Der Versandstatus ist unklar. Bitte prüfe den Verlauf in "
            "Instantly, bevor du erneut sendest.",
            502,
            text=antwort_text,
            unsicher=True,
        )

    leser.verwerfe_email_cache(ziel["campaign_id"])
    versandhinweis = erstelle_versandhinweis(
        request.app.state.serializer,
        kontakt=kontakt,
        antwort_id=str(versand["id"]),
    )
    ziel_url = "/postfach?" + urlencode(
        {"kontakt": kontakt, "versand": versandhinweis}
    )
    return RedirectResponse(ziel_url, status_code=303)

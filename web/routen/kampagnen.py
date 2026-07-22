"""Route fuer den Kampagnen-Bereich (Task 6): Liste aller Kampagnen (mit
Live-Stand aus Instantly) plus die Auftraege, aus denen noch Kampagnen
werden ("in Vorbereitung"), und die Detail-Ansicht einer einzelnen
Kampagne. Instantly ist ueber request.app.state.instantly_leser fakebar -
gleiches Muster wie request.app.state.instantly in web.routen.freigabe fuer
den Schreib-Pfad. Diese Route liest NUR (web.instantly_leser.InstantlyLeser,
nur GET) - sie legt nie eine Kampagne an und aktiviert nie eine."""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from pipeline.approval import freigabe_info
from pipeline.run_store import RunStore
from web import auth
from web.laufmanager import Laufmanager, _lade_json_sicher, wartet_seit_text as _wartet_seit_text
from web.nav import nav_kontext
from web.wartende import format_deutsches_datum, kunde_fuer as _kunde_fuer

router = APIRouter()

# Baustein 1 (Kampagne im Tool scharf schalten/pausieren) - Bestaetigungssaetze
# woertlich aus dem Auftrag/Leitfaden (docs/text-leitfaden-interface.md):
# ehrlich sagen, was beim Klick passiert, statt es hinter einem
# beilaeufigen Knopf zu verstecken.
AKTIVIEREN_BESTAETIGUNG = ("Wenn du jetzt startest, verschickt Instantly die E-Mails dieser "
                          "Kampagne nach Zeitplan. Fortfahren?")
PAUSIEREN_BESTAETIGUNG = ("Der Versand wird angehalten. Schon verschickte E-Mails bleiben "
                         "unberührt.")

# Fehlertext, wenn aktiviere_kampagne()/pausiere_kampagne() scheitert (HTTP-
# Fehler oder Netzwerkproblem, siehe pipeline.senders.instantly._post) -
# gleiches Prinzip wie web.routen.freigabe._versand_fehlertext: nichts ist
# verloren gegangen, der bisherige Zustand bleibt bestehen.
_AKTION_FEHLERTEXT = ("Instantly hat gerade nicht geantwortet. Es ist nichts verloren gegangen — "
                     "versuch es in ein paar Minuten noch einmal.")

# Chip-Farben woertlich aus docs/design/Poleposition-v4.dc.html (Methode
# kampChip) - Liste und Detail zeigen damit dieselben Farben wie die
# eingefrorene Vorlage.
_CHIP = {
    "aktiv": {"text": "AKTIV", "bg": "#1F7A46", "fg": "#FFFFFF"},
    "pausiert": {"text": "PAUSIERT", "bg": "#EAF0F6", "fg": "#2E5A82"},
    "abgeschlossen": {"text": "FERTIG", "bg": "#ECEAE1", "fg": "#6E6A5C"},
    # Review-Fund: Konto-Stoerungen (Account Suspended/Unhealthy/Bounce
    # Protect - siehe web.instantly_leser) sind KEIN normales "pausiert" -
    # eigener, lauter Chip in denselben Rot-Tönen wie die "Angehalten"-
    # Fehlerkarten/-boxen (var(--farbe-fehler-hintergrund)/-rand in
    # web/static/stil.css), damit ein Konto-Problem nicht als harmloser,
    # gewollter Zustand durchgeht.
    "kontoproblem": {"text": "KONTO-PROBLEM", "bg": "#F9E9E4", "fg": "#B03320"},
}
# Live-Stand noch nie erfolgreich abgerufen - eigener, neutraler Chip statt
# einen der echten Zustaende zu erraten.
_CHIP_UNBEKANNT = {"text": "LIVE-STAND UNBEKANNT", "bg": "#ECEAE1", "fg": "#6E6A5C"}

# Baustein 1 (20.07.2026): ersetzt den frueheren Hinweis "... Gestartet wird
# dort von Hand — hier nur zum Nachschauen." — das stimmt seit diesem
# Baustein nicht mehr, der Start passiert jetzt HIER im Tool (Knopf "Jetzt
# verschicken" unten), Instantly bleibt nur die sekundaere Option ("Kampagne
# in Instantly öffnen"-Link). Nur waehrend die Kampagne tatsaechlich
# (gewollt) pausiert ist UND unser Tool sie kennt (siehe kd_kann_aktivieren).
PAUSIERT_SATZ = "Diese Kampagne ist in Instantly angelegt, aber noch nicht gestartet."
PAUSIERT_HINWEIS = ('Noch wurde nichts verschickt. Drück unten auf »Jetzt verschicken«, wenn es '
                    "losgehen soll — bis dahin passiert nichts von allein.")

# Eigener, ehrlicher Hinweis fuer "kontoproblem" (Review-Fund) - ersetzt
# PAUSIERT_HINWEIS komplett fuer diesen Zustand: "das ist Absicht" waere
# hier schlicht falsch, das Ruhen ist ein Fehler am Instantly-Konto, keine
# gewollte Pause. Dreiteiliges Muster aus dem Leitfaden (Was ist passiert ·
# was ist NICHT passiert · was du tun kannst), plus der bestehende
# Instantly-Link (immer sichtbar, siehe kampagne_detail.html) fuehrt direkt
# zur Fehlerbehebung dort.
KONTOPROBLEM_HINWEIS = (
    "Das Instantly-Konto hinter dieser Kampagne hat ein Problem — der Versand ruht deshalb. "
    "An den Texten und Empfängern hat sich nichts geändert. Bitte in Instantly nachsehen "
    "(Konto neu verbinden oder Zustellbarkeits-Warnung prüfen).")


def _hole_leser(request: Request):
    """Wie web.routen.freigabe._hole_instantly: app.state.instantly_leser
    gewinnt (Tests faken hier), sonst der GETEILTE InstantlyLeser der App
    (IMPORTANT Review-Fund, siehe web.instantly_leser.geteilten_leser/
    web.app.create_app - EIN Objekt fuer alle Requests, sonst ist der
    60s-Cache nie wirksam). Der Import passiert erst hier, damit Tests ohne
    app.state.instantly_leser nie 'requests' brauchen."""
    leser = getattr(request.app.state, "instantly_leser", None)
    if leser is not None:
        return leser
    from web.instantly_leser import geteilten_leser

    return geteilten_leser(request.app)


def _hole_instantly(request: Request):
    """Wie web.routen.freigabe._hole_instantly (Baustein 1: derselbe
    app.state.instantly-Schreib-Pfad, hier fuer aktiviere_kampagne/
    pausiere_kampagne statt create_campaign/import_leads): app.state.instantly
    gewinnt (Tests faken hier), sonst ein echter InstantlySender mit dem
    Umgebungs-Key. Bewusst NICHT mit web.routen.freigabe geteilt (gleiche
    Duplikation wie _lauf_dir_oder_404/_hole_leser oben in dieser Datei) -
    diese Route ist unabhaengig von der Freigabe-Route lauffaehig."""
    instantly = getattr(request.app.state, "instantly", None)
    if instantly is not None:
        return instantly
    from pipeline.senders.instantly import InstantlySender

    return InstantlySender(os.environ["INSTANTLY_API_KEY"])


def _aktiviert_info(lauf_dir: Path) -> dict | None:
    """Liest aktiviert.json (falls vorhanden) - der Audit-Trail fuer 'wer hat
    diese Kampagne im Tool gestartet, wann' (Baustein 1), gleiches
    Sicherheits-Muster wie abgelehnt.json in web.routen.freigabe
    (_lade_json_sicher statt json.loads direkt: eine kaputte/halb
    geschriebene Datei darf die Detailseite nicht mit einem 500er
    abstuerzen lassen)."""
    return _lade_json_sicher(lauf_dir / "aktiviert.json")


def _lauf_dir_oder_404(daten_dir, slug: str, ts: str) -> Path:
    lauf_dir = Path(daten_dir) / "laeufe" / slug / ts
    laeufe_wurzel = (Path(daten_dir) / "laeufe").resolve()
    try:
        aufgeloest = lauf_dir.resolve()
    except OSError:
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden.")
    if laeufe_wurzel not in aufgeloest.parents or not aufgeloest.is_dir():
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden.")
    return aufgeloest


def _campaign_id_fuer(store: RunStore) -> str | None:
    """versand_komplett (Kampagne UND Leads angelegt) gewinnt vor versand
    (nur die Kampagne angelegt, Lead-Import noch offen/fehlgeschlagen) -
    beide tragen dieselbe campaign_id (siehe pipeline.__main__.
    _versand_ausfuehren), sobald versand_komplett existiert ist es also
    egal, welcher Schritt gelesen wird."""
    if store.step_done("versand_komplett"):
        return store.load_step("versand_komplett")["campaign_id"]
    if store.step_done("versand"):
        return store.load_step("versand")["campaign_id"]
    return None


def _alle_laeufe(daten_dir) -> list[dict]:
    """Iteriert ueber alle Laufordner aller Kunden und baut je Lauf einen
    Rohdatensatz - Grundlage sowohl fuer die Vorbereitungs-Liste als auch
    fuer die Kampagnen-Tabelle (Quelle der Wahrheit: die lokalen
    Laufordner, siehe Plan Task 6)."""
    manager = Laufmanager(daten_dir)
    laeufe_wurzel = Path(daten_dir) / "laeufe"
    ergebnis = []
    if not laeufe_wurzel.is_dir():
        return ergebnis
    for kunden_ordner in sorted(p for p in laeufe_wurzel.iterdir() if p.is_dir()):
        for lauf_dir in sorted(p for p in kunden_ordner.iterdir() if p.is_dir()):
            store = RunStore.resume(lauf_dir)
            stand = manager.status(lauf_dir)
            try:
                kunde_name = _kunde_fuer(daten_dir, lauf_dir).name
            except (OSError, ValueError, KeyError):
                kunde_name = kunden_ordner.name
            pruefung_ok = store.load_step("pruefung_ok") if store.step_done("pruefung_ok") else []
            ergebnis.append({
                "slug": kunden_ordner.name,
                "ts": lauf_dir.name,
                "kunde_name": kunde_name,
                "zustand": stand["zustand"],
                "campaign_id": _campaign_id_fuer(store),
                "freigabe": freigabe_info(store),
                "empf_anzahl": len(pruefung_ok),
                "wartet_seit_text": _wartet_seit_text(lauf_dir),
                "schritt_label": stand["schritt_label"],
                "fehler": stand["fehler"],
            })
    return ergebnis


def _vorbereitung_zeile(eintrag: dict) -> dict:
    """Baut eine Zeile fuer 'IN VORBEREITUNG — DARAUS WERDEN KAMPAGNEN'
    (v4) - nur fuer Auftraege VOR der Uebergabe (kein campaign_id noch,
    oder Uebergabe steckt fest). Verweist auf die Seite, auf der es
    weitergeht (Fortschritt bzw. Pruefen & Freigeben), statt die Aktion
    hier zu duplizieren."""
    titel = (f"E-Mail-Runde für {eintrag['kunde_name']} · {eintrag['empf_anzahl']} Empfänger"
             if eintrag["empf_anzahl"] else f"E-Mail-Runde für {eintrag['kunde_name']}")
    zustand = eintrag["zustand"]
    if zustand == "laeuft":
        return {"titel": titel, "zeile": f"{eintrag['schritt_label']} …",
                "link": f"/auftraege/{eintrag['slug']}/{eintrag['ts']}", "link_text": "Zusehen"}
    if zustand == "angehalten":
        fehler = eintrag["fehler"] or {}
        zeile = f"Angehalten: {fehler.get('was', '')} {fehler.get('nicht', '')}".strip()
        return {"titel": titel, "zeile": zeile,
                "link": f"/auftraege/{eintrag['slug']}/{eintrag['ts']}", "link_text": "Fortsetzen"}
    if zustand == "wartet_auf_freigabe":
        return {"titel": titel, "zeile": eintrag["wartet_seit_text"],
                "link": f"/pruefen/{eintrag['slug']}/{eintrag['ts']}", "link_text": "Jetzt lesen"}
    # zustand == "freigegeben" ohne campaign_id: Sonderfall, bei dem die
    # Kampagne in Instantly noch nicht (vollstaendig) angelegt werden
    # konnte (siehe _campaign_id_fuer) - Ansehen fuehrt zu "Erneut senden".
    von = eintrag["freigabe"]["von"] or "unbekannt"
    zeile = (f"Freigegeben von {von} am {eintrag['freigabe']['am']} — "
             f"Übergabe an Instantly noch nicht abgeschlossen.")
    return {"titel": titel, "zeile": zeile,
            "link": f"/pruefen/{eintrag['slug']}/{eintrag['ts']}", "link_text": "Ansehen"}


def _chip_fuer(status: str | None) -> dict:
    return _CHIP.get(status, _CHIP_UNBEKANNT)


def _live_stand_hinweis(staende: list[dict]) -> str | None:
    """Baut die ehrliche Zeile "Live-Stand gerade nicht erreichbar — Stand
    von HH:MM" (Plan Task 6), sobald mindestens eine Kampagne gerade nicht
    erreichbar ist - mit dem Zeitpunkt des letzten erfolgreichen Abrufs,
    falls es einen gibt, sonst ohne Zeitangabe (noch nie erfolgreich
    abgerufen)."""
    unerreichbar = [s for s in staende if not s.get("erreichbar")]
    if not unerreichbar:
        return None
    stand_zeiten = [s["stand"] for s in unerreichbar if s.get("stand") is not None]
    if stand_zeiten:
        letzter = max(stand_zeiten).strftime("%H:%M")
        return f"Live-Stand gerade nicht erreichbar — Stand von {letzter}."
    return "Live-Stand gerade nicht erreichbar — noch kein Stand abgerufen."


def _stand_fuer(request: Request, mit_kampagne: list[dict]) -> dict[str, dict]:
    """Der EINE Instantly-Abruf (InstantlyLeser.kampagnen_stand, 60s-Cache)
    fuer alle uebergebenen Laeufe mit campaign_id. Bewusst von der
    Zeilen-Aufbereitung getrennt (siehe _kampagnen_zeilen_aus_stand), damit
    andere Ansichten mit demselben Bedarf (Task 7, web.routen.dashboard)
    sich EIN Ergebnis teilen koennen statt je Kachel/Abschnitt erneut
    abzufragen - bei kaltem Cache + ausgefallener API wuerde ein zweiter
    Abruf 2x drei sequentielle GETs je Kampagne bedeuten (siehe
    InstantlyLeser._hole_frisch) und die Seite unnoetig lange blockieren."""
    if not mit_kampagne:
        return {}
    leser = _hole_leser(request)
    return leser.kampagnen_stand([l["campaign_id"] for l in mit_kampagne])


def _kampagnen_zeilen_aus_stand(mit_kampagne: list[dict], stand_by_id: dict[str, dict]) -> list[dict]:
    """Reine Aufbereitung (kein Netzwerk-Zugriff) - baut aus einem bereits
    abgerufenen stand_by_id (siehe _stand_fuer) die Anzeige-Zeilen."""
    zeilen = []
    for eintrag in mit_kampagne:
        stand = stand_by_id.get(eintrag["campaign_id"], {})
        chip = _chip_fuer(stand.get("status"))
        name = stand.get("name") or f"[TEST] {eintrag['kunde_name']}"
        versendet = stand.get("versendet")
        zeilen.append({
            "slug": eintrag["slug"], "ts": eintrag["ts"],
            "name": name, "kunde": eintrag["kunde_name"],
            "chip_text": chip["text"], "chip_bg": chip["bg"], "chip_fg": chip["fg"],
            "status": stand.get("status"),
            "gesamt": eintrag["empf_anzahl"],
            "versendet": versendet,
            "verschickt": versendet if versendet is not None else "—",
            "geoeffnet": stand.get("geoeffnet"),
            "antworten": stand.get("antworten"),
            "unzustellbar": stand.get("unzustellbar"),
            "freigegeben_am": format_deutsches_datum(eintrag["freigabe"]["am"]) or "—",
        })
    return zeilen


def _summe_oder_unbekannt(zeilen: list[dict], feld: str):
    """Addiert nur vollstaendig bekannte Werte.

    Ein fehlender Instantly-Wert ist keine Null. Damit keine scheinbar
    genauen Kennzahlen entstehen, bleibt die ganze Summe unbekannt, sobald
    ein Summand fehlt.
    """
    werte = [zeile.get(feld) for zeile in zeilen]
    if not werte or any(wert is None for wert in werte):
        return None
    return sum(werte)


def _warteschlange(gesamt_empfaenger: int, schritt_anzahl: int, stand: dict) -> dict:
    """Bereitet nur die von Instantly belegten Gruppen der Warteschlange vor."""
    moeglich = gesamt_empfaenger * schritt_anzahl
    versendet = stand.get("versendet")
    unzustellbar = stand.get("unzustellbar")
    if versendet is None or unzustellbar is None:
        return {"gesamt": moeglich, "versendet": versendet,
                "unzustellbar": unzustellbar, "ungetrennt": None}
    gesamt = max(moeglich, versendet + unzustellbar)
    return {"gesamt": gesamt, "versendet": versendet,
            "unzustellbar": unzustellbar,
            "ungetrennt": max(gesamt - versendet - unzustellbar, 0)}


_WOCHENTAGE = ("So", "Mo", "Di", "Mi", "Do", "Fr", "Sa")


def _tage_text(tage: dict) -> str:
    aktive_tage = [nummer for nummer, name in enumerate(_WOCHENTAGE)
                   if tage.get(str(nummer), tage.get(nummer, False))]
    bereiche = []
    start = ende = None
    for nummer in aktive_tage:
        if start is None:
            start = ende = nummer
        elif nummer == ende + 1:
            ende = nummer
        else:
            bereiche.append(_tage_bereich_text(start, ende))
            start = ende = nummer
    if start is not None:
        bereiche.append(_tage_bereich_text(start, ende))
    return ", ".join(bereiche) or "—"


def _tage_bereich_text(start: int, ende: int) -> str:
    return _WOCHENTAGE[start] if start == ende else f"{_WOCHENTAGE[start]}–{_WOCHENTAGE[ende]}"


def _sendefenster_anzeigen(sendefenster: list[dict], jetzt: datetime) -> list[dict]:
    """Formatiert Instantly-Sendefenster, ohne fehlende Angaben zu erfinden."""
    ergebnis = []
    for fenster in sendefenster or []:
        tage = fenster.get("tage") if isinstance(fenster.get("tage"), dict) else {}
        tage_text = _tage_text(tage)
        von, bis, zeitzone = fenster.get("von"), fenster.get("bis"), fenster.get("zeitzone")
        if not all(isinstance(wert, str) and wert for wert in (von, bis, zeitzone)):
            ergebnis.append({
                "tage_text": tage_text,
                "zeit_text": "Sendefenster nicht vollständig hinterlegt",
                "zeitzone": zeitzone or "—",
                "ist_jetzt": None,
            })
            continue
        try:
            von_zeit, bis_zeit = time.fromisoformat(von), time.fromisoformat(bis)
            if jetzt.tzinfo is None:
                raise ValueError("Zeitpunkt braucht eine Zeitzone")
            lokale_zeit = jetzt.astimezone(ZoneInfo(zeitzone))
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            ergebnis.append({
                "tage_text": tage_text,
                "zeit_text": "Sendefenster nicht vollständig hinterlegt",
                "zeitzone": zeitzone,
                "ist_jetzt": None,
            })
            continue
        heute_aktiv = lokale_zeit.weekday() + 1 if lokale_zeit.weekday() < 6 else 0
        ist_im_zeitraum = (von_zeit <= lokale_zeit.time() <= bis_zeit if von_zeit <= bis_zeit
                           else lokale_zeit.time() >= von_zeit or lokale_zeit.time() <= bis_zeit)
        ergebnis.append({
            "tage_text": tage_text,
            "zeit_text": f"{von}–{bis}",
            "zeitzone": zeitzone,
            "ist_jetzt": heute_aktiv in [nummer for nummer in range(7)
                                         if tage.get(str(nummer), tage.get(nummer, False))]
                          and ist_im_zeitraum,
        })
    return ergebnis


def _tageslimit(stand: dict, postfach_antwort: dict) -> dict:
    """Ermittelt das Limit ausschliesslich aus den Absender-Postfaechern."""
    heute = stand.get("heute_versendet")
    if not postfach_antwort.get("erreichbar"):
        return {"heute": heute, "limit": None}
    postfaecher = postfach_antwort.get("postfaecher")
    absender = stand.get("absender")
    if not isinstance(postfaecher, list) or not isinstance(absender, list) or not absender:
        return {"heute": heute, "limit": None}
    nach_email = {
        postfach.get("email", "").strip().casefold(): postfach
        for postfach in postfaecher if isinstance(postfach, dict)
    }
    limits = []
    bekannte_absender = set()
    for absender_email in absender:
        if not isinstance(absender_email, str):
            limits.append(None)
            continue
        email = absender_email.strip().casefold()
        if email in bekannte_absender:
            continue
        bekannte_absender.add(email)
        postfach = nach_email.get(email)
        limits.append(postfach.get("daily_limit") if postfach is not None else None)
    return {"heute": heute, "limit": _summe_oder_unbekannt(
        [{"limit": limit} for limit in limits], "limit")}


def _anzeige_zeitpunkt(request: Request) -> datetime:
    """Liefert eine zeitzonenbewusste Uhr, die Tests gezielt setzen koennen."""
    uhr = getattr(request.app.state, "jetzt", None)
    return uhr() if callable(uhr) else datetime.now(timezone.utc)


# Routen ------------------------------------------------------------------

@router.get("/kampagnen")
# Bewusst KEIN `async def` - IMPORTANT Review-Fund: _stand_fuer ruft
# synchron InstantlyLeser.kampagnen_stand auf (blockierende HTTP-Aufrufe bei
# kaltem Cache, siehe Modul-Docstring). Als Koroutine wuerde das den
# Event-Loop fuer ALLE gleichzeitigen Nutzer blockieren (gleicher Grund wie
# web/routen/auftraege.py). Als normale `def`-Funktion fuehrt FastAPI die
# Route stattdessen in einem Threadpool aus.
def kampagnen_liste(request: Request, suche: str = "", status: str = "alle"):
    daten_dir = request.app.state.daten_dir
    laeufe = _alle_laeufe(daten_dir)

    vorbereitung = [
        _vorbereitung_zeile(l) for l in laeufe
        if l["campaign_id"] is None and l["zustand"] in
        ("laeuft", "angehalten", "wartet_auf_freigabe", "freigegeben")
    ]
    mit_kampagne = [l for l in laeufe if l["campaign_id"]]
    stand_by_id = _stand_fuer(request, mit_kampagne)
    kampagnen_zeilen = _kampagnen_zeilen_aus_stand(mit_kampagne, stand_by_id)
    live_stand_hinweis = _live_stand_hinweis(list(stand_by_id.values()))
    kennzahlen = {
        "kampagnen": len(kampagnen_zeilen),
        "aktiv": sum(zeile["status"] == "aktiv" for zeile in kampagnen_zeilen),
        "empfaenger": sum(zeile["gesamt"] for zeile in kampagnen_zeilen),
        "geoeffnet": _summe_oder_unbekannt(kampagnen_zeilen, "geoeffnet"),
        "versendet": _summe_oder_unbekannt(kampagnen_zeilen, "versendet"),
        "antworten": _summe_oder_unbekannt(kampagnen_zeilen, "antworten"),
        "fehlgeschlagen": None,
        "unzustellbar": _summe_oder_unbekannt(kampagnen_zeilen, "unzustellbar"),
    }
    suchtext = suche.strip().casefold()
    if suchtext:
        kampagnen_zeilen = [zeile for zeile in kampagnen_zeilen if suchtext in
                            f"{zeile['name']} {zeile['kunde']}".casefold()]
    if status != "alle":
        kampagnen_zeilen = [zeile for zeile in kampagnen_zeilen if zeile["status"] == status]

    return request.app.state.templates.TemplateResponse(
        request, "kampagnen_liste.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "vorbereitung": vorbereitung,
            "kampagnen": kampagnen_zeilen,
            "kennzahlen": kennzahlen,
            "suche": suche,
            "status_filter": status,
            "live_stand_hinweis": live_stand_hinweis,
        },
    )


def _detail_kontext(request: Request, slug: str, ts: str, *, aktion_fehler: str | None = None) -> dict:
    """Baut den kompletten Anzeige-Kontext fuer kampagne_detail.html - eigene
    Funktion (statt Code direkt in der GET-Route), damit die POST-Routen
    unten (aktivieren/pausieren) bei einem Instantly-Fehler dieselbe Ansicht
    MIT einer zusaetzlichen Fehlerzeile zurueckgeben koennen, ohne die
    komplette Detail-Logik zu duplizieren (gleiches Muster wie
    web.routen.freigabe._lese_kontext + _versand_fehlertext)."""
    daten_dir = request.app.state.daten_dir
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    store = RunStore.resume(lauf_dir)

    campaign_id = _campaign_id_fuer(store)
    if campaign_id is None:
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden.")

    try:
        kunde = _kunde_fuer(daten_dir, lauf_dir)
        kunde_name, follow_up_tage = kunde.name, kunde.follow_up_tage
    except (OSError, ValueError, KeyError):
        kunde_name, follow_up_tage = slug, []
    tage = follow_up_tage or [0, 0]
    tag_1, tag_2 = tage[0], tage[1] if len(tage) > 1 else tage[0]

    pruefung_ok = store.load_step("pruefung_ok") if store.step_done("pruefung_ok") else []
    gesamt = len(pruefung_ok)

    leser = _hole_leser(request)
    stand = leser.kampagnen_stand([campaign_id])[campaign_id]
    chip = _chip_fuer(stand.get("status"))
    name = stand.get("name") or f"[TEST] {kunde_name}"

    schritt_labels = [
        "Erste E-Mail (geht sofort raus)",
        f"Nachfass-Mail 1 (nach {tag_1} Tagen)",
        f"Nachfass-Mail 2 (nach {tag_2} Tagen)",
    ]
    schritte_by_nr = {s["schritt"]: s for s in stand.get("schritte", [])}
    kd_schritte = []
    for i, label in enumerate(schritt_labels, start=1):
        schritt = schritte_by_nr.get(i, {})
        versendet = schritt.get("versendet")
        text = f"{versendet} von {gesamt} versendet" if versendet is not None else "—"
        balken = round(100 * versendet / gesamt) if versendet is not None and gesamt else 0
        kd_schritte.append({
            "label": label, "text": text, "balken": f"{balken}%",
            "geoeffnet": schritt.get("geoeffnet"),
        })

    freigabe = freigabe_info(store)
    ist_pausiert = stand.get("erreichbar") and stand.get("status") == "pausiert"
    ist_aktiv = stand.get("erreichbar") and stand.get("status") == "aktiv"
    # Review-Fund: "kontoproblem" bekommt seinen EIGENEN Hinweis statt
    # PAUSIERT_HINWEIS - die beiden Zustaende schliessen sich gegenseitig
    # aus (siehe _CHIP/_STATUS_TEXT), nie beide gleichzeitig gesetzt.
    ist_kontoproblem = stand.get("erreichbar") and stand.get("status") == "kontoproblem"

    # Baustein 1: "bekannt" heisst versand_komplett (Kampagne UND Leads
    # vollstaendig angelegt) - siehe _campaign_id_fuer-Docstring. Nur
    # "versand" (Lead-Import (noch) nicht durch) zeigt zwar noch die
    # Detailseite (unveraendertes Verhalten), aber KEINEN
    # Scharf-schalten/Pausieren-Knopf: eine unvollstaendig angelegte
    # Kampagne im Tool zu starten waere ein Versand ohne (alle) Empfaenger.
    bekannt = store.step_done("versand_komplett")
    kd_kann_aktivieren = bekannt and ist_pausiert
    kd_kann_pausieren = bekannt and ist_aktiv

    aktiviert = _aktiviert_info(lauf_dir)

    live_stand_hinweis = _live_stand_hinweis([stand])
    postfach_antwort = (leser.postfaecher() if hasattr(leser, "postfaecher") else
                         {"erreichbar": False, "postfaecher": []})
    kd_warteschlange = _warteschlange(gesamt, len(schritt_labels), stand)
    anzeige_zeitpunkt = _anzeige_zeitpunkt(request)

    return {
        "nutzer": auth.aktueller_nutzer(request),
        "nav": nav_kontext(request),
        "slug": slug, "ts": ts,
        "kd_name": name, "kd_kunde": kunde_name,
        "chip_text": chip["text"], "chip_bg": chip["bg"], "chip_fg": chip["fg"],
        "kd_satz": PAUSIERT_SATZ if kd_kann_aktivieren else "",
        "kd_pausiert_hinweis": PAUSIERT_HINWEIS if kd_kann_aktivieren else "",
        "kd_kontoproblem_hinweis": KONTOPROBLEM_HINWEIS if ist_kontoproblem else "",
        "kd_von": freigabe["von"] or "unbekannt",
        "kd_am": format_deutsches_datum(freigabe["am"]) or "—",
        "kd_gesamt": gesamt,
        "kd_kennzahlen": {
            "empfaenger": stand.get("empfaenger"),
            "moeglich": gesamt * len(schritt_labels),
            "versendet": stand.get("versendet"),
            "geoeffnet": stand.get("geoeffnet"),
            "antworten": stand.get("antworten"),
            "fehlgeschlagen": None,
            "unzustellbar": stand.get("unzustellbar"),
        },
        "kd_warteschlange": kd_warteschlange,
        "kd_schritte": kd_schritte,
        "kd_sendefenster": _sendefenster_anzeigen(
            stand.get("sendefenster") or [], anzeige_zeitpunkt),
        "kd_tageslimit": _tageslimit(stand, postfach_antwort),
        "kd_antworten": stand.get("antworten") if stand.get("antworten") is not None else "—",
        "campaign_id": campaign_id,
        "live_stand_hinweis": live_stand_hinweis,
        "kd_kann_aktivieren": kd_kann_aktivieren,
        "kd_kann_pausieren": kd_kann_pausieren,
        "kd_aktivieren_bestaetigung": AKTIVIEREN_BESTAETIGUNG,
        "kd_pausieren_bestaetigung": PAUSIEREN_BESTAETIGUNG,
        "kd_gestartet_von": aktiviert["von"] if aktiviert else None,
        "kd_gestartet_am": aktiviert["am"] if aktiviert else None,
        "kd_aktion_fehler": aktion_fehler,
    }


@router.get("/kampagnen/{slug}/{ts}")
# Bewusst KEIN `async def` - gleicher Grund wie kampagnen_liste oben:
# _hole_leser(request).kampagnen_stand(...) ist ein synchroner, blockierender
# HTTP-Aufruf (ueber _detail_kontext).
def kampagne_detail(request: Request, slug: str, ts: str):
    kontext = _detail_kontext(request, slug, ts)
    return request.app.state.templates.TemplateResponse(request, "kampagne_detail.html", kontext)


def _kampagne_lauf_oder_404(daten_dir, slug: str, ts: str) -> tuple[Path, RunStore, str]:
    """Gemeinsame Vorpruefung fuer die POST-Routen unten (aktivieren/
    pausieren): 404, wenn der Laufordner nicht existiert ODER die Kampagne
    fuer unser Tool nicht 'bekannt' ist (siehe kampagne_detail-Kommentar zu
    versand_komplett) - ohne vollstaendigen Lead-Import darf hier nichts
    scharf geschaltet/pausiert werden."""
    lauf_dir = _lauf_dir_oder_404(daten_dir, slug, ts)
    store = RunStore.resume(lauf_dir)
    if not store.step_done("versand_komplett"):
        raise HTTPException(status_code=404, detail="Kampagne nicht gefunden.")
    campaign_id = store.load_step("versand_komplett")["campaign_id"]
    return lauf_dir, store, campaign_id


@router.post("/kampagnen/{slug}/{ts}/aktivieren")
# Bewusst KEIN `async def` - blockierender HTTP-Aufruf an Instantly (gleicher
# Grund wie web.routen.freigabe.freigabe_absenden).
def kampagne_aktivieren(request: Request, slug: str, ts: str, bestaetigt: str = Form("")):
    daten_dir = request.app.state.daten_dir
    lauf_dir, _store, campaign_id = _kampagne_lauf_oder_404(daten_dir, slug, ts)

    # Der Knopf im Template ist immer hinter der Bestaetigungs-Geste
    # versteckt (details/summary + eigener "Ja, ..."-Knopf, siehe
    # kampagne_detail.html) - ein POST ohne "bestaetigt=ja" kommt also nur
    # bei einem manipulierten/direkten Aufruf vor. Sicherheitsnetz statt
    # Fehlermeldung: einfach zurueck zur Ansicht, KEIN Instantly-Aufruf.
    if bestaetigt != "ja":
        return RedirectResponse(f"/kampagnen/{slug}/{ts}", status_code=303)

    sender = _hole_instantly(request)
    try:
        sender.aktiviere_kampagne(campaign_id)
    except (RuntimeError, requests.RequestException):
        kontext = _detail_kontext(request, slug, ts, aktion_fehler=_AKTION_FEHLERTEXT)
        return request.app.state.templates.TemplateResponse(
            request, "kampagne_detail.html", kontext, status_code=200)

    (lauf_dir / "aktiviert.json").write_text(json.dumps({
        "von": auth.aktueller_nutzer(request),
        "am": datetime.now().strftime("%d.%m.%Y, %H:%M"),
    }, ensure_ascii=False), encoding="utf-8")

    return RedirectResponse(f"/kampagnen/{slug}/{ts}", status_code=303)


@router.post("/kampagnen/{slug}/{ts}/pausieren")
# Bewusst KEIN `async def` - siehe kampagne_aktivieren.
def kampagne_pausieren(request: Request, slug: str, ts: str, bestaetigt: str = Form("")):
    daten_dir = request.app.state.daten_dir
    _lauf_dir, _store, campaign_id = _kampagne_lauf_oder_404(daten_dir, slug, ts)

    if bestaetigt != "ja":
        return RedirectResponse(f"/kampagnen/{slug}/{ts}", status_code=303)

    sender = _hole_instantly(request)
    try:
        sender.pausiere_kampagne(campaign_id)
    except (RuntimeError, requests.RequestException):
        kontext = _detail_kontext(request, slug, ts, aktion_fehler=_AKTION_FEHLERTEXT)
        return request.app.state.templates.TemplateResponse(
            request, "kampagne_detail.html", kontext, status_code=200)

    return RedirectResponse(f"/kampagnen/{slug}/{ts}", status_code=303)

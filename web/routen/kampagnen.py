"""Route fuer den Kampagnen-Bereich (Task 6): Liste aller Kampagnen (mit
Live-Stand aus Instantly) plus die Auftraege, aus denen noch Kampagnen
werden ("in Vorbereitung"), und die Detail-Ansicht einer einzelnen
Kampagne. Instantly ist ueber request.app.state.instantly_leser fakebar -
gleiches Muster wie request.app.state.instantly in web.routen.freigabe fuer
den Schreib-Pfad. Diese Route liest NUR (web.instantly_leser.InstantlyLeser,
nur GET) - sie legt nie eine Kampagne an und aktiviert nie eine."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from pipeline.approval import freigabe_info
from pipeline.config import load_kunde
from pipeline.run_store import RunStore
from web import auth
from web.laufmanager import Laufmanager, wartet_seit_text as _wartet_seit_text
from web.nav import nav_kontext

router = APIRouter()

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

# Woertlich aus dem Leitfaden/v4 (kdSatz) - nur waehrend die Kampagne
# tatsaechlich (gewollt) pausiert ist.
PAUSIERT_SATZ = ("Diese Kampagne liegt pausiert in Instantly. Gestartet wird dort von Hand "
                 "— hier nur zum Nachschauen.")
PAUSIERT_HINWEIS = ("Noch wurde nichts versendet. Zum Starten die Kampagne in Instantly öffnen "
                    "und dort von Hand starten — das ist Absicht, damit nichts aus Versehen "
                    "rausgeht.")

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
    gewinnt (Tests faken hier), sonst ein echter InstantlyLeser mit dem
    Umgebungs-Key - der Import passiert erst hier, damit Tests nie
    'requests' brauchen."""
    leser = getattr(request.app.state, "instantly_leser", None)
    if leser is not None:
        return leser
    from web.instantly_leser import InstantlyLeser

    return InstantlyLeser(os.environ["INSTANTLY_API_KEY"])


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


def _kunde_fuer(daten_dir, lauf_dir: Path):
    store = RunStore.resume(lauf_dir)
    pfad = Path(store.load_step("kunde_pfad")["pfad"])
    if not pfad.is_absolute():
        pfad = Path(daten_dir) / pfad
    return load_kunde(pfad)


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
    titel = (f"{eintrag['empf_anzahl']} Anschreiben für {eintrag['kunde_name']}"
             if eintrag["empf_anzahl"] else f"Anschreiben für {eintrag['kunde_name']}")
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
                "link": f"/pruefen/{eintrag['slug']}/{eintrag['ts']}", "link_text": "Jetzt prüfen"}
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
            "gesamt": eintrag["empf_anzahl"],
            "verschickt": versendet if versendet is not None else "—",
            "freigegeben_am": eintrag["freigabe"]["am"] or "—",
        })
    return zeilen


# Routen ------------------------------------------------------------------

@router.get("/kampagnen")
async def kampagnen_liste(request: Request):
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

    return request.app.state.templates.TemplateResponse(
        request, "kampagnen_liste.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "vorbereitung": vorbereitung,
            "kampagnen": kampagnen_zeilen,
            "live_stand_hinweis": live_stand_hinweis,
        },
    )


@router.get("/kampagnen/{slug}/{ts}")
async def kampagne_detail(request: Request, slug: str, ts: str):
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
        "Anschreiben (geht sofort raus)",
        f"Nachfass-Mail 1 (nach {tag_1} Tagen)",
        f"Nachfass-Mail 2 (nach {tag_2} Tagen)",
    ]
    schritte_by_nr = {s["schritt"]: s["versendet"] for s in stand.get("schritte", [])}
    kd_schritte = []
    for i, label in enumerate(schritt_labels, start=1):
        versendet = schritte_by_nr.get(i)
        text = f"{versendet} von {gesamt} versendet" if versendet is not None else "—"
        balken = round(100 * versendet / gesamt) if versendet is not None and gesamt else 0
        kd_schritte.append({"label": label, "text": text, "balken": f"{balken}%"})

    freigabe = freigabe_info(store)
    ist_pausiert = stand.get("erreichbar") and stand.get("status") == "pausiert"
    # Review-Fund: "kontoproblem" bekommt seinen EIGENEN Hinweis statt
    # PAUSIERT_HINWEIS - die beiden Zustaende schliessen sich gegenseitig
    # aus (siehe _CHIP/_STATUS_TEXT), nie beide gleichzeitig gesetzt.
    ist_kontoproblem = stand.get("erreichbar") and stand.get("status") == "kontoproblem"

    live_stand_hinweis = _live_stand_hinweis([stand])

    return request.app.state.templates.TemplateResponse(
        request, "kampagne_detail.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "slug": slug, "ts": ts,
            "kd_name": name, "kd_kunde": kunde_name,
            "chip_text": chip["text"], "chip_bg": chip["bg"], "chip_fg": chip["fg"],
            "kd_satz": PAUSIERT_SATZ if ist_pausiert else "",
            "kd_pausiert_hinweis": PAUSIERT_HINWEIS if ist_pausiert else "",
            "kd_kontoproblem_hinweis": KONTOPROBLEM_HINWEIS if ist_kontoproblem else "",
            "kd_von": freigabe["von"] or "unbekannt", "kd_am": freigabe["am"] or "—",
            "kd_gesamt": gesamt,
            "kd_schritte": kd_schritte,
            "kd_antworten": stand.get("antworten") if stand.get("antworten") is not None else "—",
            "campaign_id": campaign_id,
            "live_stand_hinweis": live_stand_hinweis,
        },
    )

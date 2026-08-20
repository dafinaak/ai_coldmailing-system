"""Firmen fuer einen Umkreis frisch sammeln.

Die Bruecke zwischen dem, was das Formular fragt ("Hannover, 25 km,
Webdesigner"), und den Quellen-Bausteinen, die es schon gibt: Google Maps
ueber Apify, Gelbe Seiten ueber Apify, OpenStreetMap ueber Overpass -
zusammengefuehrt von pipeline.listen_fusion.

Warum es das braucht (17.08.2026): Der gesammelte Bestand deckt nur die
Postleitregionen 30 und 31 ab, also den Raum Hannover. Fuer jede andere
Stadt lieferte Schritt 4 des Formulars schlicht null Firmen - das Werkzeug
konnte nur eine einzige Region bedienen.

Kosten: Die beiden Apify-Aktoren rechnen pro Lauf ab. Die Sammlung vom
29.07.2026 kostete rund sieben Dollar fuer zwei Postleitregionen. Deshalb
sammelt niemand automatisch - der Mensch waehlt es in Schritt 3
ausdruecklich (siehe web.routen.assistent).

Das Ergebnis wird als eigener Ordner unter laeufe/leadquellen/ abgelegt.
Aeltere Sammlungen bleiben unangetastet; zusammengefuehrt wird erst beim
Lesen (web.routen.assistent._firmen_bestand).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from pipeline.listen_fusion import fusionieren
from pipeline.plz_geo import entfernung_km, plz_tabelle
from pipeline.service_categories import expand_for_search

# Ein Kreis wird als Vieleck angenaehert - der Maps-Actor will ein
# Polygon. 24 Ecken sind auf Stadtgroesse vom Kreis nicht zu unterscheiden.
_ECKEN = 24
# Grad pro Kilometer in Nord-Sued-Richtung (die Erde als Kugel gerechnet).
_GRAD_PRO_KM = 1 / 111.32


def plz_im_umkreis(ort: str, radius_km: float, tabelle=None) -> list[str]:
    """Alle Postleitzahlen, deren Mittelpunkt im Umkreis liegt."""
    tabelle = tabelle if tabelle is not None else plz_tabelle()
    zentrum = _zentrum(ort, tabelle)
    if zentrum is None:
        raise ValueError(
            f"Den Ort {ort!r} kennen wir nicht - bitte einen Ortsnamen oder "
            f"eine Postleitzahl angeben.")
    treffer = []
    for plz, eintrag in tabelle.items():
        if entfernung_km(zentrum, (eintrag["lat"], eintrag["lon"])) <= radius_km:
            treffer.append(plz)
    return sorted(treffer)


def _zentrum(ort: str, tabelle: dict):
    from pipeline.plz_geo import _vergleichbar

    eintrag = tabelle.get(str(ort).strip())
    if eintrag:
        return (eintrag["lat"], eintrag["lon"])
    gesucht = _vergleichbar(ort)
    passende = [e for e in tabelle.values() if _vergleichbar(e["ort"]) == gesucht]
    if not passende:
        return None
    return (sum(e["lat"] for e in passende) / len(passende),
            sum(e["lon"] for e in passende) / len(passende))


def kreis_geojson(zentrum: tuple, radius_km: float) -> dict:
    """Umkreis als GeoJSON-Polygon fuer den Maps-Actor."""
    lat, lon = zentrum
    # Ein Laengengrad wird zu den Polen hin kuerzer - sonst waere der Kreis
    # in Norddeutschland ein liegendes Ei.
    lon_faktor = max(math.cos(math.radians(lat)), 0.01)
    punkte = []
    for i in range(_ECKEN):
        winkel = 2 * math.pi * i / _ECKEN
        punkte.append([
            round(lon + radius_km * _GRAD_PRO_KM / lon_faktor * math.cos(winkel), 6),
            round(lat + radius_km * _GRAD_PRO_KM * math.sin(winkel), 6),
        ])
    punkte.append(punkte[0])       # GeoJSON-Ringe sind geschlossen
    return {"type": "Polygon", "coordinates": [punkte]}


def bounding_box(zentrum: tuple, radius_km: float) -> tuple:
    """(sued, west, nord, ost) - so will Overpass es."""
    lat, lon = zentrum
    lon_faktor = max(math.cos(math.radians(lat)), 0.01)
    d_lat = radius_km * _GRAD_PRO_KM
    d_lon = radius_km * _GRAD_PRO_KM / lon_faktor
    return (round(lat - d_lat, 6), round(lon - d_lon, 6),
            round(lat + d_lat, 6), round(lon + d_lon, 6))


def sammeln(ort: str, radius_km: float, dienste, *, maps=None,
            gelbe_seiten=None, overpass=None, limit_pro_suche: int = 200,
            tabelle=None) -> tuple[list, dict]:
    """Firmen im Umkreis sammeln und zu EINER Liste zusammenfuehren.

    Quellen sind einzeln uebergebbar (Tests, und damit ein Ausfall einer
    Quelle nicht die ganze Sammlung kostet). Faellt eine Quelle aus, wird
    das im Bericht vermerkt und mit den uebrigen weitergemacht - eine
    halbe Sammlung ist mehr wert als gar keine, und bezahlt ist sie ohnehin.
    """
    if not dienste:
        raise ValueError("Ohne Suchbegriffe kann nicht gesammelt werden.")
    # Eine Leistungs-Familie wird zur kurzen, kuratierten Suchliste -
    # kurz mit Absicht: jeder Suchbegriff crawlt bis zu seinem eigenen
    # Limit und wird bezahlt (pipeline.service_categories).
    dienste = expand_for_search(dienste)
    tabelle = tabelle if tabelle is not None else plz_tabelle()
    zentrum = _zentrum(ort, tabelle)
    if zentrum is None:
        raise ValueError(
            f"Den Ort {ort!r} kennen wir nicht - bitte einen Ortsnamen oder "
            f"eine Postleitzahl angeben.")

    plz_liste = plz_im_umkreis(ort, radius_km, tabelle)
    # Die Fusion filtert ueber PLZ-PRAEFIXE, nicht ueber einzelne
    # Postleitzahlen. Aus den gefundenen PLZ die Praefixe ableiten, sonst
    # wuerde die Fusion alles als "fremde PLZ" wegwerfen.
    praefixe = sorted({p[:3] for p in plz_liste}) or [""]

    listen, fehler = _quellen_sammeln(
        dienste, zentrum, radius_km, praefixe, maps=maps,
        gelbe_seiten=gelbe_seiten, overpass=overpass,
        limit_pro_suche=limit_pro_suche, gs_ort=ort)

    firmen, bericht = fusionieren(listen, praefixe)
    bericht.update({"ort": ort, "radius_km": radius_km,
                    "dienste": list(dienste), "plz_im_umkreis": len(plz_liste),
                    "plz_praefixe": praefixe, "quellen_fehler": fehler})
    return firmen, bericht


def _quellen_sammeln(dienste, zentrum, radius_km, praefixe, *, maps=None,
                     gelbe_seiten=None, overpass=None, limit_pro_suche=200,
                     gs_ort="", gs_seiten=1) -> tuple[list, dict]:
    """Ein Gebiet bei allen Quellen abfragen - der gemeinsame Kern von
    sammeln() und sammeln_bis_ziel(). Faellt eine Quelle aus, wird das
    vermerkt und mit den uebrigen weitergemacht."""
    listen, fehler = [], {}

    if maps is not None:
        try:
            listen.append(maps.search_gebiet(
                list(dienste), kreis_geojson(zentrum, radius_km),
                limit_pro_suche))
        except Exception as f:      # noqa: BLE001
            fehler["maps"] = str(f)

    if gelbe_seiten is not None and gs_ort:
        gefunden = []
        for begriff in dienste:
            try:
                gefunden += gelbe_seiten.search(begriff, gs_ort, gs_seiten)
            except Exception as f:      # noqa: BLE001
                fehler.setdefault("gelbe_seiten", str(f))
        listen.append(gefunden)

    if overpass is not None:
        try:
            listen.append(overpass.search(
                tuple(praefixe), bounding_box(zentrum, radius_km)))
        except Exception as f:      # noqa: BLE001
            fehler["overpass"] = str(f)

    return listen, fehler


def regionen_deutschland(tabelle=None) -> list:
    """Die zweistelligen Postleitregionen Deutschlands, dichteste zuerst.

    Fuer die deutschlandweite Sammlung: ein Gebiet je Region, Mittelpunkt
    und Radius aus den PLZ-Koordinaten gerechnet. "Dichteste zuerst"
    (meiste Postleitzahlen = staedtischste Region), damit ein kleines
    Ziel wie 100 Firmen schon nach ein, zwei Regionen erreicht ist und
    nicht erst das halbe Land abgesucht werden muss.
    """
    tabelle = tabelle if tabelle is not None else plz_tabelle()
    gruppen: dict = {}
    for plz, eintrag in tabelle.items():
        gruppen.setdefault(str(plz)[:2], []).append(eintrag)
    regionen = []
    for praefix, eintraege in gruppen.items():
        lat = sum(e["lat"] for e in eintraege) / len(eintraege)
        lon = sum(e["lon"] for e in eintraege) / len(eintraege)
        radius = max(entfernung_km((lat, lon), (e["lat"], e["lon"]))
                     for e in eintraege)
        orte: dict = {}
        for e in eintraege:
            orte[e["ort"]] = orte.get(e["ort"], 0) + 1
        regionen.append({
            "praefix": praefix,
            "zentrum": (lat, lon),
            # Etwas Rand, aber gedeckelt - die PLZ-Feinfilterung der
            # Fusion braucht keinen praezisen Kreis, nur Abdeckung.
            "radius_km": min(radius + 5, 120.0),
            "label": max(orte, key=orte.get),
            "plz_anzahl": len(eintraege),
        })
    regionen.sort(key=lambda r: (-r["plz_anzahl"], r["praefix"]))
    return regionen


def _bestand_schluessel(daten_dir) -> set:
    """Erkennungs-Schluessel aller schon gesammelten Firmen.

    Dieselbe Regel wie beim Bestand des Formulars (Domain, sonst Name) -
    damit "vorher bekannt / neu" im Sammelbericht dieselbe Wahrheit
    erzaehlt wie Schritt 3/4.
    """
    schluessel = set()
    wurzel = Path(daten_dir) / "laeufe" / "leadquellen"
    for pfad in (sorted(wurzel.glob("*/firmen.json")) if wurzel.exists()
                 else []):
        try:
            firmen = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for firma in firmen if isinstance(firmen, list) else []:
            kennung = (firma.get("domain") or firma.get("name") or "").lower()
            if kennung:
                schluessel.add(kennung)
    return schluessel


def sammeln_bis_ziel(ort, radius_km, dienste, ziel_anzahl, *, maps=None,
                     gelbe_seiten=None, overpass=None, tabelle=None,
                     max_gebiete=None, daten_dir=None,
                     log=print) -> tuple[list, dict]:
    """Sammeln, bis die gewuenschte Zahl einzigartiger Firmen da ist.

    Olivers Vorgabe (19.08.2026): "100 angefragt" soll so nah wie
    moeglich an 100 einzigartige, gueltige Firmen kommen. Ohne Ort wird
    deutschlandweit gesammelt - Region fuer Region (dichteste zuerst);
    nach jedem Gebiet wird fusioniert, dedupliziert und gezaehlt, dann
    entscheidet der Stand: weiter oder fertig. Es wird NICHTS erfunden
    oder doppelt gezaehlt, um das Ziel zu erreichen - reicht es nicht,
    nennt der Bericht ehrlich den Grund ("grund_ende") und jedes Gebiet
    einzeln ("je_gebiet").
    """
    if not dienste:
        raise ValueError("Ohne Suchbegriffe kann nicht gesammelt werden.")
    ziel_anzahl = max(1, int(ziel_anzahl))
    suchbegriffe = expand_for_search(dienste)
    tabelle = tabelle if tabelle is not None else plz_tabelle()

    deutschlandweit = not str(ort or "").strip()
    if deutschlandweit:
        gebiete = [{"label": f"PLZ-Region {r['praefix']} ({r['label']})",
                    "zentrum": r["zentrum"], "radius_km": r["radius_km"],
                    "praefixe": (r["praefix"],)}
                   for r in regionen_deutschland(tabelle)]
    else:
        zentrum = _zentrum(ort, tabelle)
        if zentrum is None:
            raise ValueError(
                f"Den Ort {ort!r} kennen wir nicht - bitte einen Ortsnamen "
                f"oder eine Postleitzahl angeben.")
        plz_liste = plz_im_umkreis(ort, radius_km, tabelle)
        gebiete = [{"label": str(ort), "zentrum": zentrum,
                    "radius_km": float(radius_km),
                    "praefixe": tuple(sorted({p[:3] for p in plz_liste})
                                      or ("",))}]
    if max_gebiete:
        gebiete = gebiete[:max_gebiete]

    alle_listen: list = []
    fehler_gesamt: dict = {}
    je_gebiet: list = []
    firmen: list = []
    bericht: dict = {}
    einzigartig = 0

    for nummer, gebiet in enumerate(gebiete):
        fehlen = ziel_anzahl - einzigartig
        # Limits am Restbedarf ausrichten: grosszuegig genug fuer Verluste
        # durch Dubletten und Ausschluesse, aber gedeckelt - jeder
        # gescrapte Eintrag wird bezahlt. Das Maps-Limit gilt JE
        # SUCHBEGRIFF, deshalb wird der Restbedarf auf die Begriffe
        # verteilt: beim Verifikationslauf am 19.08.2026 holten
        # 300 x 10 Begriffe 3.530 Firmen fuer ein Ziel von 100.
        maps_limit = max(30, min(300, -(-fehlen * 3 // max(1, len(suchbegriffe)))))
        gs_seiten = max(1, min(10, -(-fehlen // 10)))
        # Gelbe Seiten kann landesweit suchen - deutschlandweit deshalb
        # EINE Abfrage im ersten Gebiet statt 95 kleine je Region.
        if deutschlandweit:
            gs_ort = "Deutschland" if nummer == 0 else ""
        else:
            gs_ort = gebiet["label"]
        log(f"Gebiet {nummer + 1}/{len(gebiete)}: {gebiet['label']} - "
            f"noch {fehlen} von {ziel_anzahl} gesucht")
        listen, fehler = _quellen_sammeln(
            suchbegriffe, gebiet["zentrum"], gebiet["radius_km"],
            gebiet["praefixe"], maps=maps,
            gelbe_seiten=gelbe_seiten if gs_ort else None,
            overpass=overpass, limit_pro_suche=maps_limit,
            gs_ort=gs_ort, gs_seiten=gs_seiten)
        for quelle, text in fehler.items():
            fehler_gesamt[f"{gebiet['label']}: {quelle}"] = text
            log(f"  AUSGEFALLEN {quelle}: {text}")
        alle_listen.extend(listen)

        # Nach jedem Gebiet ueber ALLES fusionieren: so zaehlt eine Firma,
        # die zwei Gebiete oder zwei Quellen kennen, genau einmal.
        vorher = einzigartig
        praefix_filter = (("",) if deutschlandweit
                          else gebiete[0]["praefixe"])
        firmen, bericht = fusionieren(alle_listen, praefix_filter)
        einzigartig = len(firmen)
        geliefert = sum(len(liste) for liste in listen)
        je_gebiet.append({"gebiet": gebiet["label"], "geliefert": geliefert,
                          "neu_einzigartig": einzigartig - vorher})
        log(f"  geliefert: {geliefert}, neu einzigartig: "
            f"{einzigartig - vorher}, gesamt: {einzigartig}/{ziel_anzahl}")
        if einzigartig >= ziel_anzahl:
            break

    if einzigartig >= ziel_anzahl:
        grund_ende = "ziel_erreicht"
    elif fehler_gesamt and not any(alle_listen):
        grund_ende = "quellen_ausgefallen"
    else:
        grund_ende = "quellen_erschoepft"
        log(f"Nur {einzigartig} von {ziel_anzahl} gefunden - die "
            f"durchsuchten Gebiete geben nicht mehr her.")

    # Olivers Beispiel "7 bekannt + 3 neu": gegen den vorhandenen Bestand
    # zaehlen, BEVOR diese Sammlung selbst gespeichert wird. Nichts wird
    # geloescht oder ueberschrieben - der Bestand ergaenzt nur.
    if daten_dir is not None:
        bekannt = _bestand_schluessel(daten_dir)
        neu = sum(1 for f in firmen
                  if (f.get("domain") or f.get("name") or "").lower()
                  not in bekannt)
        bericht["vorher_bekannt"] = einzigartig - neu
        bericht["neu"] = neu
        log(f"Davon schon im Bestand: {einzigartig - neu}, neu: {neu}")

    bericht.update({
        "angefragt": ziel_anzahl,
        "einzigartig": einzigartig,
        "deutschlandweit": deutschlandweit,
        "gebiete_durchsucht": len(je_gebiet),
        "je_gebiet": je_gebiet,
        "grund_ende": grund_ende,
        "quellen_fehler": fehler_gesamt,
        "ort": str(ort or "").strip() or "Deutschland",
        "radius_km": None if deutschlandweit else radius_km,
        "dienste": list(dienste),
        "suchbegriffe": suchbegriffe,
    })
    return firmen, bericht


def ordnername(ort: str, radius_km: float, datum: str) -> str:
    """Sprechender, dateisystem-tauglicher Name der Sammlung."""
    sauber = "".join(c if c.isalnum() else "-" for c in str(ort).casefold())
    return f"{sauber.strip('-') or 'ort'}-{int(radius_km)}km-{datum}"


def speichern(daten_dir, firmen: list, bericht: dict, ordner_name: str) -> Path:
    """Sammlung als eigenen Ordner ablegen - aeltere bleiben unberuehrt."""
    ziel = Path(daten_dir) / "laeufe" / "leadquellen" / ordner_name
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "firmen.json").write_text(
        json.dumps(firmen, ensure_ascii=False, indent=1), encoding="utf-8")
    (ziel / "sammelbericht.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")
    return ziel

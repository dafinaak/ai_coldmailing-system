"""Startet und ueberwacht Anschreiben-Auftraege (die Pipeline, `python -m
pipeline lauf ...`) als Hintergrund-Unterprozesse, gelesen vom Web-Interface.

WICHTIG (PFLICHT-PRUEFPUNKT aus dem Plan, Task 4, Review vom 17.07.2026):
Der Unterprozess MUSS mit `cwd=daten_dir` gestartet werden. Die Pipeline
liest kunden-relative Pfade und `lade_globale_sperrliste(Path("."))`
CWD-relativ (siehe pipeline.__main__.lauf) - startet der Unterprozess mit
dem falschen Arbeitsverzeichnis (z.B. dem Code-Ordner statt dem
Datenverzeichnis), findet er die globale Sperrliste nicht und wendet sie
LEISE nicht an (fehlende Datei ergibt bewusst eine leere Liste, siehe
pipeline.config.lade_globale_sperrliste - kein Fehler, aber ein stiller
Sicherheits-Bypass). Zwei Tests in tests/web/test_laufmanager.py beweisen
das getrennt: einer, dass genau dieser cwd-Wert beim Popen-Aufruf ankommt
(hier), einer, dass die Pipeline selbst die globale Sperrliste tatsaechlich
anwendet, wenn ihr cwd auf ein daten_dir zeigt, das nicht der Code-Ordner
ist (in pipeline-Schicht, siehe Kommentar dort).

Die fuenf Arbeitsschritte (SCHRITTE unten) sind wortwoertlich aus
docs/text-leitfaden-interface.md uebernommen - keine eigenen Formulierungen.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pipeline.config import load_kunde
from pipeline.run_store import _slug

SPERRDATEI_NAME = ".lauf-aktiv"

STANDARD_BEFEHL = [sys.executable, "-m", "pipeline"]

# Projekt-Wurzel (enthaelt das pipeline-Package) - web/laufmanager.py liegt
# in web/, ein Verzeichnis darueber ist die Wurzel.
_PROJEKT_WURZEL = Path(__file__).resolve().parent.parent


def _subprozess_umgebung() -> dict:
    """Der Unterprozess MUSS mit cwd=daten_dir gestartet werden (PFLICHT,
    siehe Modul-Kommentar) - daten_dir ist i.A. NICHT der Code-Ordner (im
    Deployment z.B. ein eigenes Daten-Volume, siehe Plan Task 10). Ohne diese
    Funktion wuerde 'python -m pipeline' dort mit 'No module named pipeline'
    abbrechen: bei '-m' legt Python das cwd (nicht den Ordner des Skripts)
    auf sys.path, und 'pipeline' ist kein installiertes Package. PYTHONPATH
    wird deshalb um die Projekt-Wurzel ergaenzt (eine evtl. schon gesetzte
    PYTHONPATH bleibt erhalten, wird nur vorangestellt)."""
    umgebung = dict(os.environ)
    bisherige = umgebung.get("PYTHONPATH", "")
    teile = [str(_PROJEKT_WURZEL)] + ([bisherige] if bisherige else [])
    umgebung["PYTHONPATH"] = os.pathsep.join(teile)
    return umgebung

# Die fuenf Arbeitsschritte in "Wird vorbereitet" (Laiensprache), wortwoertlich
# aus docs/text-leitfaden-interface.md, Abschnitt "Die Arbeitsschritte in
# 'Wird vorbereitet' (Laiensprache)".
SCHRITTE = [
    "Passende Firmen und Ansprechpartner suchen",
    "E-Mail-Adressen herausfinden",
    "Doppelte und gesperrte Empfänger aussortieren",
    "Die Webseite jeder Firma lesen und ein persönliches Anschreiben schreiben",
    "Jeden Text prüfen: Klingt er persönlich? Stimmt alles?",
]

# Bekannte Fehler-Schnipsel aus dem lauf.log (Reihenfolge = Prioritaet, erster
# Treffer gewinnt) -> dreiteiliger Fehlertext nach dem Muster aus dem
# Leitfaden ("Was ist passiert · Was ist NICHT passiert · Was du tun kannst").
# Die beiden KI-Texte sind wortwoertlich aus dem Karten-Beispiel im
# Design v4 (dc-Datei, simSchritte/Fehlerbeispiel Zeile ~793) uebernommen.
_KI_FEHLER = (
    "Die KI, die die Texte schreibt, hat gerade nicht geantwortet.",
    "Es ist nichts verloren gegangen — alle bisherigen Ergebnisse sind gespeichert.",
    "Versuch es in ein paar Minuten mit »Fortsetzen«.",
)
FEHLER_MUSTER = [
    ("APOLLO_API_KEY", (
        "Die Firmen-Datenbank hat gerade nicht geantwortet.",
        "Es ist nichts verloren gegangen — alle bisherigen Ergebnisse sind gespeichert.",
        "Trag den Zugang zur Firmen-Datenbank nach (Umgebungsvariable APOLLO_API_KEY) "
        "und versuch es mit »Fortsetzen« erneut.",
    )),
    ("Apollo antwortet", (
        "Die Firmen-Datenbank hat gerade nicht geantwortet.",
        "Es ist nichts verloren gegangen — alle bisherigen Ergebnisse sind gespeichert.",
        "Versuch es in ein paar Minuten mit »Fortsetzen«.",
    )),
    ("ANTHROPIC_API_KEY", _KI_FEHLER),
    ("OPENROUTER_API_KEY", _KI_FEHLER),
    ("OpenRouter antwortet", _KI_FEHLER),
    ("Instantly antwortet", (
        "Instantly hat gerade nicht geantwortet.",
        "Es ist nichts verloren gegangen — alle bisherigen Ergebnisse sind gespeichert.",
        "Versuch es in ein paar Minuten mit »Fortsetzen«.",
    )),
]


def wartet_seit_text(lauf_dir: Path) -> str:
    """Formuliert 'Wartet seit ... auf Prüfung' - wörtliches Muster aus dem
    Karten-Beispiel im Leitfaden (docs/text-leitfaden-interface.md), nur die
    Dauer ist dynamisch (dort als Beispiel '2 Std.' vorgegeben). Hierher
    verschoben (Task 7, aus web.routen.auftraege) - web.routen.freigabe,
    web.routen.kampagnen UND jetzt web.wartende brauchen dieselbe Funktion;
    ein Leaf-Modul ohne Route-Importe verhindert Zirkel-Importe (siehe
    web/wartende.py)."""
    pruefung_pfad = lauf_dir / "pruefung_ok.json"
    try:
        sekunden = time.time() - pruefung_pfad.stat().st_mtime
    except OSError:
        sekunden = 0
    if sekunden < 60:
        dauer = "gerade eben"
    elif sekunden < 3600:
        dauer = f"{int(sekunden // 60)} Min."
    else:
        dauer = f"{int(sekunden // 3600)} Std."
    return f"Wartet seit {dauer} auf Prüfung"


class LaufmanagerFehler(Exception):
    """Basisklasse fuer alle Fehler, die eine Route direkt als deutschen
    Formular-/Seitenfehler anzeigen darf (str(fehler) ist bereits fertiger
    Anzeigetext)."""


class LaufBereitsAktiv(LaufmanagerFehler):
    """Fuer diesen Kunden laeuft laut Sperrdatei bereits ein Auftrag."""


class KundeNichtGefunden(LaufmanagerFehler):
    """Die angegebene Kunden-Datei existiert nicht oder ist ungueltig."""


def _pid_lebt(pid: int) -> bool:
    """True, wenn unter dieser PID ein Prozess laeuft. Eigene Funktion (statt
    inline), damit Tests sie leicht durch eine Fake-Funktion ersetzen koennen,
    ohne echte Prozesse starten/toeten zu muessen."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existiert, gehoert nur jemand anderem
    except OSError:
        return False
    return True


def _lade_json_sicher(pfad: Path):
    """Liest eine JSON-Datei, gibt None zurueck statt zu werfen, wenn die
    Datei fehlt oder (weil der Unterprozess gerade mitten im Schreiben ist)
    kurzzeitig kein gueltiges JSON enthaelt. status() soll nie abstuerzen,
    nur weil es genau in diesem Moment pollt."""
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _fehlertext(log_text: str) -> dict:
    """Ordnet bekannte Fehler-Schnipsel im Log einem dreiteiligen deutschen
    Fehlertext zu (Muster aus dem Leitfaden). Unbekannte Fehler bekommen
    einen generischen Text, der die letzte nicht-leere Log-Zeile nennt,
    statt den Nutzer ohne jeden Hinweis dastehen zu lassen."""
    for nadel, (was, nicht, tu) in FEHLER_MUSTER:
        if nadel in log_text:
            return {"was": was, "nicht": nicht, "tu": tu}
    letzte_zeile = ""
    for zeile in reversed(log_text.splitlines()):
        if zeile.strip():
            letzte_zeile = zeile.strip()
            break
    tu = (f"Versuch es mit »Fortsetzen« erneut. Letzte Meldung: {letzte_zeile}"
          if letzte_zeile else "Versuch es mit »Fortsetzen« erneut.")
    return {
        "was": "Es gab ein Problem, das wir nicht genauer benennen können.",
        "nicht": "Es ist nichts verloren gegangen — alle bisherigen Ergebnisse sind gespeichert.",
        "tu": tu,
    }


class Laufmanager:
    """Startet/ueberwacht Auftraege fuer genau ein Datenverzeichnis
    (dieselbe daten_dir wie web.app.create_app). `befehl` ist der Pfad-Praefix
    des Pipeline-Aufrufs (Standard: `python -m pipeline`) - austauschbar in
    Tests gegen ein Fake-Skript, das sich wie die echte CLI verhaelt
    (Schritt-Dateien schreibt, schlaeft), ohne echte API-Aufrufe."""

    def __init__(self, daten_dir, befehl: list[str] | None = None):
        self.daten_dir = Path(daten_dir)
        self.befehl = list(befehl) if befehl else list(STANDARD_BEFEHL)

    # Hilfsfunktionen ------------------------------------------------------

    def _laeufe_ordner(self, slug: str) -> Path:
        ordner = self.daten_dir / "laeufe" / slug
        ordner.mkdir(parents=True, exist_ok=True)
        return ordner

    def _sperr_pfad(self, slug: str) -> Path:
        return self._laeufe_ordner(slug) / SPERRDATEI_NAME

    def _pruefe_sperre(self, slug: str) -> Path:
        """Wirft LaufBereitsAktiv, wenn fuer diesen Kunden laut Sperrdatei
        schon ein lebender Prozess laeuft; raeumt eine verwaiste Sperre
        (Prozess tot) sonst still auf. Gibt den Sperr-Pfad zurueck, damit die
        aufrufende Stelle nach dem erfolgreichen Start die neue PID hinein-
        schreiben kann."""
        sperr_pfad = self._sperr_pfad(slug)
        if sperr_pfad.exists():
            inhalt = sperr_pfad.read_text(encoding="utf-8").strip()
            alte_pid = int(inhalt) if inhalt.isdigit() else None
            if alte_pid is not None and _pid_lebt(alte_pid):
                raise LaufBereitsAktiv(
                    "Für diesen Kunden läuft gerade schon ein Auftrag.")
            sperr_pfad.unlink()  # verwaiste Sperre (Prozess tot) - aufraeumen
        return sperr_pfad

    def _sperre_loesen(self, slug: str, nur_wenn_pid: int | None = None) -> None:
        """Loescht die Sperrdatei fuer diesen Kunden. `nur_wenn_pid`
        (CRITICAL Review-Fund, siehe status()): wird sie uebergeben, wird NUR
        geloescht, wenn der Sperrdatei-Inhalt exakt dieser PID entspricht -
        sonst koennte status() fuer einen ALTEN, laengst toten Laufordner die
        Sperre eines NEUEREN, gerade aktiv laufenden Auftrags DESSELBEN
        Kunden loeschen. status() wird fuer JEDEN Laufordner aufgerufen
        (Dashboard/Kampagnen/Pruefen iterieren ueber ALLE Laeufe aller
        Kunden) - ohne diesen Abgleich wuerde jeder Seitenaufruf, der auch
        einen alten toten Lauf sieht, den Sperr-Schutz eines aktiven neueren
        Laufs desselben Kunden aufheben."""
        sperr_pfad = self._sperr_pfad(slug)
        if not sperr_pfad.exists():
            return
        if nur_wenn_pid is not None:
            inhalt = sperr_pfad.read_text(encoding="utf-8").strip()
            if inhalt != str(nur_wenn_pid):
                return
        sperr_pfad.unlink()

    def _warte_auf_lauf_dir(self, kunden_ordner: Path, vorher: set,
                             prozess, timeout: float = 10.0,
                             intervall: float = 0.05) -> Path | None:
        """Der Laufordner (laeufe/<slug>/<zeitstempel>/) wird vom
        Unterprozess selbst angelegt (RunStore), nicht von uns - wir muessen
        ihn also nach dem Start abwarten/entdecken. Bricht der Unterprozess
        sofort ab (z.B. fehlende Umgebungsvariable), wird nicht die volle
        Zeitspanne gewartet: sobald der Prozess beendet ist und (nach einer
        letzten kurzen Nachschau) kein neuer Ordner da ist, wird sofort
        aufgegeben statt den vollen Timeout auszusitzen."""
        ende = time.time() + timeout
        while time.time() < ende:
            neue = sorted(p for p in kunden_ordner.iterdir()
                          if p.is_dir() and p.name not in vorher)
            if neue:
                return neue[-1]
            if prozess.poll() is not None:
                time.sleep(intervall)
                neue = sorted(p for p in kunden_ordner.iterdir()
                              if p.is_dir() and p.name not in vorher)
                return neue[-1] if neue else None
            time.sleep(intervall)
        return None

    def _kunde_datei_fuer(self, lauf_dir: Path) -> str:
        meta = _lade_json_sicher(lauf_dir / "auftrag_meta.json")
        if meta and meta.get("kunde_datei"):
            return meta["kunde_datei"]
        kunde_pfad = _lade_json_sicher(lauf_dir / "kunde_pfad.json")
        if kunde_pfad and kunde_pfad.get("pfad"):
            return kunde_pfad["pfad"]
        raise LaufmanagerFehler(
            f"Kein Kunde für Laufordner {lauf_dir} ermittelbar.")

    def _limit_fuer(self, lauf_dir: Path) -> int:
        meta = _lade_json_sicher(lauf_dir / "auftrag_meta.json")
        if meta and meta.get("limit"):
            return int(meta["limit"])
        return 10  # gleicher Default wie die CLI (argparse --limit)

    # Oeffentliche Schnittstelle --------------------------------------------

    def starte(self, kunde_datei: str, limit: int) -> Path:
        """Startet 'python -m pipeline lauf <kunde_datei> --limit <limit>'
        als Unterprozess MIT cwd=self.daten_dir (PFLICHT, siehe Modul-Kommentar
        oben) und liefert den entstandenen Laufordner zurueck."""
        kunde_voller_pfad = self.daten_dir / kunde_datei
        if not kunde_voller_pfad.exists():
            raise KundeNichtGefunden(f"Kunden-Datei nicht gefunden: {kunde_datei}")
        try:
            kunde = load_kunde(kunde_voller_pfad)
        except ValueError as fehler:
            raise KundeNichtGefunden(str(fehler)) from None

        slug = _slug(kunde.name)
        kunden_ordner = self._laeufe_ordner(slug)

        # Sperr-Pruefung VOR dem Start (nicht erst nach dem Popen-Aufruf) -
        # sonst wuerde ein zweiter, verbotener Prozess trotzdem schon
        # laufen, bevor der Fehler geworfen wird.
        sperr_pfad = self._pruefe_sperre(slug)

        vorher = {p.name for p in kunden_ordner.iterdir() if p.is_dir()}

        argv = self.befehl + ["lauf", kunde_datei, "--limit", str(limit)]
        temp_log_pfad = kunden_ordner / f".start-{os.getpid()}-{int(time.time() * 1000)}.log"
        log_datei = open(temp_log_pfad, "wb")
        try:
            prozess = subprocess.Popen(
                argv, cwd=str(self.daten_dir), stdout=log_datei, stderr=subprocess.STDOUT,
                env=_subprozess_umgebung())
        except Exception:
            log_datei.close()
            temp_log_pfad.unlink(missing_ok=True)
            raise

        lauf_dir = self._warte_auf_lauf_dir(kunden_ordner, vorher, prozess)
        log_datei.close()

        if lauf_dir is None:
            # Kein Laufordner entstanden - typischerweise eine fehlende
            # Umgebungsvariable, die den Unterprozess sofort abbrechen liess
            # (RunStore legt den Ordner erst NACH den Env-Pruefungen an).
            log_text = temp_log_pfad.read_text(encoding="utf-8", errors="replace")
            temp_log_pfad.unlink(missing_ok=True)
            fehler = _fehlertext(log_text)
            raise LaufmanagerFehler(f"{fehler['was']} {fehler['nicht']} {fehler['tu']}")

        ziel_log_pfad = lauf_dir / "lauf.log"
        temp_log_pfad.replace(ziel_log_pfad)

        (lauf_dir / "pid").write_text(str(prozess.pid), encoding="utf-8")
        (lauf_dir / "auftrag_meta.json").write_text(
            json.dumps({"kunde_datei": kunde_datei, "limit": limit}), encoding="utf-8")
        sperr_pfad.write_text(str(prozess.pid), encoding="utf-8")

        return lauf_dir

    def setze_fort(self, lauf_dir, neu_ab: str | None = None) -> Path:
        """Setzt einen angehaltenen Auftrag fort ('--fortsetzen <lauf_dir>',
        optional '--neu-ab <schritt>'), ebenfalls MIT cwd=self.daten_dir."""
        lauf_dir = Path(lauf_dir)
        slug = lauf_dir.parent.name
        kunde_datei = self._kunde_datei_fuer(lauf_dir)
        limit = self._limit_fuer(lauf_dir)

        sperr_pfad = self._pruefe_sperre(slug)

        argv = self.befehl + ["lauf", kunde_datei, "--limit", str(limit),
                              "--fortsetzen", str(lauf_dir)]
        if neu_ab:
            argv += ["--neu-ab", neu_ab]

        log_datei = open(lauf_dir / "lauf.log", "ab")
        prozess = subprocess.Popen(
            argv, cwd=str(self.daten_dir), stdout=log_datei, stderr=subprocess.STDOUT,
            env=_subprozess_umgebung())
        log_datei.close()

        (lauf_dir / "pid").write_text(str(prozess.pid), encoding="utf-8")
        sperr_pfad.write_text(str(prozess.pid), encoding="utf-8")

        return lauf_dir

    def status(self, lauf_dir) -> dict:
        lauf_dir = Path(lauf_dir)
        slug = lauf_dir.parent.name

        pid_text = None
        pid_pfad = lauf_dir / "pid"
        if pid_pfad.exists():
            pid_text = pid_pfad.read_text(encoding="utf-8").strip()
        pid = int(pid_text) if pid_text and pid_text.isdigit() else None
        laeuft = pid is not None and _pid_lebt(pid)

        leads = _lade_json_sicher(lauf_dir / "leads.json")
        dedupe = _lade_json_sicher(lauf_dir / "dedupe.json")
        personalisierung = _lade_json_sicher(lauf_dir / "personalisierung.json")
        pruefung_ok = (lauf_dir / "pruefung_ok.json").exists()
        freigegeben = (lauf_dir / "FREIGABE.txt").exists()
        versand_komplett = (lauf_dir / "versand_komplett.json").exists()
        # Carry-Forward aus Task-4-Review (Task 5, web/routen/freigabe.py
        # schreibt abgelehnt.json beim Ablehnen): MUSS vor pruefung_ok
        # geprueft werden, sonst zeigt ein abgelehnter Lauf fuer immer
        # "wartet_auf_freigabe" statt zu verschwinden.
        abgelehnt = (lauf_dir / "abgelehnt.json").exists()

        if laeuft:
            zustand = "laeuft"
        elif abgelehnt:
            zustand = "abgelehnt"
        elif versand_komplett:
            zustand = "uebergeben"
        elif freigegeben:
            zustand = "freigegeben"
        elif pruefung_ok:
            zustand = "wartet_auf_freigabe"
        else:
            zustand = "angehalten"

        if pid is not None and not laeuft:
            # Der Prozess DIESES Laufordners ist tot - die Sperre darf aber
            # nur geloescht werden, wenn sie WIRKLICH noch diese PID traegt
            # (CRITICAL Review-Fund, siehe _sperre_loesen): ein neuerer,
            # gerade aktiv laufender Auftrag desselben Kunden koennte die
            # Sperre laengst mit seiner eigenen (lebenden) PID ueberschrieben
            # haben.
            self._sperre_loesen(slug, nur_wenn_pid=pid)

        # Altes Listenformat abfangen (siehe pipeline.__main__.lauf): vor der
        # "ohne_email"-Zaehlung war leads.json eine reine Liste.
        if isinstance(leads, list):
            leads = {"leads": leads, "ohne_email": 0}

        if leads is None:
            schritt = 1
        elif dedupe is None:
            schritt = 3
        elif personalisierung is None:
            schritt = 4
        else:
            schritt = 5

        # schritt (1-5) sagt, WELCHER Schritt gerade dran ist/als letztes
        # angefasst wurde - das ist NICHT dasselbe wie "wie viele Schritte
        # sind fertig". Ist der Auftrag durchgelaufen (wartet_auf_freigabe/
        # freigegeben/uebergeben), sind ALLE fuenf Schritte erledigt, auch
        # Schritt 5 selbst (der sonst nie einen Haken bekaeme, weil
        # schritt==5 den Maximalwert erreicht hat, aber "nr < schritt" fuer
        # nr=5 nie wahr wird). schritt_fertig ist die fuer die Anzeige
        # gedachte Zahl "so viele Haken".
        if zustand in ("wartet_auf_freigabe", "freigegeben", "uebergeben", "abgelehnt"):
            schritt_fertig = 5
        else:
            schritt_fertig = schritt - 1

        fehler = None
        if zustand == "angehalten":
            log_pfad = lauf_dir / "lauf.log"
            log_text = log_pfad.read_text(encoding="utf-8", errors="replace") if log_pfad.exists() else ""
            fehler = _fehlertext(log_text)

        return {
            "zustand": zustand,
            "schritt": schritt,
            "schritt_fertig": schritt_fertig,
            "schritt_label": SCHRITTE[schritt - 1],
            "gefunden": len(leads["leads"]) if leads else 0,
            "ohne_email": leads["ohne_email"] if leads else 0,
            "verworfen": len(dedupe["verworfen"]) if dedupe else 0,
            "fertig": len(personalisierung["fertig"]) if personalisierung else 0,
            "nacharbeit": len(personalisierung["nacharbeit"]) if personalisierung else 0,
            "fehler": fehler,
        }

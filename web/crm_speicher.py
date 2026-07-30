"""CRM-Datenfundament (Bauplan CRM-Verkaufsstufen, Schritt 1; von
Leonard freigegeben 29.07.2026).

Eine SQLite-Datenbankdatei im Datenverzeichnis (daten_dir/kontakte.db)
mit genau einer Tabelle: die CRM-Kontakte samt Verkaufsstufe und
Kampagnen-Zuordnung. Entscheidungen vom 29.07.2026:

- Je E-Mail-Adresse genau EIN Kontakt (Duplikate werden abgewiesen,
  nichts wird still ueberschrieben).
- Stufen: die sechs deutschen Wholix-Stufen (STUFEN unten); Einstieg
  immer "neuer_lead". Unbekannte Stufen werden laut abgelehnt.
- Mehrere Kampagnen von Beginn an: jeder Kontakt traegt seine
  Kampagne; Filter und Zaehler arbeiten je Kampagne oder ueber alle.
- Einzelnutzer-Betrieb; SQLite reicht dafuer ohne weitere Vorkehrungen
  und waechst problemlos mit.

Die Uhr ist injizierbar (uhr=...), damit Tests feste Zeitstempel
pruefen koennen - gleiche Bauart wie anderswo im Projekt.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

STUFEN = ("neuer_lead", "demo_termin", "nachfassen",
          "angebot", "gewonnen", "verloren")

STUFEN_BESCHRIFTUNG = {
    "neuer_lead": "Neuer Lead",
    "demo_termin": "Demo-Termin",
    "nachfassen": "Nachfassen",
    "angebot": "Angebot",
    "gewonnen": "Gewonnen",
    "verloren": "Verloren",
}

_TABELLE = """
CREATE TABLE IF NOT EXISTS kontakte (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    firma TEXT NOT NULL DEFAULT '',
    kampagne TEXT NOT NULL DEFAULT '',
    stufe TEXT NOT NULL DEFAULT 'neuer_lead',
    angelegt_am TEXT NOT NULL,
    stufe_geaendert_am TEXT NOT NULL
)
"""


def _jetzt_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class KontakteSpeicher:
    def __init__(self, pfad, uhr=_jetzt_iso):
        self.pfad = Path(pfad)
        self.uhr = uhr
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        with self._verbindung() as v:
            v.execute(_TABELLE)

    def _verbindung(self):
        v = sqlite3.connect(self.pfad)
        v.row_factory = sqlite3.Row
        return v

    def kontakt_anlegen(self, email: str, name: str = "", firma: str = "",
                        kampagne: str = "") -> bool:
        """Legt einen Kontakt mit Einstiegs-Stufe an. Gibt False zurueck,
        wenn die Adresse schon existiert (nichts wird ueberschrieben)."""
        jetzt = self.uhr()
        with self._verbindung() as v:
            try:
                v.execute(
                    "INSERT INTO kontakte (email, name, firma, kampagne, "
                    "stufe, angelegt_am, stufe_geaendert_am) "
                    "VALUES (?, ?, ?, ?, 'neuer_lead', ?, ?)",
                    (email, name, firma, kampagne, jetzt, jetzt))
                return True
            except sqlite3.IntegrityError:
                return False

    def stufe_setzen(self, email: str, stufe: str) -> None:
        if stufe not in STUFEN:
            raise ValueError(
                f"Unbekannte Stufe {stufe!r} - erlaubt: {', '.join(STUFEN)}")
        with self._verbindung() as v:
            v.execute(
                "UPDATE kontakte SET stufe = ?, stufe_geaendert_am = ? "
                "WHERE email = ?", (stufe, self.uhr(), email))

    def kontakte(self, kampagne: str | None = None,
                 stufe: str | None = None) -> list:
        abfrage = "SELECT * FROM kontakte WHERE 1=1"
        werte = []
        if kampagne is not None:
            abfrage += " AND kampagne = ?"
            werte.append(kampagne)
        if stufe is not None:
            abfrage += " AND stufe = ?"
            werte.append(stufe)
        abfrage += " ORDER BY angelegt_am DESC, email"
        with self._verbindung() as v:
            return [dict(zeile) for zeile in v.execute(abfrage, werte)]

    def zaehler(self, kampagne: str | None = None) -> dict:
        """Zaehler je Stufe (immer alle sechs, fehlende als 0) plus
        'alle' - die Zahlen fuer die Stufen-Leiste."""
        abfrage = "SELECT stufe, COUNT(*) AS anzahl FROM kontakte"
        werte = []
        if kampagne is not None:
            abfrage += " WHERE kampagne = ?"
            werte.append(kampagne)
        abfrage += " GROUP BY stufe"
        ergebnis = {stufe: 0 for stufe in STUFEN}
        with self._verbindung() as v:
            for zeile in v.execute(abfrage, werte):
                ergebnis[zeile["stufe"]] = zeile["anzahl"]
        ergebnis["alle"] = sum(ergebnis[stufe] for stufe in STUFEN)
        return ergebnis

    def kampagnen(self) -> list:
        """Alle Kampagnen, zu denen Kontakte existieren - daraus entsteht
        die Kampagnen-Auswahl (Brett je Kampagne, kein Anlegen von Hand)."""
        with self._verbindung() as v:
            return [zeile["kampagne"] for zeile in v.execute(
                "SELECT DISTINCT kampagne FROM kontakte ORDER BY kampagne")]

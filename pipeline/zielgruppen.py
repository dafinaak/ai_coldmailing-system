"""Zielgruppen: derselbe Zonen-Ablauf fuer mehr als eine Branche.

Dafina, 15.10.2026: "ky eshte jo IT, AMA TNJEJTIN SEN duhesh me bo me i
scrap si ne listat tjera" - Prozessberater statt IT-Dienstleister, aber
dieselbe Kette und dieselben Listen.

Die Kette war an drei Stellen auf eine Zielgruppe verdrahtet:

  1. die Suchbegriffe (`zonen.SUCHBEGRIFFE`, eine Liste),
  2. das Profil-Urteil (`branchen_filter.SYSTEM_PROMPT`),
  3. der Name der Listen (`IT-Liste-Emails-Zona...`).

Hier stehen sie beisammen, eine Zeile je Zielgruppe. Die IT-Zielgruppe
LIEST Begriffe und Prompt dort, wo sie schon stehen - eine zweite Kopie
wuerde mit der Zeit auseinanderlaufen, und dann sammelt die Kette nach
anderen Worten als sie urteilt.

Der Name der Listen gehoert dazu, weil zwei Zielgruppen dasselbe
Postleitzahl-Gebiet haben: Zone "32" ist fuer die IT vergeben, und die
Zonen-Nummer allein wuerde die Listen gegenseitig ueberschreiben.
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline import zonen
from pipeline.branchen_filter import SYSTEM_PROMPT
from pipeline.sources.overpass import STANDARD_MERKMALE

# Dafinas Liste vom 15.10.2026, in ihrer Reihenfolge. "Prozessoptimierung"
# stand zweimal drin und steht hier einmal: jeder Begriff kostet bis zu
# 110 Orte bei Apify, ein doppelter zahlt dasselbe zweimal.
PROZESS_SUCHBEGRIFFE = (
    "Prozessberater",
    "Prozess Consultant",
    "Prozess Consulting",
    "Prozessoptimierer",
    "Prozessspezialist",
    "Prozessexperte",
    "Prozessoptimierung",
    "Prozessberatung",
    "Prozessmanagement",
    "Prozess- und Organisationsberater",
    "Prozess- und Organisationsberatung",
    "Prozess- und Strategieberatung",
    "Organisations- und Prozessberatung",
    "Geschäftsprozessanalyse",
    "Geschäftsberatung",
    "Geschäftsberater",
    "Consulting im Prozessmanagement",
    "Prozessberatung für Geschäftsprozesse",
    "REFA Consulting",
    "REFA Berater",
    "REFA Beratung",
)

# Dasselbe Geruest wie der IT-Prompt: ein JSON-Urteil, eine Liste "drin",
# eine Liste "draussen", und im Zweifel false. Die Regel kommt aus
# Dafinas Begriffsliste - Prozesse UND Organisation, nicht Strategie
# allein und nicht Schulung allein.
PROZESS_SYSTEM_PROMPT = """Du prüfst, ob eine Firma zum Zielprofil einer
B2B-Kampagne passt. Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{"passt": true|false, "typ": "<kurze Einordnung>", "grund": "<ein Satz>"}

ZIELPROFIL (passt = true), nur wenn die Firma andere Unternehmen zu
ihren Arbeitsabläufen berät:
- Prozessberatung, Prozessoptimierung, Prozessmanagement
- Organisationsberatung, Aufbau- und Ablauforganisation
- Geschäftsprozessanalyse, Prozessaufnahme, Prozessdokumentation
- REFA-Beratung, Arbeitsstudium, Zeitwirtschaft, Arbeitsplatzgestaltung
- Lean-, Kaizen- und KVP-Beratung, Wertstromanalyse
- typische Merkmale: Analyse und Verbesserung der Abläufe BEIM KUNDEN,
  als Beratungsleistung

AUSSCHLÜSSE (passt = false), auch wenn "Prozess" im Namen steht:
- reine Schulung und Weiterbildung: Seminare, Trainings, Zertifikate,
  Coaching-Angebote ohne Beratung im Betrieb
- reine Strategie-, Management- oder Nachfolgeberatung ohne Arbeit an
  den Abläufen
- Firmen mit EIGENER Software oder Software-Entwicklung als Angebot:
  Prozess-/Workflow-/BPM-Software, Hersteller, Anbieter eines eigenen
  Produkts - AUCH dann, wenn sie zusätzlich beraten
- Beratungs- und Vertriebspartner eines FREMDEN Produkts (SAP-, Signavio-,
  Camunda-Partner und Ähnliches): das ist Projektgeschäft am Produkt
- Firmen, die SELBST Automationen anbieten (Prozessautomatisierung,
  Workflow-Automation, RPA, KI-Automatisierung) - das sind Wettbewerber
- Personalberatung, Zeitarbeit, Recruiting
- Steuerberatung, Wirtschaftsprüfung, Rechtsberatung
- Qualitätsmanagement allein als Zertifizierung (ISO-Audit, Zertifizierer)
- Marketing-, Werbe- und Webagenturen
- alles Branchenfremde (Handel, Handwerk, Medizin, Bildung ...)

AUSDRÜCKLICH DRIN, damit die Regeln oben keine echten Prozessberater
mitreißen:
- Beratung, die neben den Abläufen auch die Organisation, die Kennzahlen
  oder die Einführung von Standards begleitet - solange die Arbeit an den
  Abläufen des Kunden der Kern bleibt
- Einzelberater und kleine Büros: Größe entscheidet nicht

Im Zweifel passt = false. Sei streng: Nur klar erkennbare
Prozess- und Organisationsberatung bekommt true."""


@dataclass(frozen=True)
class Zielgruppe:
    schluessel: str
    name: str
    suchbegriffe: tuple
    system_prompt: str
    listen_prefix: str
    # Overpass sucht nach Karten-Merkmalen, nicht nach Worten. Mit dem
    # Merkmal der IT wuerde eine andere Zielgruppe IT-Firmen einsammeln,
    # die der Profil-Filter danach alle wegwirft - die freie zweite
    # Quelle waere still wirkungslos.
    osm_merkmale: tuple = STANDARD_MERKMALE
    # Teil des Ordnernamens: "" fuer die IT (so heissen ihre Ordner seit
    # August), "-prozess" fuer die Prozessberater. Ohne ihn fand das
    # Muster "zona33-dropcontact-*" am 15.10.2026 den IT-Ordner vom
    # September, warf dessen Firmen als "ausserhalb der Zone" weg und
    # schrieb eine LEERE Liste, ohne sich zu beschweren.
    ordner_teil: str = ""
    # Eine Firma, die selbst Automationen anbietet, ist Wettbewerber und
    # bleibt draussen. Dafina am 15.10.2026 fuer die Prozessberater
    # bestaetigt: "po vlen automatizimi edhe ketu".
    wettbewerber_pruefung: bool = True

    def lauf_glob(self, zone: str, art: str) -> str:
        """Das Suchmuster fuer einen Lauf-Ordner dieser Zielgruppe.

        art: "dropcontact", "overpass" ... - der Teil nach der Zone.
        """
        return f"zona{zone}{self.ordner_teil}-{art}-*"


ZIELGRUPPEN = {
    "it": Zielgruppe(
        schluessel="it",
        name="IT-Dienstleister",
        suchbegriffe=tuple(zonen.SUCHBEGRIFFE),
        system_prompt=SYSTEM_PROMPT,
        listen_prefix="IT-Liste-Emails-",
        osm_merkmale=STANDARD_MERKMALE,
    ),
    "prozess": Zielgruppe(
        schluessel="prozess",
        name="Prozess- und Organisationsberater",
        suchbegriffe=PROZESS_SUCHBEGRIFFE,
        system_prompt=PROZESS_SYSTEM_PROMPT,
        listen_prefix="Prozess-Liste-Emails-",
        osm_merkmale=(("office", "consulting"),),
        ordner_teil="-prozess",
    ),
}

STANDARD = "it"


def zielgruppe(schluessel: str = STANDARD) -> Zielgruppe:
    """Die Zielgruppe zu "it", "prozess" ... - unbekannt ist ein Fehler.

    Keine stille Rueckkehr zur IT: wer sich vertippt, wuerde sonst die
    falsche Branche sammeln und dafuer zahlen.
    """
    try:
        return ZIELGRUPPEN[schluessel]
    except KeyError:
        raise KeyError(
            f"Unbekannte Zielgruppe {schluessel!r} - bekannt: "
            f"{', '.join(sorted(ZIELGRUPPEN))}") from None

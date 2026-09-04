"""Branchen-Pruefung nach Olivers Profil (Auftrag 30.07.2026).

Anlass: Die erste Paket-Liste enthielt Branchenfremde (Augenarzt,
Zeitarbeit, Baufinanzierung, Gebaeudereinigung ...), Rechenzentren,
Software-Produktfirmen, Niederlassungen und moegliche Automations-
Wettbewerber. Der alte Filter (Schluesselwoerter in Name/Kategorie,
pipeline/listen_fusion.py) ist dafuer zu grob: Er kann nicht sehen,
WAS eine Firma tatsaechlich anbietet.

Zwei Stufen:

1. Harte Regeln (kostenlos, ohne Netz): Niederlassungen/Filialen
   (Olivers Vorgabe "nur die Zentrale"), klar branchenfremde Kategorien
   und Firmen mit eigener Software (Dafina, 31.08.2026). Diese Faelle
   brauchen kein KI-Urteil.
2. KI-Urteil je Firma: Name, Kategorien und der sichtbare Text der
   Firmen-Webseite gehen an das Modell, das nach Olivers Profil
   entscheidet - inklusive der Frage, ob die Firma SELBST Automationen
   anbietet (Wettbewerber).

Es gab bis zum 31.08.2026 eine dritte Stufe, die "zweite Chance": sie
holte ausgeschlossene Software-Hersteller zurueck, sobald deren Webseite
auch IT-Betreuung nannte. Ueber sie kamen vier der sechs Firmen herein,
die Dafina aus den Listen 33 und 34 aussortiert hat. Ihre Regel sagt das
Gegenteil - eigene Software heisst raus, auch mit Betreuung -, deshalb
ist die Stufe ersatzlos entfernt (Gegentest:
tests/test_branchen_filter.py::test_zweite_chance_ist_abgeschafft).

Zuverlaessigkeit zuerst: Was die KI nicht eindeutig als passend
bezeichnet, gilt als NICHT passend (typ "unsicher") und wird im Bericht
aufgefuehrt - lieber eine Firma zu wenig anschreiben als eine falsche.
"""
import json
import re

# "eigene_software" stand hier bis 03.09.2026 als harter Grund; seitdem
# urteilt die KI anhand der Webseite (siehe software_hinweis).
AUSSCHLUSS_GRUENDE = ("niederlassung", "branchenfremd", "unsicher")

# Olivers Vorgabe: bei Filialisten/Niederlassungen nur die Zentrale.
_NIEDERLASSUNG = re.compile(
    r"\b(niederlassung|filiale|zweigstelle|zweigniederlassung|standort)\b",
    re.IGNORECASE)

# Kategorien/Namensteile, die eine Firma ohne KI-Rueckfrage disqualifizieren.
# Alle aus der echten Fehlerliste vom 30.07.2026 abgeleitet.
_FREMD = (
    "zeitarbeit", "personaldienst", "personalmanagement", "immobilien",
    "lebensmittel", "biomarkt", "supermarkt", "spielwaren", "spielzeug",
    "möbel", "verlag", "buchhandlung", "reinigung", "gebäudeservice",
    "baufinanzier", "finanzberat", "versicherung", "steuerberat",
    "buchhaltungs", "coworking", "arzt", "ärzt", "klinik", "augenlaser",
    "zahn", "apotheke", "restaurant", "café", "hotel", "friseur",
    "fitness", "schule", "kindergarten", "bäckerei", "metzger",
    "autohaus", "kfz", "reifen", "grosshändler", "großhändler",
    "einzelhandel", "baumarkt", "garten", "veranstaltungsservice",
    "eventmanagement", "reisebüro", "logistik", "spedition",
)


# Dafinas Regel (31.08.2026): Firmen mit eigener Software gehoeren nicht
# ins Zielprofil - auch nicht, wenn sie zusaetzlich IT betreuen.
#
# Praezisierung (Dafina, 03.09.2026): das entscheidet die WEBSEITE, nicht
# die Verzeichnis-Kategorie. Vom 31.08. bis 03.09. warf eine harte Regel
# jede Firma raus, deren Google-Maps-Kategorie "Softwareentwickler/
# -hersteller" enthielt - ohne die Seite zu lesen. Google vergibt vier bis
# fuenf Kategorien je Firma, und echte Systemhaeuser tragen diese oft mit.
# Bei der Nachpruefung der Zonen 32-34 traf die harte Regel 61 Firmen;
# die Webseite bestaetigte 49 davon und holte 12 echte IT-Dienstleister
# zurueck (Computer live, Deltatec, ELAAX, IT-HAUS, Klanke, Wulf Systems).
# Die Kategorie steht weiter im Prompt - als Hinweis fuer die KI, nicht
# als Urteil. Der Ausschluss selbst steht im SYSTEM_PROMPT (eigene
# Software = raus, auch mit Support) und wird an der Seite geprueft.
#
# Diese Kategorie-Woerter loesen den Hinweis aus (software_hinweis()).
# Bewusst nur Kategorien, nicht der Name: "Software" im Namen traegt auch
# ein echtes Systemhaus ("Eulah IT - Systemhaus fuer Digitalisierung,
# Software & IT").
_EIGENE_SOFTWARE = (
    "softwareentwickl", "softwarehersteller", "software-hersteller",
    "softwareanbieter", "software-anbieter", "softwarehaus",
    "softwarevertrieb", "software-vertrieb", "software publisher",
    "software development", "schulungsinstitut für software",
)


def _text_von(firma: dict) -> str:
    return " ".join([firma.get("name", "")] +
                    [str(k) for k in firma.get("categories") or []]).lower()


def _kategorien_von(firma: dict) -> str:
    return " ".join(str(k) for k in firma.get("categories") or []).lower()


def harter_ausschluss(firma: dict):
    """Gibt den Ausschlussgrund zurueck oder None, wenn die Firma die
    harten Regeln uebersteht (dann entscheidet die KI)."""
    if _NIEDERLASSUNG.search(firma.get("name", "")):
        return "niederlassung"
    text = _text_von(firma)
    if any(wort in text for wort in _FREMD):
        return "branchenfremd"
    # "Softwareentwickler/-hersteller" als Verzeichnis-Kategorie ist hier
    # KEIN harter Ausschluss mehr (Dafina, 03.09.2026: die Webseite
    # entscheidet, nicht die Karte). Die Kategorie geht als Hinweis an die
    # KI - siehe software_hinweis() und firma_bewerten().
    return None


def software_hinweis(firma: dict) -> str:
    """Hinweis fuer die KI, wenn das Verzeichnis die Firma als Software-
    Entwickler/-Hersteller fuehrt. Google vergibt vier bis fuenf
    Kategorien je Firma, und ein klassisches Systemhaus traegt oft auch
    diese - am 03.09.2026 hatte die Kategorie allein 61 Firmen der Zonen
    32-34 aussortiert, von denen die Webseite 12 als reine IT-Betreuer
    auswies (Computer live, Deltatec, ELAAX, IT-HAUS, Klanke, Wulf Systems).
    Deshalb: die Kategorie schaerft den Blick, sie faellt kein Urteil."""
    if any(wort in _kategorien_von(firma) for wort in _EIGENE_SOFTWARE):
        return ("Hinweis: Das Verzeichnis führt die Firma als Softwareentwickler/"
                "-hersteller. Prüfe am Webseitentext besonders, ob sie EIGENE "
                "Software oder Softwareentwicklung anbietet - dann passt = false, "
                "auch mit Support. Zeigt die Webseite nur klassische IT-Betreuung "
                "ohne eigenes Produkt, gilt die Webseite.")
    return ""


SYSTEM_PROMPT = """Du prüfst, ob eine Firma zum Zielprofil einer
B2B-Kampagne passt. Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{"passt": true|false, "typ": "<kurze Einordnung>", "grund": "<ein Satz>"}

ZIELPROFIL (passt = true), nur wenn die Firma als Dienstleister die IT
ihrer Geschäftskunden betreut:
- IT-Dienstleister, IT-Systemhaus, IT-Service, IT-Support
- typische Merkmale: Betreuung/Wartung von IT-Infrastruktur, Netzwerke,
  Server, Arbeitsplätze, Managed Services, IT-Betreuung für Firmen

AUSSCHLÜSSE (passt = false), auch wenn "IT" im Namen steht:
- reiner Computerhandel: Verkauf von Hardware oder Software als Ware
- Firmen mit EIGENER Software oder mit Software-Entwicklung als
  Angebot: Entwickler, Hersteller, Anbieter eines eigenen Produkts,
  ebenso Auftrags-/Individualentwicklung für Kunden - AUCH dann, wenn
  sie zusätzlich Support, Wartung oder Schulung anbieten
- Anbieter eines Branchen-/Nischenprodukts (Software für Steuerkanzleien,
  Kirchen, Arztpraxen, CAD, Logistik und Ähnliches)
- Beratungs- und Vertriebspartner eines FREMDEN Produkts (Salesforce-,
  SAP-, DATEV-Partner, ERP-/CRM-Einführung): das ist Projektgeschäft am
  Produkt, keine laufende IT-Betreuung
- Firmen, deren Angebot im Kern IT-Sicherheit ist (Security-Beratung,
  Pentest, Schwachstellenscan, ISMS/ISO 27001, NIS-2, externer ISB/CISO)
  - auch wenn "Managed IT" als Nebenpunkt daneben steht
- Rechenzentren, Colocation
- reine Elektro-/Leitungs-Installationsunternehmen
- Hoster, Webhosting, Internet-Provider, Internet-Dienstleister
- Firmen, die SELBST Automationen anbieten (Prozessautomatisierung,
  Workflow-Automation, RPA, Systemintegration als Automations-Angebot,
  KI-Automatisierung) - das sind Wettbewerber
- Webdesign-/Marketing-/Werbeagenturen ohne IT-Betreuung
- alles Branchenfremde (Handel, Handwerk, Beratung, Medizin, Bildung ...)

AUSDRÜCKLICH DRIN, damit die Regeln oben keine echten Systemhäuser
mitreißen:
- laufende Betreuung von Microsoft 365, Cloud-Arbeitsplätzen, Servern,
  Netzwerken und Endgeräten - das ist normales IT-Betreuungsgeschäft,
  auch wenn dabei fremde Produkte eingerichtet und gepflegt werden

Im Zweifel passt = false. Sei streng: Nur klar erkennbare
IT-Dienstleister mit Betreuungsgeschäft bekommen true."""


WETTBEWERBER_SYSTEM = """Du prüfst EINE Frage: Bietet diese Firma selbst
Geschäftsprozess-Automatisierung oder KI-Lösungen als LEISTUNG für
Kunden an?

"automation" NUR, wenn die Firma solche Leistungen erkennbar ANBIETET:
- Prozessautomatisierung, Workflow-Automatisierung, Geschäftsprozess-
  Automatisierung, RPA, Hyperautomation
- KI-Lösungen, KI-Beratung, KI-Implementierung als Dienstleistung,
  KI-Agenten, Chatbots, "Prozesse intelligent automatisieren"
- Automatisierungs-Beratung oder -Umsetzung für Kunden (z.B. mit n8n,
  Make, Zapier, Power Automate)
- Digitalisierungs-Projekte mit ausdrücklichem Automatisierungs-Angebot
  ("Abläufe automatisieren", "Papierlose Prozesse", Workflow-Systeme)
- Geschäftsprozess-Integration/EDI-Orchestrierung NUR, wenn die Firma
  sie selbst ausdrücklich als (Business Process) Automation vermarktet -
  gewöhnliche Systemintegration ohne dieses Versprechen zählt NICHT

"keine_automation" bei:
- reiner IT-Betreuung: Managed Services, Support, Wartung, Netzwerk/
  Server-Betrieb, Hardware, Security-Betrieb, Backup, Cloud-Migration
- INDUSTRIE-Automatisierung: Steuerungstechnik, SPS/PLC, Maschinen-,
  Fertigungs- oder Gebäudeautomation - andere Branche, kein Wettbewerber
- Software-PRODUKTEN, die Automatisierungs-/KI-Funktionen nur ENTHALTEN
  (z.B. ein CAD-, Logistik- oder Branchenprodukt "mit KI") - solange die
  Firma keine Automatisierungs-DIENSTLEISTUNG verkauft
- blossen Erwähnungen wie "automatisierte Backups", "automatisches
  Monitoring" oder intern genutzter Automatisierung

"unsicher" bei zu wenig oder mehrdeutiger Information. Rate NICHT.

Antworte AUSSCHLIESSLICH mit:
{"einstufung": "automation" | "keine_automation" | "unsicher",
 "belege": "<Zitat/Stichwort von der Seite oder leer>"}"""


def ist_wettbewerber(firma: dict, webtext: str, ki) -> dict:
    """Zweite, harte Pruefung (Olivers Fund 30.07.2026; Dreiteilung seit
    der Phase-2-Eichung 20.08.2026): Bietet die Firma SELBST
    Geschaeftsprozess-Automatisierung/KI als Leistung an?

    Gibt {"wettbewerber": bool, "unsicher": bool, "belege": str} zurueck.
    Unlesbare Antworten gelten als "unsicher" - wer nicht eindeutig
    unbedenklich ist, wird nicht angeschrieben (die Firma bleibt
    gespeichert). WICHTIG fuer Aufrufer: Ist gar kein Webseiten-Text
    lesbar, soll die Firma OHNE diesen Aufruf als unsicher gelten -
    ein Urteil nur aus dem Namen waere geraten (Benchmark 20.08.2026)."""
    kategorien = ", ".join(str(k) for k in firma.get("categories") or []) or "keine"
    webseite_teil = (f"Text der Webseite (Auszug):\n{webtext[:3500]}"
                     if webtext.strip() else
                     "Kein Text von der Webseite verfügbar - urteile nur nach "
                     "Name und Kategorien; im Zweifel \"unsicher\".")
    prompt = (f"Firma: {firma.get('name', '')}\n"
              f"Kategorien: {kategorien}\n\n{webseite_teil}")
    antwort = ki.frage(WETTBEWERBER_SYSTEM, prompt)
    treffer = re.search(r"\{.*\}", antwort or "", re.S)
    if not treffer:
        return {"wettbewerber": False, "unsicher": True,
                "belege": "KI-Antwort nicht lesbar"}
    try:
        daten = json.loads(treffer.group(0))
    except ValueError:
        return {"wettbewerber": False, "unsicher": True,
                "belege": "KI-Antwort nicht lesbar"}
    belege = str(daten.get("belege") or "")
    if "einstufung" in daten:
        stufe = str(daten.get("einstufung") or "").strip().lower()
        return {"wettbewerber": stufe == "automation",
                "unsicher": stufe not in ("automation", "keine_automation"),
                "belege": belege}
    # Alte Antwortform {"wettbewerber": true|false} (aeltere Ablaeufe und
    # Test-Attrappen) bleibt lesbar.
    return {"wettbewerber": bool(daten.get("wettbewerber")),
            "unsicher": False, "belege": belege}


def firma_bewerten(firma: dict, webtext: str, ki, system=None) -> dict:
    """Bewertet EINE Firma. Gibt {"passt", "typ", "grund", "quelle"}.
    "system" erlaubt einen kampagnen-eigenen Prompt statt SYSTEM_PROMPT."""
    grund = harter_ausschluss(firma)
    if grund:
        return {"passt": False, "typ": grund,
                "grund": f"Harte Regel: {grund}", "quelle": "regel"}

    kategorien = ", ".join(str(k) for k in firma.get("categories") or []) or "keine"
    webseite_teil = (f"Text der Webseite (Auszug):\n{webtext[:3500]}"
                     if webtext.strip() else
                     "Kein Text von der Webseite verfügbar (keine Webseite "
                     "erreichbar) - urteile nur nach Name und Kategorien.")
    hinweis = software_hinweis(firma)
    prompt = (f"Firma: {firma.get('name', '')}\n"
              f"Kategorien (aus Verzeichnissen): {kategorien}\n"
              f"Webseite: {firma.get('website') or 'keine'}\n"
              + (f"{hinweis}\n" if hinweis else "")
              + f"\n{webseite_teil}")

    antwort = ki.frage(system or SYSTEM_PROMPT, prompt)
    treffer = re.search(r"\{.*\}", antwort or "", re.S)
    if not treffer:
        return {"passt": False, "typ": "unsicher",
                "grund": "KI-Antwort nicht lesbar", "quelle": "ki"}
    try:
        daten = json.loads(treffer.group(0))
    except ValueError:
        return {"passt": False, "typ": "unsicher",
                "grund": "KI-Antwort nicht lesbar", "quelle": "ki"}
    return {"passt": bool(daten.get("passt")),
            "typ": str(daten.get("typ") or "unbekannt"),
            "grund": str(daten.get("grund") or ""),
            "quelle": "ki"}

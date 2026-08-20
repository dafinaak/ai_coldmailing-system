from dataclasses import dataclass, field
from pathlib import Path
import yaml

PFLICHTFELDER = ["name", "zielgruppe", "angebot", "tonalitaet",
                 "absender", "follow_up_tage", "test_empfaenger"]

@dataclass
class Kunde:
    name: str
    zielgruppe: dict
    angebot: str
    tonalitaet: str
    absender: str
    follow_up_tage: list
    test_empfaenger: list
    sperrliste: list = field(default_factory=list)  # Domains, nie anschreiben
    webseite: str = ""  # Firmen-Webseite, Basis fuer die Angebots-Ableitung im Web-Interface
    # Kern-Umbau (3-stufige Lead-Beschaffung, siehe pipeline.sourcing): beide
    # Felder sind hier bewusst OPTIONAL, damit alte Kunden-Dateien weiter
    # laden - "zielgruppe" bleibt als Feld erhalten, wird vom neuen Ablauf
    # aber nicht mehr genutzt. Fehlen sie, wenn der neue Ablauf tatsaechlich
    # laeuft, wirft pipeline.sourcing.source_leads() den klaren deutschen
    # Fehler (nicht hier - load_kunde() muss alte Dateien ohne diese Felder
    # weiter einlesen koennen).
    maps_suche: str = ""  # Google-Maps-Suchbegriff, z.B. "IT-Dienstleister Hannover"
    kontakt_rollen: list = field(default_factory=list)  # gewuenschte Jobtitel, z.B. [Geschäftsführer, IT-Leiter]
    # Lead-Qualitaets-Fix: Apollo liefert pro Firma teils mehrere Kontakte in
    # derselben/aehnlichen Rolle (im Probe-Lauf: 5x "Managing Director" bei
    # einer kleinen Firma) - so viele Leute in einer Firma anzuschreiben
    # verbrennt Budget und wirkt unseriös. Deckelt, wie viele Entscheider
    # PRO FIRMA maximal zu Leads werden (siehe pipeline.sourcing._entscheider_kontakte).
    # Default 1: standardmäßig genau EIN Entscheider pro Firma, damit nicht
    # mehrere Personen derselben kleinen Firma angeschrieben werden. Optional,
    # damit alte Kunden-Dateien ohne dieses Feld weiter laden.
    max_kontakte_pro_firma: int = 1
    # Kaskade (Chef-Vorgabe 23.07.2026): Reihenfolge der Anbieter-Stufen fuer
    # die Entscheider-Suche, z.B. ["prospeo", "hunter_dropcontact"] - Stufe 2
    # versucht nur die Firmen, bei denen Stufe 1 leer ausging; ganz am Ende
    # greift immer die info@-Regel. Leer = Standard (nur "hunter_dropcontact",
    # bis der Anbieter-Vergleich die Reihenfolge festgelegt hat). Gueltige
    # Stufennamen prueft pipeline.sourcing.source_leads() mit klarem Fehler.
    anbieter_reihenfolge: list = field(default_factory=list)
    # Olivers Regel (19.08.2026): Firmen, die SELBST Automatisierung
    # anbieten, sind Wettbewerber und duerfen in keine Kampagne. Mit true
    # prueft der Lauf jede Firma VOR jedem bezahlten Schritt
    # (Webseiten-Text + KI, siehe pipeline.branchen_filter) und schliesst
    # Treffer aus - gespeichert bleiben sie trotzdem. Standard false,
    # damit alte Kunden-Dateien ihr Verhalten behalten; das Formular
    # setzt es fuer neue Kampagnen selbst.
    wettbewerber_pruefung: bool = False
    # Versand-Einstellungen (14.08.2026). Vorher fragte das Formular in
    # Schritt 5 nach Postfach, Tageslimit, Zeitfenster und Wochentagen -
    # und KEINE dieser Antworten kam je bei Instantly an: die Kampagne
    # wurde ohne Absender-Postfach angelegt (konnte also gar nicht
    # senden), mit fest eingebautem Zeitplan. Die Felder stehen deshalb
    # jetzt in der Kundendatei und werden bei der Uebergabe mitgegeben.
    #
    # Alle optional mit sicheren Vorgaben, damit bestehende Kundendateien
    # unveraendert weiterladen (gleiches Prinzip wie die Felder darueber).
    versand_postfach: str = ""      # Absender-Postfach in Instantly (email_list)
    tageslimit: int = 20            # Mails pro Tag, Kampagnen-Ebene
    zeit_von: str = "08:00"
    zeit_bis: str = "19:00"
    # Kuerzel wie in der Oberflaeche: mo di mi do fr sa so.
    wochentage: list = field(default_factory=lambda: ["mo", "di", "mi", "do", "fr"])
    signatur: str = ""
    # "test": nur an test_empfaenger senden (Vorgabe, siehe
    # pipeline.__main__._versand_ausfuehren). "echt": an die gefundenen
    # Empfaenger. Fehlt das Feld, gilt "test" - eine alte Kundendatei darf
    # durch das blosse Vorhandensein dieses Codes nicht scharf werden.
    versand_modus: str = "test"

# Wochentag-Kuerzel -> Instantly-Tagesnummer (0=Sonntag ... 6=Samstag,
# live verifiziert, siehe pipeline.senders.instantly).
WOCHENTAG_NUMMER = {"so": "0", "mo": "1", "di": "2", "mi": "3",
                    "do": "4", "fr": "5", "sa": "6"}

VERSAND_MODI = ("test", "echt")


def load_kunde(path) -> Kunde:
    with open(path, encoding="utf-8") as f:
        daten = yaml.safe_load(f) or {}
    fehlend = [k for k in PFLICHTFELDER if k not in daten]
    if fehlend:
        raise ValueError(f"Pflichtfelder fehlen in {path}: {', '.join(fehlend)}")

    tage = daten["follow_up_tage"]
    if (not isinstance(tage, list) or len(tage) < 2
            or not all(isinstance(t, (int, float)) and not isinstance(t, bool) for t in tage)):
        raise ValueError(
            f"follow_up_tage in {path} muss eine Liste aus mindestens zwei Zahlen sein "
            f"(z.B. [3, 7]), gefunden: {tage!r}")
    if not all(tage[i] < tage[i + 1] for i in range(len(tage) - 1)):
        raise ValueError(
            f"follow_up_tage in {path} muss aufsteigend sortiert sein, jeder Tag also "
            f"später als der vorherige (z.B. [3, 7], nicht [7, 3] oder [3, 3]) - "
            f"gefunden: {tage!r}. Grund: Instantly zählt den Abstand jeweils zum "
            f"vorherigen Schritt, aus [a, b] wird also 'Follow-up 1 nach a Tagen, "
            f"Follow-up 2 nach (b - a) weiteren Tagen'.")

    empfaenger = daten["test_empfaenger"]
    if (not isinstance(empfaenger, list) or not empfaenger
            or not all(isinstance(e, str) for e in empfaenger)):
        raise ValueError(
            f"test_empfaenger in {path} muss eine nicht-leere Liste aus E-Mail-Adressen "
            f"(Strings) sein, gefunden: {empfaenger!r}")

    if "sperrliste" in daten and daten["sperrliste"] is not None:
        if not isinstance(daten["sperrliste"], list):
            raise ValueError(
                f"sperrliste in {path} muss, wenn vorhanden, eine Liste sein, "
                f"gefunden: {daten['sperrliste']!r}")

    modus = str(daten.get("versand_modus") or "test").strip().lower()
    if modus not in VERSAND_MODI:
        raise ValueError(
            f"versand_modus in {path} muss '{VERSAND_MODI[0]}' oder "
            f"'{VERSAND_MODI[1]}' sein, gefunden: {daten.get('versand_modus')!r}. "
            f"'test' schickt nur an test_empfaenger, 'echt' an die gefundenen "
            f"Empfaenger.")

    tage = daten.get("wochentage")
    if tage is not None:
        if not isinstance(tage, list) or not tage:
            raise ValueError(
                f"wochentage in {path} muss, wenn vorhanden, eine nicht-leere "
                f"Liste sein, gefunden: {tage!r}")
        unbekannt = [t for t in tage if str(t).strip().lower() not in WOCHENTAG_NUMMER]
        if unbekannt:
            raise ValueError(
                f"wochentage in {path} kennt nur {', '.join(WOCHENTAG_NUMMER)} - "
                f"unbekannt: {unbekannt!r}")

    return Kunde(**{k: daten[k] for k in PFLICHTFELDER},
                 sperrliste=daten.get("sperrliste") or [],
                 webseite=daten.get("webseite") or "",
                 maps_suche=daten.get("maps_suche") or "",
                 kontakt_rollen=daten.get("kontakt_rollen") or [],
                 max_kontakte_pro_firma=daten.get("max_kontakte_pro_firma") or 1,
                 anbieter_reihenfolge=daten.get("anbieter_reihenfolge") or [],
                 versand_postfach=daten.get("versand_postfach") or "",
                 tageslimit=int(daten.get("tageslimit") or 20),
                 zeit_von=str(daten.get("zeit_von") or "08:00"),
                 zeit_bis=str(daten.get("zeit_bis") or "19:00"),
                 wochentage=[str(t).strip().lower() for t in (tage or
                             ["mo", "di", "mi", "do", "fr"])],
                 signatur=daten.get("signatur") or "",
                 versand_modus=modus)

def lade_globale_sperrlisten_eintraege(daten_dir) -> list[dict]:
    """Liest alte Zeichenketten und neue strukturierte Sperrlisten-Eintraege."""
    pfad = Path(daten_dir) / "sperrliste-global.yaml"
    if not pfad.exists():
        return []
    inhalt = yaml.safe_load(pfad.read_text(encoding="utf-8")) or []
    if not isinstance(inhalt, list):
        raise ValueError(
            f"sperrliste-global.yaml in {pfad} ist falsch aufgebaut: erwartet wird eine "
            f"Liste von Domains (z.B. '- konkurrent-ki.de'), gefunden wurde "
            f"stattdessen: {type(inhalt).__name__}.")
    ergebnis = []
    for eintrag in inhalt:
        if isinstance(eintrag, str):
            ergebnis.append({
                "domain": eintrag, "reason": "", "comment": "", "legacy": True,
            })
            continue
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("domain"), str):
            raise ValueError(
                f"Ein Sperrlisten-Eintrag in {pfad} ist falsch aufgebaut."
            )
        reason = eintrag.get("reason") or ""
        comment = eintrag.get("comment") or ""
        if not isinstance(reason, str) or not isinstance(comment, str):
            raise ValueError(
                f"Ein Sperrlisten-Eintrag in {pfad} ist falsch aufgebaut."
            )
        ergebnis.append({
            "domain": eintrag["domain"], "reason": reason,
            "comment": comment, "legacy": False,
        })
    return ergebnis


def lade_globale_sperrliste(daten_dir) -> list[str]:
    """Gibt fuer Pipeline und Deduplizierung weiterhin nur Domain-Muster aus."""
    return [e["domain"] for e in lade_globale_sperrlisten_eintraege(daten_dir)]

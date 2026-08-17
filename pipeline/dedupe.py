import json
from pathlib import Path
from urllib.parse import urlparse

# Erweiterungspunkt: Hier koennte nach dem Dedupe eine externe
# E-Mail-Verifizierung (z.B. MillionVerifier) haengen. v1 nutzt die
# eingebaute Pruefung von Instantly beim Import.

def _bekannte_emails(kunde_laeufe_dir, ausser=None, alle_kampagnen_dir=None) -> set:
    """Alle Adressen, die wir schon einmal angeschrieben haben.

    kunde_laeufe_dir sind die Laeufe des eigenen Kunden (laeufe/<kunde>/).
    alle_kampagnen_dir ist, wenn angegeben, die Wurzel ueber allen Kunden
    (laeufe/) - dann zaehlen auch die Laeufe ANDERER Kampagnen als
    Vorgeschichte.

    Warum das noetig wurde (14.08.2026): Das Formular legt fuer jede
    Kampagne einen neuen Kunden an. Die eigene Vorgeschichte war damit
    immer leer, und zwei Kampagnen konnten denselben Geschaeftsfuehrer
    anschreiben, ohne dass es irgendwo auffiel. Es sind alles Kampagnen
    derselben Firma - ein Empfaenger soll dasselbe Angebot nicht zweimal
    von uns bekommen.

    Bewusst ein ausdruecklicher Parameter statt "eine Ebene hoeher raten":
    beim Raten griff der Suchlauf in Tests in fremde Ordner (erster Versuch
    genau daran gescheitert).

    ZAEHLEN TUT NUR, WAS AUCH RAUSGING. Ein Laufordner belegt erst dann,
    dass jemand angeschrieben wurde, wenn er als Kampagne uebergeben wurde
    (versand_komplett.json). Vorher hiess "steht in leads.json" schon
    "angeschrieben" - und weil das Formular beim Ausprobieren laufend neue
    Laeufe erzeugt, sperrte jeder Probelauf seine Firmen dauerhaft fuer
    alle spaeteren Kampagnen. Am 17.08.2026 kam ein Lauf so mit 23
    gefundenen Kontakten und NULL uebrigen heraus: alle 23 waren in
    frueheren Probelaeufen schon einmal gefunden - angeschrieben aber nie.
    """
    dateien = set(Path(kunde_laeufe_dir).glob("*/leads.json"))
    if alle_kampagnen_dir:
        dateien |= set(Path(alle_kampagnen_dir).glob("*/*/leads.json"))

    bekannte = set()
    for datei in sorted(dateien):
        if ausser is not None and datei.parent == Path(ausser):
            continue  # eigener, gerade laufender Lauf zaehlt nicht als "frueher"
        if not (datei.parent / "versand_komplett.json").exists():
            continue  # gefunden, aber nie uebergeben - also nie angeschrieben
        try:
            daten = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Ein kaputter alter Laufordner darf den neuen Lauf nicht
            # aufhalten - lieber diese eine Datei ueberspringen.
            continue
        # leads.json ist seit der "ohne_email"-Zaehlung ein Objekt
        # {"leads": [...], "ohne_email": n}; alte Laeufe koennen noch die
        # frühere, reine Listenform auf der Platte haben - beides lesen.
        eintraege = daten["leads"] if isinstance(daten, dict) else daten
        for eintrag in eintraege:
            bekannte.add(eintrag["email"].strip().lower())
    return bekannte

def _gesperrt(lead, sperrliste) -> bool:
    domains = {lead.email.split("@", 1)[-1]}
    if lead.website:
        netloc = urlparse(lead.website).netloc.lower()
        # Fallback for schemeless URLs: use text before first "/"
        if not netloc:
            netloc = lead.website.split("/")[0].lower()
        domains.add(netloc[4:] if netloc.startswith("www.") else netloc)
    for muster in sperrliste:
        muster = muster.strip().lower()
        for domain in domains:
            if muster.startswith("*.") and domain.endswith(muster[1:]):
                return True
            if domain == muster:
                return True
    return False

def dedupe(leads, kunde_laeufe_dir, sperrliste=(), aktueller_lauf=None,
           alle_kampagnen_dir=None):
    bekannte = _bekannte_emails(kunde_laeufe_dir, ausser=aktueller_lauf,
                                 alle_kampagnen_dir=alle_kampagnen_dir)
    gesehen, behalten, verworfen = set(), [], []
    for lead in leads:
        if _gesperrt(lead, sperrliste):
            verworfen.append({"email": lead.email, "grund": "Domain auf Sperrliste"})
        elif lead.email in gesehen:
            verworfen.append({"email": lead.email, "grund": "doppelt in dieser Liste"})
        # Wortlaut bewusst unveraendert, obwohl der Treffer seit 14.08.2026
        # auch aus einer ANDEREN Kampagne stammen kann - "Lauf" meint hier
        # jeden frueheren Durchgang.
        elif lead.email in bekannte:
            verworfen.append({"email": lead.email,
                              "grund": "bereits in früherem Lauf angeschrieben"})
        else:
            gesehen.add(lead.email)
            behalten.append(lead)
    return behalten, verworfen

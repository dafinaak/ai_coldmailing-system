"""Versand-Pakete schnueren - mit eingebauter Schutzregel.

Lehre aus Olivers Beschwerde vom 30.07.2026 ("Die Datenqualitaet ist
leider nicht gut"): Damals entstand das Paket direkt aus der gescrapten
Liste, die Branchen-Pruefung war nur ein grober Schluesselwort-Filter in
der Fusion. Ergebnis: Augenarzt, Zeitarbeit, Baufinanzierung,
Niederlassungen und moegliche Wettbewerber in einer Liste, die an Oliver
ging.

Diese Datei ist der strukturelle Riegel dagegen:

1. OHNE Branchenpruefung gibt es kein Paket - paket_schnueren() bricht
   mit UngepruefteListe ab, statt eine ungepruefte Liste zu liefern.
2. Es kommt NUR ins Paket, was drei Bedingungen erfuellt: geprueft UND
   als passend eingestuft UND mit gefundenem Ansprechpartner-Namen.
   Firmen ohne Pruefergebnis fallen durch (nicht "im Zweifel dabei").
3. Der Bericht zwingt zum Hinsehen: Er zaehlt jede Ausschluss-Ursache
   und liefert eine Stichprobe (Name + eingestufter Typ), damit vor dem
   Verschicken ein Mensch die Trefferqualitaet beurteilen kann.

Die Priorisierung innerhalb des Pakets bleibt wie im Bauplan
Leadquellen-Fundament (Schritt 6): bestaetigter Listen-Hinweis zuerst,
dann Datenreichtum (mehrere Quellen), dann vorhandene Telefonnummer.
"""


class UngepruefteListe(RuntimeError):
    """Kein Paket ohne Branchenpruefung (siehe Modul-Docstring)."""


def _schluessel(firma: dict) -> str:
    return firma.get("domain") or firma.get("name") or ""


def paket_schnueren(firmen: list, namenslauf: dict, branchenpruefung: dict,
                    groesse: int, *, gesperrt) -> tuple:
    """Gibt (paket, bericht) zurueck.

    branchenpruefung darf nicht leer sein - sonst UngepruefteListe.
    gesperrt (Domains, die ein Mensch gestrichen hat) ist ein PFLICHT-
    Argument, auch wenn es leer ist: Nach Olivers zweiter Beschwerde
    (30.07.2026, "Die Unternehmen, welche ich aussortiert hatte, duerfen
    nicht angeschrieben werden") darf die Sperrliste nicht vergessen
    werden koennen. Eine Sperre schlaegt JEDES andere Urteil - auch ein
    fachlich passendes Branchen-Ergebnis."""
    if not branchenpruefung:
        raise UngepruefteListe(
            "Keine Branchenprüfung vorhanden - es wird kein Paket gebaut. "
            "Bitte zuerst pipeline.branchen_filter über die Liste laufen "
            "lassen (Lehre aus Olivers Beschwerde vom 30.07.2026).")

    gesperrte = {str(d).strip().lower() for d in (gesperrt or set())}
    kandidaten = []
    zaehler = {"ohne_namen": 0, "ohne_pruefung": 0,
               "ausgeschlossen_branche": 0, "gesperrt": 0}
    for firma in firmen:
        s = _schluessel(firma)
        # Sperre zuerst: schlaegt jedes andere Urteil.
        if (firma.get("domain") or "").strip().lower() in gesperrte:
            zaehler["gesperrt"] += 1
            continue
        namens_eintrag = namenslauf.get(s) or {}
        pruef_eintrag = branchenpruefung.get(s)
        if namens_eintrag.get("ausgang") != "namen":
            zaehler["ohne_namen"] += 1
            continue
        if pruef_eintrag is None:
            zaehler["ohne_pruefung"] += 1
            continue
        if not pruef_eintrag.get("passt"):
            zaehler["ausgeschlossen_branche"] += 1
            continue
        rang = (1 if firma.get("gf_name_liste") else 0,
                len(firma.get("quellen") or []),
                1 if firma.get("telefon") else 0)
        kandidaten.append((rang, firma, namens_eintrag, pruef_eintrag))

    kandidaten.sort(key=lambda k: k[0], reverse=True)
    paket = []
    typen = {}
    for _, firma, namens_eintrag, pruef_eintrag in kandidaten[:groesse]:
        typ = pruef_eintrag.get("typ") or "unbekannt"
        typen[typ] = typen.get(typ, 0) + 1
        paket.append({**firma,
                      "personen": namens_eintrag.get("personen") or [],
                      "mail_domain": namens_eintrag.get("mail_domain"),
                      "branche_typ": typ,
                      "branche_grund": pruef_eintrag.get("grund", "")})

    bericht = {
        "kandidaten": len(kandidaten),
        "im_paket": len(paket),
        "reserve": max(0, len(kandidaten) - len(paket)),
        "typen": typen,
        "stichprobe": [{"name": f["name"], "typ": f["branche_typ"],
                        "grund": f["branche_grund"]}
                       for f in paket[:20]],
        **zaehler,
    }
    return paket, bericht

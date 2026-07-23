"""Anbieter-Vergleich fuer die Datenbeschaffung (Auftrag vom 23.07.2026).

Verglichen werden zwei Wege, die aus DERSELBEN Apify-Firmenliste die
richtige Ansprechperson mit gepruefter persoenlicher Mail holen sollen:

- Weg A: Apify/Google Maps -> Prospeo (Suche + Anreicherung, ein Anbieter)
- Weg B: Apify/Google Maps -> Hunter (findet Entscheider) -> Dropcontact
  (baut + prueft die persoenliche Mail) - der heute im Code aktive Weg.

ACHTUNG Benennung: pipeline/sourcing.py nennt Hunter->Dropcontact intern
noch "Weg A" (aeltere Zaehlung aus dem Kern-Umbau). Fuer den Vergleich gilt
die Benennung aus dem Auftrag: Weg A = Prospeo, Weg B = Hunter->Dropcontact.

Gemessen wird pro Firma und Weg:
- Wurde ein passender Entscheider gefunden (Rolle/Seniority)?
- Gibt es eine persoenliche, als zustellbar GEPRUEFTE Mail?
- Passt die Mail-Domain zur Firma (Warnzeichen fuer falsche Zuordnung)?
- Fehler/Zeitueberschreitungen, Dauer, geschaetzte Credits.

Die Einordnung "richtige Person / richtige Firma" kann nur ein Mensch
abschliessend beurteilen - der Bericht (bericht.md) stellt beide Wege je
Firma nebeneinander und laesst eine Spalte fuer die Handpruefung frei.

Der Lauf ist wiederaufnehmbar: Ergebnisse werden nach jeder Firma in
ergebnisse.json gesichert; ein erneuter Start mit demselben --lauf-Ordner
fragt bereits geprüfte Firmen nicht noch einmal an (schont die
Gratis-Kontingente; Firmen mit Status "fehler" werden erneut versucht).

Aufruf (Beispiel):
    python -m pipeline.vergleich \
        --firmen laeufe/demo-gmbh/20260721-145036/firmen.json \
        --lauf laeufe/vergleich-anbieter/lauf-1
Benoetigte .env-Schluessel: PROSPEO_API_KEY (Weg A), HUNTER_API_KEY und
DROPCONTACT_API_KEY (Weg B). Mit --weg a|b laesst sich ein einzelner Weg
nachziehen, falls erst ein Konto vorhanden ist.
"""
import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from pipeline.env import lade_dotenv, brauche_env
from pipeline.sourcing import (_qualifiziert, _qualifiziert_prospeo,
                               _nach_rollen_sortieren, _verifizierte_email)
from pipeline.sources.prospeo import ProspeoSource
from pipeline.sources.hunter import HunterSource
from pipeline.sources.dropcontact import DropcontactSource

STANDARD_ROLLEN = ["Geschäftsführer", "Inhaber"]
# Pro Firma werden hoechstens so viele passende Personen auf eine gepruefte
# Mail probiert - gleicher Deckel fuer beide Wege (Fairness). Fehlversuche
# kosten bei beiden Anbietern laut Doku keine Credits ("pay on success").
MAX_MAILVERSUCHE = 3

WEG_A_NAME = "Weg A (Prospeo)"
WEG_B_NAME = "Weg B (Hunter→Dropcontact)"
STATUS_REIHENFOLGE = ["gepruefte_mail", "person_ohne_gepruefte_mail",
                      "kein_entscheider", "kein_treffer", "keine_webseite",
                      "fehler", "uebersprungen"]
STATUS_TEXTE = {
    "gepruefte_mail": "geprüfte persönliche Mail",
    "person_ohne_gepruefte_mail": "Person gefunden, keine geprüfte Mail",
    "kein_entscheider": "Personen gefunden, aber kein passender Entscheider",
    "kein_treffer": "Anbieter kennt die Firma nicht",
    "keine_webseite": "Firma ohne Webseite/Domain",
    "fehler": "Fehler/Zeitüberschreitung",
    "uebersprungen": "nicht geprüft (kein Schlüssel)",
}


def _person_dict(vorname: str, nachname: str, titel: str) -> dict:
    return {"vorname": vorname, "nachname": nachname, "titel": titel}


def _domain_passt(email: str, domain: str):
    """True, wenn die Mail-Domain zur Firmen-Domain passt (auch Subdomain in
    beide Richtungen), False bei einer fremden Domain - das ist das
    automatische Warnzeichen fuer eine falsche Firmenzuordnung. None, wenn
    es nichts zu vergleichen gibt."""
    if not email or "@" not in email or not domain:
        return None
    mail_domain = email.rsplit("@", 1)[1].lower()
    domain = domain.lower()
    return (mail_domain == domain or mail_domain.endswith("." + domain)
            or domain.endswith("." + mail_domain))


def _basis(status, person=None, email=None, geprueft=False, pruefweg="",
           fehler=None, credits=0, dauer_s=0.0, domain=""):
    return {"status": status, "person": person, "email": email,
            "email_geprueft": geprueft, "pruefweg": pruefweg,
            "domain_passt": _domain_passt(email, domain),
            "fehler": fehler, "credits": credits,
            "dauer_s": round(dauer_s, 2)}


def weg_a_pruefen(firma: dict, rollen: list, prospeo,
                  max_mailversuche: int = MAX_MAILVERSUCHE) -> dict:
    """Weg A: Prospeo-Suche ueber die Firmen-Domain, dann Anreicherung der
    passendsten Entscheider bis zur ersten geprueften Mail."""
    domain = firma.get("domain") or ""
    start = time.monotonic()
    if not domain:
        return _basis("keine_webseite")
    try:
        personen = prospeo.entscheider_finden(domain)
        credits = 1 if personen else 0  # 1 Credit je Suche mit Treffer
        if not personen:
            return _basis("kein_treffer", dauer_s=time.monotonic() - start)
        passende = _nach_rollen_sortieren(
            [p for p in personen if _qualifiziert_prospeo(p, rollen)], rollen)
        if not passende:
            return _basis("kein_entscheider", credits=credits,
                          dauer_s=time.monotonic() - start)
        for person in passende[:max_mailversuche]:
            mail = prospeo.email_anreichern(person.get("person_id", ""))
            if mail:
                if not mail.get("schon_bezahlt"):
                    credits += 1  # 1 Credit je gefundener Mail
                return _basis(
                    "gepruefte_mail",
                    person=_person_dict(person.get("first_name", ""),
                                        person.get("last_name", ""),
                                        person.get("title", "")),
                    email=mail["email"], geprueft=True,
                    pruefweg=f"prospeo:{mail.get('verification_method', '')}",
                    credits=credits, dauer_s=time.monotonic() - start,
                    domain=domain)
        erste = passende[0]
        return _basis("person_ohne_gepruefte_mail",
                      person=_person_dict(erste.get("first_name", ""),
                                          erste.get("last_name", ""),
                                          erste.get("title", "")),
                      credits=credits, dauer_s=time.monotonic() - start)
    except Exception as fehler:
        return _basis("fehler", fehler=str(fehler),
                      dauer_s=time.monotonic() - start)


def weg_b_pruefen(firma: dict, rollen: list, hunter, dropcontact,
                  max_mailversuche: int = MAX_MAILVERSUCHE) -> dict:
    """Weg B: Hunter findet die Entscheider der Domain, Dropcontact baut und
    prueft die persoenliche Mail (Rueckfall: Hunters eigene, als 'valid'
    verifizierte Mail) - dieselbe Logik wie im Produktions-Ablauf
    (sourcing._entscheider_kontakte), hier aber mit sichtbarem Zwischenstand
    fuer den Vergleich."""
    domain = firma.get("domain") or ""
    start = time.monotonic()
    if not domain:
        return _basis("keine_webseite")
    try:
        personen = hunter.entscheider_finden(domain)
        # Schaetzung laut Hunter-Doku: 1 Credit je gefundener Mail der
        # Domain-Suche (keine Treffer = keine Credits). Am Konto gegenpruefen.
        credits = len(personen)
        if not personen:
            return _basis("kein_treffer", dauer_s=time.monotonic() - start)
        passende = _nach_rollen_sortieren(
            [p for p in personen if _qualifiziert(p, rollen)], rollen)
        if not passende:
            return _basis("kein_entscheider", credits=credits,
                          dauer_s=time.monotonic() - start)
        for person in passende[:max_mailversuche]:
            mail = _verifizierte_email(person, firma, dropcontact)
            if mail:
                if mail["quelle"] == "dropcontact":
                    credits += 1  # Dropcontact: 1 Credit je gefundener Mail
                    pruefweg = "dropcontact:nominative@pro"
                else:
                    pruefweg = "hunter:valid"
                return _basis(
                    "gepruefte_mail",
                    person=_person_dict(person.get("first_name", ""),
                                        person.get("last_name", ""),
                                        person.get("title", "")),
                    email=mail["wert"], geprueft=True, pruefweg=pruefweg,
                    credits=credits, dauer_s=time.monotonic() - start,
                    domain=domain)
        erste = passende[0]
        return _basis("person_ohne_gepruefte_mail",
                      person=_person_dict(erste.get("first_name", ""),
                                          erste.get("last_name", ""),
                                          erste.get("title", "")),
                      credits=credits, dauer_s=time.monotonic() - start)
    except Exception as fehler:
        return _basis("fehler", fehler=str(fehler),
                      dauer_s=time.monotonic() - start)


def _schluessel(firma: dict) -> str:
    return firma.get("domain") or firma.get("firma") or firma.get("name") or ""


def _weg_wiederverwendbar(eintrag) -> bool:
    """Ein frueheres Weg-Ergebnis wird wiederverwendet, ausser es fehlt, wurde
    uebersprungen (damals kein Schluessel) oder war ein Fehler - die beiden
    letzten Faelle sollen beim Fortsetzen erneut versucht werden."""
    return bool(eintrag) and eintrag.get("status") not in ("uebersprungen", "fehler")


def vergleich_ausfuehren(firmen: list, rollen: list, prospeo=None, hunter=None,
                         dropcontact=None, vorhandene=None,
                         fortschritt=print, nach_firma=None) -> list:
    """Fuehrt beide Wege ueber DIESELBEN Firmen aus. Quellen, die None sind,
    werden als "uebersprungen" markiert (so laesst sich ein Weg nachziehen,
    sobald sein Konto existiert). `vorhandene` sind die Ergebnisse eines
    frueheren Laufs - bereits geprüfte Firmen werden nicht erneut angefragt.
    `nach_firma` (optional) wird nach jeder Firma mit dem bisherigen
    Ergebnisstand aufgerufen - so geht bei einem Abbruch mitten im Lauf
    kein bereits bezahltes Anbieter-Ergebnis verloren."""
    alte = {_schluessel(e): e for e in (vorhandene or [])}
    ergebnisse = []
    for nr, firma in enumerate(firmen, start=1):
        alt = alte.get(_schluessel({"domain": firma.get("domain"),
                                    "name": firma.get("name")}), {})
        eintrag = {"firma": firma.get("name", ""),
                   "domain": firma.get("domain", ""),
                   "address": firma.get("address", "")}
        for weg, quelle, pruefen in (
                ("weg_a", prospeo,
                 lambda: weg_a_pruefen(firma, rollen, prospeo)),
                ("weg_b", hunter and dropcontact,
                 lambda: weg_b_pruefen(firma, rollen, hunter, dropcontact))):
            if _weg_wiederverwendbar(alt.get(weg)):
                eintrag[weg] = alt[weg]
            elif quelle:
                eintrag[weg] = pruefen()
            else:
                eintrag[weg] = _basis("uebersprungen")
        ergebnisse.append(eintrag)
        fortschritt(f"[{nr}/{len(firmen)}] {eintrag['domain'] or eintrag['firma']}: "
                    f"A={eintrag['weg_a']['status']} B={eintrag['weg_b']['status']}")
        if nach_firma:
            nach_firma(ergebnisse)
    return ergebnisse


def zusammenfassung(ergebnisse: list) -> dict:
    z = {"firmen_gesamt": len(ergebnisse)}
    for weg in ("weg_a", "weg_b"):
        werte = [e.get(weg) or {} for e in ergebnisse]
        gezaehlt = {status: sum(1 for w in werte if w.get("status") == status)
                    for status in STATUS_REIHENFOLGE}
        treffer = gezaehlt["gepruefte_mail"]
        quote = (treffer / len(ergebnisse) * 100) if ergebnisse else 0.0
        z[weg] = {**gezaehlt,
                  "quote_prozent": round(quote, 1),
                  "fremde_domain": sum(1 for w in werte
                                       if w.get("domain_passt") is False),
                  "credits_geschaetzt": sum(w.get("credits") or 0 for w in werte),
                  "dauer_s": round(sum(w.get("dauer_s") or 0 for w in werte), 1)}
    # Kaskaden-Auswertung (Chef-Vorgabe 23.07.2026: "wenn Stufe 1 nur 80 von
    # 100 findet, versucht Stufe 2 die restlichen 20"): Wie viele Firmen
    # bekommt die KOMBINATION beider Wege abgedeckt, und wer traegt was bei?
    def _hat_mail(e, weg):
        return (e.get(weg) or {}).get("status") == "gepruefte_mail"
    nur_a = sum(1 for e in ergebnisse if _hat_mail(e, "weg_a") and not _hat_mail(e, "weg_b"))
    nur_b = sum(1 for e in ergebnisse if _hat_mail(e, "weg_b") and not _hat_mail(e, "weg_a"))
    beide = sum(1 for e in ergebnisse if _hat_mail(e, "weg_a") and _hat_mail(e, "weg_b"))
    vereint = nur_a + nur_b + beide
    z["kaskade"] = {
        "mindestens_ein_weg": vereint,
        "quote_prozent": round(vereint / len(ergebnisse) * 100, 1) if ergebnisse else 0.0,
        "nur_weg_a": nur_a, "nur_weg_b": nur_b, "beide_wege": beide}
    return z


def _person_zelle(w: dict) -> str:
    p = w.get("person")
    if not p:
        return "—"
    name = f"{p.get('vorname', '')} {p.get('nachname', '')}".strip()
    return f"{name} ({p.get('titel') or 'ohne Titel'})"


def _mail_zelle(w: dict) -> str:
    if not w.get("email"):
        return STATUS_TEXTE.get(w.get("status", ""), "—")
    zusatz = "geprüft" if w.get("email_geprueft") else "UNGEPRÜFT"
    warnung = "" if w.get("domain_passt") in (True, None) else " ⚠ fremde Domain"
    return f"{w['email']} ({zusatz}, {w.get('pruefweg', '')}){warnung}"


def bericht_markdown(ergebnisse: list, z: dict, stand: str = "") -> str:
    stand = stand or datetime.now().strftime("%d.%m.%Y %H:%M")
    zeilen = [
        "# Anbieter-Vergleich: Weg A (Prospeo) gegen Weg B (Hunter→Dropcontact)",
        "",
        f"Stand: {stand}. Beide Wege bekamen dieselben {z['firmen_gesamt']} "
        "Firmen aus derselben Apify/Google-Maps-Liste.",
        "",
        "## Ergebnis in Zahlen",
        "",
        f"| Kennzahl | {WEG_A_NAME} | {WEG_B_NAME} |",
        "|---|---|---|",
    ]
    def paar(schluessel):
        return z["weg_a"].get(schluessel, 0), z["weg_b"].get(schluessel, 0)
    kennzahlen = [
        ("Geprüfte persönliche Mail gefunden", "gepruefte_mail"),
        ("**Trefferquote**", None),
        ("Person gefunden, aber keine geprüfte Mail", "person_ohne_gepruefte_mail"),
        ("Personen gefunden, aber kein passender Entscheider", "kein_entscheider"),
        ("Anbieter kennt die Firma nicht", "kein_treffer"),
        ("Firma ohne Webseite/Domain", "keine_webseite"),
        ("Fehler/Zeitüberschreitungen", "fehler"),
        ("Noch nicht geprüft (kein Schlüssel)", "uebersprungen"),
        ("⚠ Mail mit fremder Domain (mögliche Falschzuordnung)", "fremde_domain"),
        ("Credits verbraucht (Schätzung, am Konto gegenprüfen)", "credits_geschaetzt"),
        ("Dauer gesamt (Sekunden)", "dauer_s"),
    ]
    for beschriftung, schluessel in kennzahlen:
        if schluessel is None:
            a, b = z["weg_a"]["quote_prozent"], z["weg_b"]["quote_prozent"]
            zeilen.append(f"| {beschriftung} | **{a} %** | **{b} %** |")
        else:
            a, b = paar(schluessel)
            zeilen.append(f"| {beschriftung} | {a} | {b} |")
    k = z.get("kaskade") or {}
    zeilen += [
        "",
        "Trefferquote = Anteil der Firmen mit geprüfter persönlicher Mail.",
        "Credits sind Schätzungen nach den Doku-Regeln der Anbieter; der",
        "echte Verbrauch steht im jeweiligen Anbieter-Konto.",
        "",
        "## Kaskade: Was bringt die Kombination beider Wege?",
        "",
        f"Mindestens ein Weg fand eine geprüfte persönliche Mail bei "
        f"**{k.get('mindestens_ein_weg', 0)} von {z['firmen_gesamt']} Firmen "
        f"({k.get('quote_prozent', 0.0)} %)** — davon nur Weg A: "
        f"{k.get('nur_weg_a', 0)}, nur Weg B: {k.get('nur_weg_b', 0)}, beide: "
        f"{k.get('beide_wege', 0)}. Die „nur\"-Zahlen zeigen, wie viele "
        f"Firmen eine zweite Stufe zusätzlich retten würde; für den Rest "
        f"bliebe die info@-Regel.",
        "",
        "## Firmen im Einzelnen",
        "",
        "Die Spalte „Manuelle Prüfung“ ist bewusst leer: Ob die gefundene",
        "Person wirklich die Geschäftsführung DIESER Firma ist, kann nur ein",
        "Mensch beurteilen (kurzer Blick auf Webseite/Impressum).",
        "",
        f"| Firma | {WEG_A_NAME}: Person | {WEG_A_NAME}: Mail | "
        f"{WEG_B_NAME}: Person | {WEG_B_NAME}: Mail | Manuelle Prüfung |",
        "|---|---|---|---|---|---|",
    ]
    for e in ergebnisse:
        a, b = e.get("weg_a") or {}, e.get("weg_b") or {}
        zeilen.append(
            f"| {e.get('firma') or e.get('domain')} ({e.get('domain', '')}) "
            f"| {_person_zelle(a)} | {_mail_zelle(a)} "
            f"| {_person_zelle(b)} | {_mail_zelle(b)} |  |")
    fehlerhafte = [(e, w, e.get(w) or {}) for e in ergebnisse for w in ("weg_a", "weg_b")
                   if (e.get(w) or {}).get("status") == "fehler"]
    if fehlerhafte:
        zeilen += ["", "## Fehlerdetails", ""]
        for e, weg, w in fehlerhafte:
            name = WEG_A_NAME if weg == "weg_a" else WEG_B_NAME
            zeilen.append(f"- {e.get('domain') or e.get('firma')} — {name}: "
                          f"{w.get('fehler', '')}")
    return "\n".join(zeilen) + "\n"


def lauf_speichern(lauf_dir, ergebnisse: list, z: dict):
    lauf_dir = Path(lauf_dir)
    lauf_dir.mkdir(parents=True, exist_ok=True)
    (lauf_dir / "ergebnisse.json").write_text(
        json.dumps({"zusammenfassung": z, "firmen": ergebnisse},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (lauf_dir / "bericht.md").write_text(bericht_markdown(ergebnisse, z),
                                         encoding="utf-8")


def lauf_laden(lauf_dir) -> list:
    pfad = Path(lauf_dir) / "ergebnisse.json"
    if not pfad.exists():
        return []
    return (json.loads(pfad.read_text(encoding="utf-8")) or {}).get("firmen", [])


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Anbieter-Vergleich: Weg A (Prospeo) gegen Weg B "
                    "(Hunter→Dropcontact) ueber dieselbe Apify-Firmenliste.")
    parser.add_argument("--firmen", required=True,
                        help="Pfad zu einer firmen.json aus einem Apify-Lauf")
    parser.add_argument("--lauf", required=True,
                        help="Ausgabe-Ordner; existierende ergebnisse.json wird "
                             "fortgesetzt statt erneut Guthaben zu verbrauchen")
    parser.add_argument("--weg", choices=["a", "b", "beide"], default="beide")
    parser.add_argument("--rollen", default=",".join(STANDARD_ROLLEN),
                        help="Gewuenschte Rollen, kommagetrennt")
    parser.add_argument("--limit", type=int, default=None,
                        help="Hoechstens so viele Firmen pruefen")
    args = parser.parse_args(argv)

    lade_dotenv()
    prospeo = hunter = dropcontact = None
    if args.weg in ("a", "beide"):
        brauche_env("PROSPEO_API_KEY")
        prospeo = ProspeoSource(os.environ["PROSPEO_API_KEY"])
    if args.weg in ("b", "beide"):
        brauche_env("HUNTER_API_KEY")
        brauche_env("DROPCONTACT_API_KEY")
        hunter = HunterSource(os.environ["HUNTER_API_KEY"])
        dropcontact = DropcontactSource(os.environ["DROPCONTACT_API_KEY"])

    firmen = json.loads(Path(args.firmen).read_text(encoding="utf-8"))
    if args.limit:
        firmen = firmen[:args.limit]
    rollen = [r.strip() for r in args.rollen.split(",") if r.strip()]
    vorhandene = lauf_laden(args.lauf)
    if vorhandene:
        print(f"Setze bestehenden Lauf fort ({len(vorhandene)} Firmen bereits "
              f"gespeichert) - nur Fehlendes wird neu angefragt.")

    ergebnisse = vergleich_ausfuehren(
        firmen, rollen, prospeo=prospeo, hunter=hunter, dropcontact=dropcontact,
        vorhandene=vorhandene,
        # Nach jeder Firma sichern: ein Abbruch mitten im Lauf verliert kein
        # bereits bezahltes Anbieter-Ergebnis.
        nach_firma=lambda erg: lauf_speichern(args.lauf, erg, zusammenfassung(erg)))
    z = zusammenfassung(ergebnisse)
    lauf_speichern(args.lauf, ergebnisse, z)
    print(f"\nFertig: {z['firmen_gesamt']} Firmen. "
          f"Weg A: {z['weg_a']['quote_prozent']} % geprüfte Mails, "
          f"Weg B: {z['weg_b']['quote_prozent']} %. "
          f"Bericht: {Path(args.lauf) / 'bericht.md'}")


if __name__ == "__main__":
    main()

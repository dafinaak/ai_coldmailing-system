"""Grosslauf ueber eine importierte Firmenliste (Bauplan 2026-07-27).

Olivers Auftrag: Fuer jede Firma der Liste den Entscheider mit persoenlicher,
GEPRUEFTER E-Mail ermitteln. Kaskade: Prospeo (Personen-Suche) -> Impressum
(KI liest den Chef-Namen, Dropcontact baut/prueft die Mail) -> info@ als
letzter Rueckfall (hier ohne Hunter-Konto ungeprueft, wird im Bericht so
gekennzeichnet - geprueft wird VOR einem Versand). Es wird nichts versendet.

Der Lauf ist wiederaufnehmbar: nach jeder Firma wird gespeichert; ein
Neustart mit demselben --lauf-Ordner ueberspringt fertige Firmen und
versucht nur "fehler"-Firmen erneut. Der Bericht entsteht im von Oliver
bestellten Format: Gesamtzahl, Anzahl/Quote persoenlicher Mails, Liste der
Firmen OHNE persoenliche Mail samt Telefonnummer (fuer Anruf/Brief), dazu
die Abschnitte "Zentralen ausserhalb der Region" und "moegliche Dubletten"
(Olivers Hinweis: manche Organisationen nutzen eine URL fuer alle
Standorte, andere je Standort eine eigene).

Aufruf:
    python -m pipeline.grosslauf --firmen laeufe/plr30-39/firmen.json \
        --lauf laeufe/plr30-39/lauf-1 [--limit N]
Benoetigt: PROSPEO_API_KEY, DROPCONTACT_API_KEY und einen KI-Schluessel
(ANTHROPIC_API_KEY oder OPENROUTER_API_KEY) in der .env.
"""
import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from pipeline.config import Kunde
from pipeline.env import lade_dotenv, brauche_env, brauche_env_eines_von
from pipeline.sourcing import source_leads
from pipeline.sources.prospeo import ProspeoSource
from pipeline.sources.dropcontact import DropcontactSource
from pipeline.sources.impressum import ImpressumQuelle

REIHENFOLGE = ["prospeo", "impressum"]
PERSOENLICH = "mit_entscheider"

# Namenszusaetze, die fuer den Dubletten-Vergleich keinen Unterschied machen.
_NAMENS_RAUSCHEN = {"gmbh", "mbh", "ag", "kg", "ug", "gbr", "ohg", "co", "e.k.",
                    "ek", "it", "edv", "systemhaus", "systeme", "service",
                    "services", "solutions", "dienstleister", "hannover",
                    "niederlassung", "the", "die", "der", "das", "&", "und", "+"}


class ListenQuelle:
    """Ersatz fuer die Apify-Suche: liefert eine fertige Firmenliste, damit
    source_leads() unveraendert ueber importierte Listen laufen kann."""
    def __init__(self, firmen):
        self._firmen = firmen
    def search(self, suchbegriff, limit):
        return self._firmen[:limit]


def _namenskern(name: str) -> str:
    """Erstes aussagekraeftiges Namenswort als grober Dubletten-Anker:
    Filialisten heissen typischerweise "<Marke> <Stadt/Zusatz>" (Bechtle
    Hannover / Bechtle Braunschweig) - die Marke vorn ist der gemeinsame
    Kern. Bewusst grob: Die Gruppen werden nur GEMELDET, ein Mensch
    entscheidet (Olivers Regel: nicht doppelt anschreiben)."""
    for wort in re.sub(r"[^\wäöüß ]", " ", (name or "").lower()).split():
        if wort not in _NAMENS_RAUSCHEN and len(wort) >= 3:
            return wort
    return ""


def dubletten_finden(firmen: list) -> list:
    """Gruppen moeglicher Dubletten: gleiche Domain ODER gleicher
    Namenskern trotz verschiedener Domains (Filialisten mit regionalen
    URLs). Es wird nur GEMELDET, nicht geloescht - die Entscheidung, wer
    die Zentrale ist, trifft ein Mensch."""
    doppelte, gesehen = [], set()
    def sammeln(schluessel_von):
        gruppen = {}
        for f in firmen:
            schluessel = schluessel_von(f)
            if schluessel:
                gruppen.setdefault(schluessel, []).append(f)
        for mitglieder in gruppen.values():
            if len(mitglieder) > 1:
                kennung = frozenset(id(m) for m in mitglieder)
                if kennung not in gesehen:
                    gesehen.add(kennung)
                    doppelte.append(mitglieder)
    sammeln(lambda f: f.get("domain", ""))
    sammeln(lambda f: _namenskern(f.get("name", "")))
    return doppelte


def _schluessel(f: dict) -> str:
    return f.get("domain") or f.get("name") or ""


def lauf_ausfuehren(firmen: list, kunde, prospeo, dropcontact, impressum,
                    vorhandene=None, fortschritt=print, nach_firma=None) -> list:
    """Fuehrt die Kaskade Firma fuer Firma aus (je Firma ein eigener
    source_leads-Aufruf mit Ein-Firmen-Liste - so bleibt der Lauf nach
    jeder Firma speicherbar und wiederaufnehmbar). Firmen mit frueherem
    Ergebnis werden uebersprungen; nur "fehler" wird erneut versucht."""
    alte = {_schluessel(e): e for e in (vorhandene or [])}
    ergebnisse = []
    for nr, firma in enumerate(firmen, start=1):
        alt = alte.get(_schluessel(firma))
        if alt and alt.get("ausgang") != "fehler":
            ergebnisse.append(alt)
            continue
        leads, _, mit_ausgang = source_leads(
            kunde, 1, "", "", "", apify_source=ListenQuelle([firma]),
            hunter_source=object(),  # kein Hunter: info@ bleibt ungeprueft
            dropcontact_source=dropcontact, prospeo_source=prospeo,
            impressum_quelle=impressum)
        eintrag = {**mit_ausgang[0],
                   "leads": [l.__dict__ for l in leads]}
        ergebnisse.append(eintrag)
        fortschritt(f"[{nr}/{len(firmen)}] {_schluessel(firma)}: "
                    f"{eintrag.get('ausgang')} "
                    f"({eintrag.get('stufe') or '-'})")
        if nach_firma:
            nach_firma(ergebnisse)
    return ergebnisse


def zusammenfassung(ergebnisse: list) -> dict:
    z = {"firmen_gesamt": len(ergebnisse)}
    z["persoenliche_mail"] = sum(1 for e in ergebnisse if e.get("ausgang") == PERSOENLICH)
    z["quote_prozent"] = round(z["persoenliche_mail"] / len(ergebnisse) * 100, 1) \
        if ergebnisse else 0.0
    z["info_ungeprueft"] = sum(1 for e in ergebnisse
                               if e.get("ausgang") == "info_fallback"
                               and "info_pruefstatus" not in e)
    z["ohne_kontakt"] = sum(1 for e in ergebnisse if e.get("ausgang") in
                            ("kein_entscheider", "kein_treffer",
                             "keine_webseite", "info_ungueltig", "fehler"))
    je_stufe = {}
    for e in ergebnisse:
        if e.get("ausgang") == PERSOENLICH:
            je_stufe[e.get("stufe") or "?"] = je_stufe.get(e.get("stufe") or "?", 0) + 1
    z["je_stufe"] = je_stufe
    z["fehler"] = sum(1 for e in ergebnisse if e.get("ausgang") == "fehler")
    z["ausserhalb_region"] = sum(1 for e in ergebnisse if e.get("ausserhalb_region"))
    return z


def bericht_markdown(ergebnisse: list, z: dict, dubletten: list,
                     stand: str = "") -> str:
    stand = stand or datetime.now().strftime("%d.%m.%Y %H:%M")
    zeilen = [
        "# Großlauf-Bericht: persönliche Entscheider-Mails",
        "",
        f"Stand: {stand}. Es wurde nichts versendet.",
        "",
        "## Ergebnis in Zahlen",
        "",
        f"- Firmen gesamt: **{z['firmen_gesamt']}**",
        f"- Persönliche, geprüfte E-Mail gefunden: **{z['persoenliche_mail']} "
        f"({z['quote_prozent']} %)**",
        f"  - davon je Stufe: " + (", ".join(
            f"{name}: {anzahl}" for name, anzahl in sorted(z["je_stufe"].items()))
            or "—"),
        f"- Nur info@-Adresse (noch ungeprüft, Prüfung vor Versand): "
        f"{z['info_ungeprueft']}",
        f"- Ohne nutzbaren Kontakt: {z['ohne_kontakt']} (davon Fehler: {z['fehler']})",
        f"- Zentralen außerhalb der Region (werden mitgeführt): "
        f"{z['ausserhalb_region']}",
        "",
        "## Firmen ohne persönliche Mail (für Anruf oder Brief)",
        "",
        "| Firma | Domain | Telefon | Stand |",
        "|---|---|---|---|",
    ]
    for e in ergebnisse:
        if e.get("ausgang") == PERSOENLICH:
            continue
        zeilen.append(f"| {e.get('name', '')} | {e.get('domain', '')} "
                      f"| {e.get('telefon') or '—'} "
                      f"| {e.get('ausgang', '')} |")
    ausserhalb = [e for e in ergebnisse if e.get("ausserhalb_region")]
    zeilen += ["", "## Zentralen außerhalb der Region (nicht vergessen)", ""]
    if ausserhalb:
        for e in ausserhalb:
            zeilen.append(f"- {e.get('name', '')} ({e.get('domain', '')}, "
                          f"PLZ {e.get('plz') or '?'}) — {e.get('ausgang', '')}")
    else:
        zeilen.append("Keine.")
    zeilen += ["", "## Mögliche Dubletten (bitte von Hand entscheiden)", ""]
    if dubletten:
        for gruppe in dubletten:
            zeilen.append("- " + " / ".join(
                f"{m.get('name', '')} ({m.get('domain', '')})" for m in gruppe))
    else:
        zeilen.append("Keine gefunden.")
    return "\n".join(zeilen) + "\n"


def lauf_speichern(lauf_dir, ergebnisse, dubletten):
    lauf_dir = Path(lauf_dir)
    lauf_dir.mkdir(parents=True, exist_ok=True)
    z = zusammenfassung(ergebnisse)
    (lauf_dir / "ergebnisse.json").write_text(
        json.dumps({"zusammenfassung": z, "firmen": ergebnisse},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (lauf_dir / "bericht.md").write_text(
        bericht_markdown(ergebnisse, z, dubletten), encoding="utf-8")


def lauf_laden(lauf_dir) -> list:
    pfad = Path(lauf_dir) / "ergebnisse.json"
    if not pfad.exists():
        return []
    return (json.loads(pfad.read_text(encoding="utf-8")) or {}).get("firmen", [])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--firmen", required=True)
    parser.add_argument("--lauf", required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    lade_dotenv()
    brauche_env("PROSPEO_API_KEY")
    brauche_env("DROPCONTACT_API_KEY")
    brauche_env_eines_von("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY")

    from pipeline.ki import KI
    firmen = json.loads(Path(args.firmen).read_text(encoding="utf-8"))
    if args.limit:
        firmen = firmen[:args.limit]
    kunde = Kunde(name="Großlauf", zielgruppe={}, angebot="-", tonalitaet="-",
                  absender="-", follow_up_tage=[3, 7],
                  test_empfaenger=["test@example.com"],
                  maps_suche="(Liste)", kontakt_rollen=["Geschäftsführer", "Inhaber"],
                  anbieter_reihenfolge=REIHENFOLGE)
    prospeo = ProspeoSource(os.environ["PROSPEO_API_KEY"], wartezeit=20)
    dropcontact = DropcontactSource(os.environ["DROPCONTACT_API_KEY"])
    impressum = ImpressumQuelle(KI())
    dubletten = dubletten_finden(firmen)
    vorhandene = lauf_laden(args.lauf)
    if vorhandene:
        print(f"Setze bestehenden Lauf fort ({len(vorhandene)} Firmen gespeichert).")
    ergebnisse = lauf_ausfuehren(
        firmen, kunde, prospeo, dropcontact, impressum, vorhandene=vorhandene,
        nach_firma=lambda erg: lauf_speichern(args.lauf, erg, dubletten))
    lauf_speichern(args.lauf, ergebnisse, dubletten)
    z = zusammenfassung(ergebnisse)
    print(f"\nFertig: {z['firmen_gesamt']} Firmen, {z['persoenliche_mail']} "
          f"persönliche Mails ({z['quote_prozent']} %). "
          f"Bericht: {Path(args.lauf) / 'bericht.md'}")


if __name__ == "__main__":
    main()

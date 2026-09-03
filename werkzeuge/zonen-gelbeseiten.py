#!/usr/bin/env python3
"""Prove e vogel: sa firma te reja sjell Gelbe Seiten mbi nje zone.

Pse ekziston (vendim i Dafines, 01.09.2026 - opsioni C): testi i burimeve
me 20.08.2026 tregoi qe Gelbe Seiten njeh rreth 20% firma qe Maps s'i ka
fare. Por sa kushton kjo per zonat tona s'e dinim, sepse Gelbe Seiten
s'ka rrjedhur kurre mbi nje zone. Kjo vegel e mat me shifra, mbi nje zone
te vetme, me nje shpenzim te vogel dhe te parashikuar - pastaj vendos
Dafina a shtrihet te zonat tjera.

Matet mbi nje zone ku Maps-i ka rrjedhur TASHME (34 Kassel, 33 Bielefeld,
32 Herford). Keshtu "e re" do te thote vertet "Maps s'e kishte", dhe nuk
paguhet asnje vrapim Maps per hir te proves.

CMIMI (llogaria eshte plani STARTER / tarifa BRONZE nga 02.09.2026):
    Gelbe Seiten  0.00178  USD / rezultat
    Google Maps   0.003    USD / vend
Pra Gelbe Seiten kushton rreth 60% te cmimit te Maps-it per rezultat.

SIGURI: pa argumentin --nise kjo vegel NUK shpenzon asgje. Ajo vetem
llogarit dhe e shtyp sa do te kushtonte. Vetem --nise e nis vertet.

    python werkzeuge/zonen-gelbeseiten.py --zone=34            # prove e thate
    python werkzeuge/zonen-gelbeseiten.py --zone=34 --nise     # niset vertet
    python werkzeuge/zonen-gelbeseiten.py --zone=34 --fjale=3 --faqe=2 --nise

ASNJE email nuk dergohet. Instantly nuk preket fare.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline.env import lade_dotenv  # noqa: E402

lade_dotenv(PROJEKT / ".env")

import os  # noqa: E402

from pipeline import zonen  # noqa: E402
# E njejta rregull "e njohur / e re" si te raporti i mbledhjes: domain,
# perndryshe emri. Nese kjo vegel do te numeronte ndryshe, prova do te
# jepte nje perqindje qe s'do te perputhej me asnje numer tjeter tonin.
from pipeline.firmen_sammeln import _bestand_schluessel  # noqa: E402
from pipeline.sources.gelbe_seiten import GelbeSeitenQuelle  # noqa: E402

PREIS_PRO_ERGEBNIS = 0.00178   # tarifa BRONZE (plani STARTER, nga 02.09.2026)
PREIS_MAPS_PRO_ORT = 0.003     # per krahasim ne raportin perfundimtar

# Sa jep nje faqe e Gelbe Seiten-it (vezhguar te mini-vrapimi i 29.07.2026).
ERGEBNISSE_PRO_SEITE = 10

# Frenat e proves. Te vegjel me qellim: prova duhet te jape nje pergjigje,
# jo nje liste te plote.
FJALE_STANDARD = 3
FAQE_STANDARD = 2


def log(*teile):
    print(f"[{datetime.now():%H:%M:%S}]", *teile, flush=True)


def argumente():
    nummer, fjale, faqe, nise = None, FJALE_STANDARD, FAQE_STANDARD, False
    for arg in sys.argv[1:]:
        if arg.startswith("--zone="):
            nummer = arg.split("=", 1)[1]
        elif arg.startswith("--fjale="):
            fjale = int(arg.split("=", 1)[1])
        elif arg.startswith("--faqe="):
            faqe = int(arg.split("=", 1)[1])
        elif arg == "--nise":
            nise = True
        else:
            sys.exit(f"Argument i panjohur: {arg}")
    if nummer is None:
        sys.exit(f"Duhet --zone= nga: {', '.join(sorted(zonen.ZONEN))}")
    if fjale < 1 or fjale > len(zonen.SUCHBEGRIFFE):
        sys.exit(f"--fjale duhet te jete 1..{len(zonen.SUCHBEGRIFFE)}")
    if faqe < 1 or faqe > 10:
        sys.exit("--faqe duhet te jete 1..10")
    return nummer, fjale, faqe, nise


def main():
    nummer, fjale, faqe, nise = argumente()
    try:
        zone = zonen.zone(nummer)
    except KeyError as gabim:
        sys.exit(str(gabim))

    begriffe = zonen.SUCHBEGRIFFE[:fjale]
    kodet = set(zonen.plz_kodes(nummer))
    max_ergebnisse = fjale * faqe * ERGEBNISSE_PRO_SEITE
    max_kosten = max_ergebnisse * PREIS_PRO_ERGEBNIS

    log("=" * 62)
    log(f"ZONA {nummer} ({zone['stadt']}) - prove Gelbe Seiten")
    log("=" * 62)
    log(f"Qyteti i kerkimit:  {zone['stadt']}   (jo 'Deutschland' - do te "
        f"kushtonte shume here me shume)")
    log(f"Fjale kerkimi:      {fjale}  {begriffe}")
    log(f"Faqe per fjale:     {faqe}")
    log(f"Maksimumi rezultat: {max_ergebnisse}  (~{ERGEBNISSE_PRO_SEITE}/faqe)")
    log(f"Kosto maksimale:    {max_kosten:.2f} USD  "
        f"({PREIS_PRO_ERGEBNIS} USD/rezultat, tarifa BRONZE)")
    log(f"Kode postare zone:  {len(kodet)}")

    if not nise:
        log("-" * 62)
        log("PROVE E THATE - s'u shpenzua asgje, s'u thirr Apify fare.")
        log("Per ta nisur vertet: shto --nise")
        log("=" * 62)
        return

    token = os.environ.get("APIFY_API_KEY")
    if not token:
        sys.exit("Mungon APIFY_API_KEY te .env")

    log("-" * 62)
    log("PO NISET VERTET - ky vrapim shpenzon nga buxheti i Apify-t.")

    quelle = GelbeSeitenQuelle(token)
    roh, fehler = [], {}
    for begriff in begriffe:
        try:
            gefunden = quelle.search(begriff, zone["stadt"], faqe)
            log(f"  {begriff}: {len(gefunden)} rezultate")
            roh.extend(gefunden)
        except Exception as f:                       # noqa: BLE001
            fehler[begriff] = str(f)
            log(f"  {begriff}: DESHTOI - {f}")

    ordner = PROJEKT / "laeufe/leadquellen" / \
        f"zona{nummer}-gelbeseiten-{datetime.now():%Y-%m-%d}"
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "00-gelbeseiten-roh.json").write_text(
        json.dumps(roh, ensure_ascii=False, indent=1), encoding="utf-8")

    # Nje firme mund te dale te disa fjale kerkimi - numerohet nje here.
    einzeln, gesehen = [], set()
    for firma in roh:
        kennung = (firma.get("domain") or firma.get("name") or "").lower()
        if kennung and kennung not in gesehen:
            gesehen.add(kennung)
            einzeln.append(firma)

    in_zone = [f for f in einzeln if f.get("plz") in kodet]
    bekannt = _bestand_schluessel(str(PROJEKT))
    neu = [f for f in in_zone
           if (f.get("domain") or f.get("name") or "").lower() not in bekannt]
    mit_email = [f for f in neu if f.get("vorhandene_email")]

    kosten = len(roh) * PREIS_PRO_ERGEBNIS
    bericht = {
        "zone": nummer, "stadt": zone["stadt"],
        "suchbegriffe": begriffe, "seiten_je_begriff": faqe,
        "ergebnisse_bezahlt": len(roh), "kosten_usd": round(kosten, 4),
        "firmen_einzeln": len(einzeln), "firmen_in_zone": len(in_zone),
        "firmen_neu": len(neu), "davon_mit_email": len(mit_email),
        "fehler": fehler,
    }
    (ordner / "firmen.json").write_text(
        json.dumps(neu, ensure_ascii=False, indent=1), encoding="utf-8")
    (ordner / "probebericht.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=1), encoding="utf-8")

    log("=" * 62)
    log(f"Rezultate te paguara:      {len(roh)}   = {kosten:.2f} USD")
    log(f"Firma te vecanta:          {len(einzeln)}")
    log(f"Prej tyre brenda zones:    {len(in_zone)}")
    log(f"Prej tyre TE REJA per ne:  {len(neu)}")
    log(f"Prej te rejave me email:   {len(mit_email)}  "
        f"(Maps s'kthen kurre email)")
    if neu:
        log(f"-> {kosten / len(neu):.4f} USD per firme te re")
        log(f"   Maps per krahasim: {PREIS_MAPS_PRO_ORT} USD per vend te gjetur")
    else:
        log("-> asnje firme e re: Gelbe Seiten s'ka cka shton ne kete zone")
    log(f"U ruajt te: {ordner}")
    log("=" * 62)
    log("Asnje email s'u dergua. Instantly s'u prek.")


if __name__ == "__main__":
    main()

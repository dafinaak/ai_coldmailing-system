#!/usr/bin/env python3
"""Lista perfundimtare e Zones 32 ne formatin IT-Liste-Emails-FERTIG,
plus kolonat qe i kerkoi Dafina: Position, lokacioni dhe burimi per
cdo fushe.

Merr rezultatin e gatshem te Dropcontact-it (ergebnisse.json) dhe
Anrede-n nga dosja qe e ndertoi anrede_spalte.aus_lauf(), qe teksti i
pershendetjes te jete saktesisht i njejti si te lista e vjeter.
"""
import glob
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJEKT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJEKT))

from pipeline import zonen  # noqa: E402
from pipeline.anrede_spalte import baue_anrede  # noqa: E402
from pipeline.config import lade_globale_sperrlisten_eintraege  # noqa: E402
from pipeline.sperrliste_pruefung import (  # noqa: E402
    gesperrte_domains, ist_gesperrt)

# "quellen" jane dosjet e mbledhjes nga vijne kodi postar, qyteti dhe
# telefonat. DY burime per zone: Maps dhe Overpass. Gelbe Seiten u hoq me
# 04.09.2026 me urdher te Dafines (zero kontakte mbi te teta zonat).
# "lauf" nuk perdoret me per lexim - lista i bashkon VETE te gjitha
# dosjet "zona<NR>-dropcontact-*" te zones.
ZONEN = {
    "32": {"lauf": "zona32-dropcontact-2026-08-21",
           "quellen": ["zona32-herford-2026-08-21",
                       "zona32-overpass-2026-08-21"]},
    "33": {"lauf": "zona33-dropcontact-2026-08-28",
           "quellen": ["zona33-bielefeld-2026-08-25",
                       "zona33-overpass-2026-09-03"]},
    "34": {"lauf": "zona34-dropcontact-2026-08-28",
           "quellen": ["zona34-kassel-2026-08-28",
                       "zona34-overpass-2026-09-03"]},
    "35": {"lauf": "zona35-dropcontact-2026-09-02",
           "quellen": ["zona35-giessen-2026-08-28",
                       "zona35-overpass-2026-09-02"]},
    "36": {"lauf": "zona36-dropcontact-2026-09-02",
           "quellen": ["zona36-fulda-2026-09-01",
                       "zona36-overpass-2026-09-02"]},
    "37": {"lauf": "zona37-dropcontact-2026-09-02",
           "quellen": ["zona37-goettingen-2026-09-01",
                       "zona37-overpass-2026-09-02"]},
    "38": {"lauf": "zona38-dropcontact-2026-09-03",
           "quellen": ["zona38-braunschweig-2026-09-01",
                       "zona38-overpass-2026-09-03"]},
    "39": {"lauf": "zona39-dropcontact-2026-09-03",
           "quellen": ["zona39-magdeburg-2026-09-01",
                       "zona39-overpass-2026-09-03"]},
}

# Nga cili mjet erdhi vertet secili vrapim. Kjo shkruhet ne kolonen
# "Quelle - Firma", prandaj duhet te jete e sakte per cdo vrapim - jo e
# hamendesuar nga emri i zones.
QUELLE_FIRMA = {
    "zona32-herford-2026-08-21": "Google Maps (Apify, 21.08.2026)",
    "zona32-overpass-2026-08-21": "Overpass/OSM (21.08.2026)",
    "zona33-bielefeld-2026-08-25": "Google Maps (Apify, 21.08.2026)",
    "zona34-kassel-2026-08-28": "Google Maps (Apify, 28.08.2026)",
    "zona33-overpass-2026-09-03": "Overpass/OSM (03.09.2026)",
    "zona34-overpass-2026-09-03": "Overpass/OSM (03.09.2026)",
    "zona35-giessen-2026-08-28": "Google Maps (Apify, 02.09.2026)",
    "zona35-overpass-2026-09-02": "Overpass/OSM (02.09.2026)",
    "zona36-fulda-2026-09-01": "Google Maps (Apify, 02.09.2026)",
    "zona36-overpass-2026-09-02": "Overpass/OSM (02.09.2026)",
    "zona37-goettingen-2026-09-01": "Google Maps (Apify, 02.09.2026)",
    "zona37-overpass-2026-09-02": "Overpass/OSM (02.09.2026)",
    "zona38-braunschweig-2026-09-01": "Google Maps (Apify, 02.09.2026)",
    "zona38-overpass-2026-09-03": "Overpass/OSM (03.09.2026)",
    "zona39-magdeburg-2026-09-01": "Google Maps (Apify, 02.09.2026)",
    "zona39-overpass-2026-09-03": "Overpass/OSM (03.09.2026)",
}
ZONE = "32"
for _a in sys.argv[1:]:
    if _a.startswith("--zone="):
        ZONE = _a.split("=", 1)[1]
if ZONE not in ZONEN:
    sys.exit(f"Unbekannte Zone {ZONE!r}")
LAUF = PROJEKT / "laeufe/leadquellen" / ZONEN[ZONE]["lauf"]

# Kolonat 1-17 jane saktesisht ato te IT-Liste-Emails-Zona32-FERTIG, qe
# lista te lexohet si me pare. Pas tyre vijne te dhenat qe Dropcontact-i
# i kthen me te njejtin kredit si email-in (vendim i Dafines, 03.09.2026:
# "gjithcka qe kthen") - deri me 03.09 hidheshin poshte pa i pare askush.
KOPF = [
    "Nr", "Firma", "Person", "Position", "E-Mail", "Anrede", "Hinweis",
    "Telefon (Person)", "Telefon (Firma)", "Webseite", "PLZ", "Ort",
    "Quelle - Firma", "Quelle - Person", "Quelle - Position",
    "Quelle - E-Mail", "Quelle - Telefon",
    "LinkedIn (Person)", "LinkedIn (Firma)", "Mitarbeiter",
    "Adresse (Handelsregister)", "PLZ (HR)", "Ort (HR)", "Land",
]

KOPF_FUELL = "FF1F3A56"
GELB = "FFF8ECD6"
GRUEN = "FFDFF0E8"

# Etiketa qe s'jane tituj pune, por fraza ligjore te impressum-it.
NICHT_TITEL = ("vertreten durch", "vertretungsberechtigt", "inhaltlich",
               "verantwortlich f", "dienstanbieter", "veranwortlich")
AUFSICHT = ("aufsichtsrat",)


def rolle_saeubern(rohe_rolle):
    """Kthen (position_e_paster, shenim). Asgje nuk shpiket: nese teksti
    s'eshte titull pune, kolona mbetet bosh dhe arsyeja shkon te Hinweis."""
    text = (rohe_rolle or "").strip()
    niedrig = text.casefold()
    if not text:
        return "", "Position nicht im Impressum genannt"
    if any(a in niedrig for a in AUFSICHT):
        return "", f"Aufsichtsrat ('{text}') - kein Einkaufsentscheider"
    if any(n in niedrig for n in NICHT_TITEL):
        return "", (f"Impressum sagt nur '{text}' - rechtliche Formel, "
                    f"keine Funktionsbezeichnung")
    return text, ""


def nummer_normal(text):
    """Vetem shifrat, pa prefiksin e shtetit dhe pa zeron e pare - qe
    '0641 350 99 48 0' dhe '+49 641 35099480' te njihen si i njejti
    numer. Pa kete, i njejti numer i shkruar ndryshe do te dukej si dy
    linja te ndryshme."""
    ziffern = re.sub(r"\D", "", text or "")
    if ziffern.startswith("00"):
        ziffern = ziffern[2:]
    if ziffern.startswith("49"):
        ziffern = ziffern[2:]
    return ziffern.lstrip("0")


def telefone_waehlen(impressum, firma):
    """Kthen (telefon_person, telefon_firma).

    Ne te dhenat tona NUK ka numer personal: te pipeline-i cdo person i
    te njejtit impressum merr te njejtin numer, ate te faqes. Pra kemi
    nje numer per firme nga DY burime - impressum-i dhe Google Maps.

    Prandaj kolona e personit mbushet vetem kur numri i impressum-it
    eshte VERTET nje numer tjeter (vendim i Dafines, 03.09.2026) - pra
    kur ka gjasa te jete nje linje e dyte. Perjashtohen:
      - numrat e cunguar nga nxjerrja (p.sh. '+49 (0) 5703' - vetem
        prefiksi i qytetit, jo numer per t'u thirrur);
      - rastet ku njeri eshte fillimi i tjetrit (mungon vetem
        prapashtesa: '45775' kunder '45775-0').
    Kur s'ka numer te dyte, kolona e personit rri bosh dhe numri i
    vetem qe kemi shkon te kolona e firmes - aty ku i takon."""
    imp_n, firma_n = nummer_normal(impressum), nummer_normal(firma)
    imp_ok = len(imp_n) >= 7
    if imp_ok and firma_n and imp_n != firma_n \
            and not imp_n.startswith(firma_n) and not firma_n.startswith(imp_n):
        return impressum, firma
    if firma:
        return "", firma
    return "", (impressum if imp_ok else "")


def firmen_index():
    """Kodi postar, qyteti, pozita DHE telefonat vijne nga vrapimet e
    mbledhjes.

    Telefonat jane dy gjera te ndryshme dhe duhen mbajtur ndare:
    "telefon" i firmes eshte centralja (Maps ose impressum), kurse
    telefoni i personit eshte ai qe qendron te impressum-i pikerisht
    ne rreshtin e atij njeriu. Deri me 02.09.2026 lista i shkruante te
    dyja kolonat nga e njejta fushe, prandaj dilnin gjithmone identike -
    dhe centralja dukej si linje direkte e personit."""
    index = {}
    for ordner in ZONEN[ZONE]["quellen"]:
        pfad = PROJEKT / "laeufe/leadquellen" / ordner / "firmen.json"
        if not pfad.exists():
            continue
        for firma in json.loads(pfad.read_text(encoding="utf-8")):
            kennung = (firma.get("domain") or firma.get("name") or "").lower()
            # Fushat bosh mbushen nga burimi tjeter, te plotat nuk prishen:
            # OSM shpesh s'e ka kodin postar, kurse Maps po - dhe anasjelltas
            # per telefonin. Mbishkrimi i thjeshte i humbte te dyja radhazi.
            vjeter = index.get(kennung, {})
            index[kennung] = {
                # E verteta e profilit, si qendron SOT ne dosjen e
                # mbledhjes. Nese nje rigjykim e ka nxjerre firmen jashte,
                # lista duhet ta dije - rezultati i Dropcontact-it nuk e
                # mban kete informacion.
                "profil_passt": (bool(firma.get("profil_passt"))
                                 if "profil_passt" in firma
                                 else vjeter.get("profil_passt", True)),
                "profil_typ": firma.get("profil_typ") or vjeter.get("profil_typ", ""),
                "plz": firma.get("plz") or vjeter.get("plz") or "",
                "ort": firma.get("ort") or vjeter.get("ort") or "",
                "telefon_firma": (firma.get("telefon")
                                  or vjeter.get("telefon_firma") or ""),
                # Cdo vendimmarres me numrin e vet, i gjetur me emer -
                # jo thjesht i pari i listes, se Dropcontact-i mund te
                # kete kthyer nje tjeter person te se njejtes firme.
                "personen": {**vjeter.get("personen", {}),
                             **{f"{p.get('vorname','')} "
                                f"{p.get('nachname','')}".strip().lower():
                                p.get("telefon") or ""
                                for p in (firma.get("entscheider") or [])}},
                # Burimi i pare qe e njohu firmen mbetet burimi i saj.
                "lauf": vjeter.get("lauf") or ordner,
            }
    return index


def bauen():
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    # Nje zone mund te kete disa vrapime Dropcontact-i: zonat 33 e 34 u
    # plotesuan me 03.09.2026 me burimin Overpass, dhe ata kontakte te
    # rinj shkuan ne dosje te vet qe te vjetrit te mos paguheshin serish.
    # Lista i mbledh te gjitha - perndryshe gjysma e punes s'do te dukej.
    daten = []
    dosjet = sorted((PROJEKT / "laeufe/leadquellen").glob(
        f"zona{ZONE}-dropcontact-*/ergebnisse.json"))
    for pfad in dosjet:
        daten.extend(json.loads(pfad.read_text(encoding="utf-8")))
    if not daten:
        sys.exit(f"Zona {ZONE}: asnje rezultat Dropcontact-i. "
                 f"Nis se pari werkzeuge/zona32-dropcontact.py --zone={ZONE}")
    if len(dosjet) > 1:
        print(f"U bashkuan {len(dosjet)} vrapime Dropcontact-i: "
              f"{', '.join(p.parent.name for p in dosjet)}")
    index = firmen_index()

    wb = openpyxl.Workbook()
    blatt = wb.active
    blatt.title = "Versandfertig"
    blatt.append(KOPF)

    # I njejti njeri te dy firma motra do te merrte DY email nga e njejta
    # fushate - pikerisht gabimi qe u ndal me 17.08.2026. Nje person, nje
    # rresht: mbahet ai me pozite te shkruar, perndryshe i pari.
    def person_schluessel(firma):
        lead = (firma.get("leads") or [None])[0] or {}
        return (f"{lead.get('first_name','')} "
                f"{lead.get('last_name','')}").strip().casefold()

    beste = {}
    doppelte = []
    for firma in daten:
        if not (firma.get("leads") or [None])[0]:
            continue
        schluessel = person_schluessel(firma)
        if not schluessel:
            continue
        hat_position = bool(rolle_saeubern(firma.get("rolle"))[0])
        vorher = beste.get(schluessel)
        if vorher is None:
            beste[schluessel] = firma
        elif hat_position and not bool(rolle_saeubern(vorher.get("rolle"))[0]):
            doppelte.append((schluessel, vorher))
            beste[schluessel] = firma
        else:
            doppelte.append((schluessel, firma))
    if doppelte:
        print(f"Persona te dyfishte te hequr: {len(doppelte)}")
        for schluessel, firma in doppelte:
            print(f"    hequr: {firma.get('name')} "
                  f"({(firma.get('leads') or [{}])[0].get('email')})")
    daten = [f for f in daten if f in beste.values()]

    # Porta e fundit para se lista te shkoje kund. Bllokimi vlen edhe per
    # rezultate te vjetra: batch-et e zonave 32/33/34 rrodhen me 21 e 28
    # gusht, kurse gjashte firmat u bllokuan me 31.08.2026 - pa kete
    # kontroll ato dilnin ne liste sikur asgje te mos kishte ndodhur.
    domains = gesperrte_domains(lade_globale_sperrlisten_eintraege(str(PROJEKT)))
    frei = [f for f in daten if not ist_gesperrt(f.get("website"), domains)]
    if len(frei) != len(daten):
        print(f"Lista e bllokimit hoqi {len(daten) - len(frei)} firma:")
        for f in daten:
            if ist_gesperrt(f.get("website"), domains):
                print(f"    bllokuar: {f.get('name')} ({f.get('website')})")
    daten = frei

    # Porta e dyte e fundit: profili IT si qendron SOT. Rezultati i
    # Dropcontact-it u be kur firma kalonte filtrin; nese me vone nje
    # rigjykim me rregullin e ri (AGENTS.md, 31.08.2026) e nxori jashte,
    # ai njeri s'guxon te dale ne liste vetem se email-i i tij u pagua.
    def profil_sot(f):
        e = index.get((f.get("domain") or f.get("name") or "").lower(), {})
        return e.get("profil_passt", True)
    frei = [f for f in daten if profil_sot(f)]
    if len(frei) != len(daten):
        print(f"Profili IT (rigjykuar) hoqi {len(daten) - len(frei)} firma:")
        for f in daten:
            if not profil_sot(f):
                e = index.get((f.get("domain") or f.get("name") or "").lower(), {})
                print(f"    jashte profilit: {f.get('name')} - {e.get('profil_typ', '')}")
    daten = frei

    # Porta e zones: firma hyn vetem me kod postar nga lista e zones.
    # OSM kerkon ne katrorin e tere rajonit postar (zona 35: rreze 120 km,
    # kurse zona ka 48), dhe firmat e tij pa kod postar hynin si "brenda
    # zones". Me 04.09.2026 dolen keshtu 23 rreshta ne listat e gatshme
    # qe s'ishin te provuar ne zonen e vet - tre prej tyre Maps i njeh ne
    # nje zone tjeter. Vendim i Dafines, 10.09.2026: pa kod postar nga
    # lista, jashte. Kodi i Handelsregister-it nuk vlen si prove: ai eshte
    # selia, jo zyra qe kerkuam.
    kodet = set(zonen.plz_kodes(ZONE))

    def ne_zone(f):
        e = index.get((f.get("domain") or f.get("name") or "").lower(), {})
        return e.get("plz", "") in kodet
    frei = [f for f in daten if ne_zone(f)]
    if len(frei) != len(daten):
        print(f"Porta e zones hoqi {len(daten) - len(frei)} firma "
              f"pa kod postar nga lista:")
        for f in daten:
            if not ne_zone(f):
                print(f"    jashte zones: {f.get('name')} ({f.get('website')})")
    daten = frei

    # Porta e trete: i njejti njeri ne DY zona. Nje firme me dy zyra bie
    # ne dy lista, dhe personi i saj do te merrte dy email nga e njejta
    # fushate - gabimi i 17.08.2026, tash mes zonave. Rregulli: zona me
    # numrin me te vogel e mban; kjo liste kontrollon listat e fundit te
    # zonave me numer me te vogel. Kontrolli i 03.09.2026 gjeti 22 te tille.
    tjeter = set()
    for z_tjeter in sorted(ZONEN):
        if z_tjeter >= ZONE:
            break
        fs = sorted(glob.glob(str(PROJEKT / f"IT-Liste-Emails-Zona{z_tjeter}-FERTIG-*.xlsx")),
                    key=os.path.getmtime)
        if not fs:
            continue
        ws_t = openpyxl.load_workbook(fs[-1]).active
        for r in range(2, ws_t.max_row + 1):
            email = str(ws_t.cell(r, 5).value or "").strip().casefold()
            person = str(ws_t.cell(r, 3).value or "").strip().casefold()
            if email:
                tjeter.add(("email", email))
            if person:
                tjeter.add(("person", person))
    if tjeter:
        para = len(daten)
        mbetur = []
        for f in daten:
            lead = (f.get("leads") or [{}])[0]
            email = str(lead.get("email") or "").strip().casefold()
            person = person_schluessel(f)
            if ("email", email) in tjeter or ("person", person) in tjeter:
                print(f"    tashme ne nje zone me te vogel: {person} ({email})")
            else:
                mbetur.append(f)
        if len(mbetur) != para:
            print(f"Dublikata mes zonave hoqi {para - len(mbetur)} persona.")
        daten = mbetur

    kontrolle = []
    nummer = 0
    ohne_position = 0
    for firma in daten:
        lead = (firma.get("leads") or [None])[0]
        if not lead:
            continue
        nummer += 1
        person = f"{lead.get('first_name','')} {lead.get('last_name','')}".strip()
        # Cka ktheu Dropcontact-i per kete person, pervec email-it. Vjen me
        # te njejtin kredit; deri me 03.09.2026 hidhej poshte.
        dc = firma.get("dropcontact") or {}
        anrede, grund = baue_anrede(person, civility=dc.get("civility"))

        position, positions_hinweis = rolle_saeubern(firma.get("rolle"))
        if not position:
            ohne_position += 1

        hinweise = []
        if grund != "maennlich":
            hinweise.append(grund)
        if positions_hinweis:
            hinweise.append(positions_hinweis)
        for notiz in lead.get("notizen") or []:
            hinweise.append(str(notiz))
        hinweis = " | ".join(hinweise)
        if hinweise:
            kontrolle.append((firma.get("name", ""), person, hinweis))

        ort_daten = index.get(
            (firma.get("domain") or firma.get("name") or "").lower(), {})
        quelle_firma = QUELLE_FIRMA.get(ort_daten.get("lauf", ""), "?")

        # Telefoni i personit merret me emrin e tij; nese ai njeri s'ka
        # numer te vetin te impressum-i, kolona mbetet BOSH. Me pare aty
        # binte centralja e firmes, dhe nje qendrore dukej si linje
        # direkte - lexuesi s'kishte si ta dallonte.
        telefon_person, telefon_firma = telefone_waehlen(
            ort_daten.get("personen", {}).get(person.lower(), ""),
            ort_daten.get("telefon_firma", "") or firma.get("telefon", ""))

        # Numri i Dropcontact-it eshte i lidhur me kete person konkret,
        # kurse ai i impressum-it eshte numri i faqes. Prandaj i pari ka
        # perparesi te kolona e personit.
        if dc.get("phone"):
            telefon_person = dc["phone"]
            quelle_telefon = "Dropcontact"
        elif telefon_person:
            quelle_telefon = "Impressum"
        elif telefon_firma:
            quelle_telefon = "Firma (Maps/Impressum)"
        else:
            quelle_telefon = "—"

        blatt.append([
            nummer, firma.get("name", ""), person, position,
            lead.get("email", ""), anrede, hinweis,
            telefon_person, telefon_firma,
            firma.get("website", ""),
            # Pas portes se zones cdo firme e ka kodin postar nga lista.
            # Deri me 10.09.2026 ketu binte kodi i Handelsregister-it kur
            # OSM s'kishte kod - keshtu dolen kode nga Wuppertal e Mainz.
            # Selia zyrtare mbetet te kolonat e veta "... (HR)".
            ort_daten.get("plz", ""),
            ort_daten.get("ort") or dc.get("siret_city", ""),
            quelle_firma, "Impressum + KI",
            "Impressum (wörtlich)" if position else "—",
            "Dropcontact (gebaut + verifiziert)",
            quelle_telefon,
            # Fushat e Dropcontact-it, te paguara me te njejtin kredit.
            dc.get("linkedin", ""), dc.get("company_linkedin", ""),
            dc.get("nb_employees", ""),
            dc.get("siret_address", ""), dc.get("siret_zip", ""),
            dc.get("siret_city", ""), dc.get("country", ""),
        ])

    for zelle in blatt[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = PatternFill("solid", fgColor=KOPF_FUELL)
        zelle.alignment = Alignment(vertical="center", wrap_text=True)
    blatt.row_dimensions[1].height = 30
    blatt.freeze_panes = "A2"
    blatt.auto_filter.ref = blatt.dimensions

    breiten = [5, 36, 24, 26, 36, 22, 46, 20, 20, 34, 8, 18,
               30, 18, 22, 32, 14,
               40, 40, 12, 34, 10, 18, 8]
    for spalte, breite in enumerate(breiten, 1):
        blatt.column_dimensions[get_column_letter(spalte)].width = breite

    for rreshti in range(2, blatt.max_row + 1):
        zelle = blatt.cell(rreshti, 4)          # Position
        zelle.fill = PatternFill(
            "solid", fgColor=GRUEN if zelle.value else GELB)

    kb = wb.create_sheet("Zur Kontrolle")
    kb.append(["Firma", "Person", "Warum auf dieser Liste"])
    for reihe in kontrolle:
        kb.append(list(reihe))
    for zelle in kb[1]:
        zelle.font = Font(bold=True, color="FFFFFFFF", size=10)
        zelle.fill = PatternFill("solid", fgColor=KOPF_FUELL)
    for spalte, breite in zip("ABC", [36, 26, 90]):
        kb.column_dimensions[spalte].width = breite

    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    ziel = PROJEKT / f"IT-Liste-Emails-Zona{ZONE}-FERTIG-{stempel}.xlsx"
    wb.save(ziel)
    return ziel, nummer, ohne_position, len(kontrolle)


if __name__ == "__main__":
    ziel, rreshta, pa_pozite, kontrolle = bauen()
    print(f"DOSJA:            {ziel}")
    print(f"Rreshta:          {rreshta}")
    print(f"Me pozite:        {rreshta - pa_pozite}")
    print(f"Pa pozite:        {pa_pozite}")
    print(f"Zur Kontrolle:    {kontrolle}")

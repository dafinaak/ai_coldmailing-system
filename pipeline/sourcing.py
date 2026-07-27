"""Orchestriert die Lead-Beschaffung als Kaskade (Chef-Vorgabe 23.07.2026).

Stufe 1: Firmen ueber Google Maps finden (pipeline.sources.apify_maps.
         ApifyMapsSource) - uebernommen wird v.a. die Website/Domain; der
         Maps-Titel dient nur bereinigt als Namens-Rueckfallebene.
Stufe 2+: Anbieter-Stufen laut Kunde.anbieter_reihenfolge, NACHEINANDER je
         Firma, bis eine Stufe liefert ("wenn Stufe 1 nur 80 von 100 findet,
         versucht Stufe 2 die restlichen 20"):
         - "hunter_dropcontact": Hunter findet die Entscheider der Domain,
           Dropcontact baut + prueft die persoenliche Mail.
         - "prospeo": Prospeo sucht Personen ueber die Domain und deckt nur
           geprueft zustellbare Mails auf.
         Standard (solange der Anbieter-Vergleich die Reihenfolge nicht
         festgelegt hat): nur "hunter_dropcontact".
Zuletzt: info@-Regel (unten) fuer Firmen, bei denen keine Stufe traf.

info@-Regel: Findet keine Stufe einen persoenlichen Kontakt, wird
info@<domain> als Lead-E-Mail verwendet (source="info@") - nur, wenn eine
Domain bekannt ist, und GEPRUEFT ueber Hunters Email Verifier, sofern die
Hunter-Quelle das anbietet (Projektregel: keine ungepruefte Adresse in den
Versand; nicht versandtaugliche Adressen enden als "info_ungueltig").

Deckungsquote: Anteil der Stufe-1-Firmen, die am Ende mindestens einen
nutzbaren Kontakt (persoenlich ODER info@) haben - das ist die vom Chef
geforderte "mindestens 80%"-Zahl (siehe pipeline.report).

Fehlertoleranz pro Firma: Ein Fehler bei der Anreicherung EINER Firma
(z.B. Apollo antwortet dauerhaft mit 401/422, oder mit 500 auch nach den
Retries in ApolloSource) bricht NICHT den ganzen Lauf ab - die Firma wird
uebersprungen (zaehlt zu firmen_gesamt, nicht zu firmen_mit_kontakt), der
Rest laeuft weiter. Bei ~50 Firmen pro Lauf soll eine einzelne flackernde
Firma nur die Deckungsquote verschlechtern, nicht alle bereits gefundenen
Leads und das schon verbrauchte Apify-/Apollo-Kontingent verwerfen.

Lead-Qualitaets-Fix (Probe-Lauf-Funde, siehe Auftrag):
1) Apollo lieferte bei einer kleinen Firma 5 Kontakte, alle mit dem Titel
   "Managing Director" - 5 Personen einer Firma anzuschreiben verbrennt
   Budget und wirkt unseriös, zumal die gewuenschten Rollen (kontakt_rollen,
   z.B. "Geschäftsführer"/"IT-Leiter") nur locker mit Apollos englischen
   Jobtiteln abgeglichen wurden. Fix: _rolle_passt() unten matcht ueber eine
   Synonym-Tabelle (deutsch<->englisch); _entscheider_kontakte() deckelt auf
   kunde.max_kontakte_pro_firma (Default 1), sortiert nach Rollen-Prioritaet
   aus kontakt_rollen (erste Rolle zuerst).
2) Ein Google-Maps-Titel enthielt den Suchbegriff als Praefix
   ("IT-Dienstleister Hannover - Ihre Helden" statt "Ihre Helden"). Fix:
   _firmenname_saeubern() unten - genutzt wird der Name aber nur als
   Rueckfallebene, bevorzugt wird Apollos kanonischer Organisationsname
   (ergebnis["name"]), wenn Apollo die Organisation gefunden hat."""
import re
from pipeline.models import Lead
from pipeline.sources.apify_maps import ApifyMapsSource
from pipeline.sources.hunter import HunterSource
from pipeline.sources.dropcontact import DropcontactSource
from pipeline.sources.prospeo import ProspeoSource

MAX_KONTAKTE_PRO_FIRMA_STANDARD = 1  # siehe Kunde.max_kontakte_pro_firma (pipeline.config)

# Kaskade (Chef-Vorgabe 23.07.2026): Die Entscheider-Suche laeuft in
# konfigurierbaren Stufen (Kunde.anbieter_reihenfolge). Stufe 2 versucht nur
# die Firmen, bei denen Stufe 1 leer ausging; wer danach immer noch ohne
# Kontakt ist, faellt in die info@-Regel (mit Pruefung, siehe unten).
# Solange der Anbieter-Vergleich die Reihenfolge nicht festgelegt hat, bleibt
# der Standard beim bisherigen einstufigen Ablauf.
STANDARD_REIHENFOLGE = ["hunter_dropcontact"]
GUELTIGE_STUFEN = ("hunter_dropcontact", "prospeo", "impressum")
# info@-Pruefstatus (Hunter Email Verifier), die als versandtauglich gelten.
# "accept_all" bewusst dabei: der Server nimmt dort formal alles an, mehr als
# diese Aussage gibt es fuer solche Domains technisch nicht - bei unseren
# Kleinstfirmen ist das der haeufigste Fall. "invalid"/"disposable"/"unknown"
# fliegen raus (Zuverlaessigkeit zuerst).
INFO_OK_STATUS = ("valid", "accept_all")

# Prospeo kennt keinen decision_maker-Schalter wie Hunter; diese
# Seniority-Stufen gelten als Entscheider-Merkmal. Nur fuer die LOKALE
# Auswahl benutzt - sie gehen nicht als Filter an die Prospeo-API, damit ein
# unbekannter Enum-Wert dort nicht den ganzen Aufruf scheitern laesst.
# "Partner" seit dem Messlauf 23.07.2026 dabei: bei unseren Kleinfirmen sind
# "Partner" (beobachtet u.a. fuer "Geschaeftsfuehrender Gesellschafter")
# praktisch immer Mitinhaber. Live beobachtete weitere Werte: Manager, Head,
# Director, Entry - die bleiben bewusst draussen (keine Entscheider-Garantie).
ENTSCHEIDER_SENIORITIES = {"Founder/Owner", "C-Level", "Partner"}

# Rollen-Synonym-Tabelle (Lead-Qualitaets-Fix): jede Gruppe fasst eine
# gewuenschte Rolle mit ihren deutschen UND englischen Entsprechungen
# zusammen, wie sie in echten Apollo-Jobtiteln vorkommen. Bewusst klein
# gehalten und leicht erweiterbar (einfach eine weitere Menge ergaenzen) -
# eine gewuenschte Rolle, die in KEINER Gruppe steckt, faellt in
# _rolle_passt() auf einen einfachen, verlustfreien Teilstring-Abgleich
# zurueck, matcht also weiterhin, nur eben ohne Synonyme.
ROLLEN_GRUPPEN = [
    {"geschäftsführer", "geschäftsführung", "managing director", "ceo",
     "inhaber", "owner", "gründer", "founder",
     # Messlauf-Funde 23.07.2026 (Prospeo, echte 20er-Liste): deutsche
     # Titelformen, die der Wortgrenzen-Abgleich sonst verfehlt -
     # "geschäftsführender" ist ein anderes Wort als "geschäftsführer".
     "geschäftsführender gesellschafter", "geschäftsführende gesellschafterin",
     "gründungspartner"},
    {"it-leiter", "it-leitung", "leiter it", "head of it", "it manager",
     "it-manager", "cto", "cio"},
]


def _normalisieren(text: str) -> str:
    """Kleinschreibung, Bindestriche zu Leerzeichen (damit "IT-Leiter" und
    "Leiter IT" vergleichbar werden), doppelte Leerzeichen entfernt."""
    return " ".join((text or "").strip().lower().replace("-", " ").split())


def _gruppe_fuer_rolle(rolle_norm: str):
    """Findet die Synonym-Gruppe, zu der eine (bereits normalisierte)
    gewuenschte Rolle gehoert - oder None, wenn sie in keiner Gruppe steckt
    (dann greift in _rolle_passt() der einfache Teilstring-Abgleich)."""
    for gruppe in ROLLEN_GRUPPEN:
        if any(_normalisieren(s) == rolle_norm for s in gruppe):
            return gruppe
    return None


def _enthaelt_als_wort(haystack: str, needle: str) -> bool:
    """Prueft, ob `needle` als EIGENSTAENDIGES Wort bzw. eigenstaendige
    Wortfolge in `haystack` vorkommt - Wortgrenzen-genau (\\b...\\b), KEIN
    roher Teilstring-Abgleich. Bug-Fix (Review-Fund): ein roher `in`-Abgleich
    matcht faelschlich "cto" als Teilstring in "director" (di-REC-TO-r) und
    "contractor" (con-TRA-CTO-r) - jeder "Director"/"Contractor"-Titel waere
    damit faelschlich als IT-Leiter erkannt worden. Mit Wortgrenzen matcht
    "cto" nur, wenn es tatsaechlich als eigenes Wort auftaucht (z.B. in
    "CTO" oder "Chief Technology Officer (CTO)"), nicht mitten in einem
    anderen Wort. Beide Strings muessen bereits ueber _normalisieren() -
    d.h. kleingeschrieben, Bindestriche zu Leerzeichen - laufen."""
    if not needle:
        return False
    # Optionale deutsche weibliche Endung "in"/"innen" direkt hinter dem Wort
    # (z.B. "Geschaeftsfuehrerin" -> "Geschaeftsfuehrer", "Leiterin" -> "Leiter"),
    # bleibt wortgrenzen-genau - "cto" matcht weiter NICHT in "director".
    return re.search(rf"\b{re.escape(needle)}(in|innen)?\b", haystack) is not None


def _rolle_passt(kontakt_titel: str, gewuenschte_rolle: str) -> bool:
    """Prueft, ob ein von Apollo gelieferter Jobtitel zu einer gewuenschten
    Rolle aus kontakt_rollen passt - case-insensitive, Synonym-bewusst
    (z.B. "Managing Director" passt zu "Geschäftsführer", "Head of IT" zu
    "IT-Leiter"), aber immer WORTGRENZEN-genau (_enthaelt_als_wort) statt
    als roher Teilstring - sonst matchen kurze Akronyme wie "cto"/"ceo"
    versehentlich mitten in unverwandten Woertern (siehe _enthaelt_als_wort).
    Rollen ausserhalb der Synonym-Tabelle degradieren zu einem schlichten,
    aber weiterhin wortgrenzen-genauen Abgleich (in beide Richtungen,
    toleriert also sowohl kuerzere als auch laengere Formulierungen)."""
    titel_norm, rolle_norm = _normalisieren(kontakt_titel), _normalisieren(gewuenschte_rolle)
    # Falsche Freunde (Messlauf-Fund 23.07.2026, echte 20er-Liste): in
    # "Product Owner"/"Process Owner" steckt "owner" als eigenes Wort, die
    # Person ist aber Projektrolle, kein Inhaber. Solche Phrasen werden vor
    # dem Abgleich aus dem Titel entfernt - ein alleinstehendes "Owner"
    # (oder "Owner / CEO") matcht weiterhin.
    for falscher_freund in ("product owner", "process owner"):
        titel_norm = " ".join(titel_norm.replace(falscher_freund, " ").split())
    if not titel_norm or not rolle_norm:
        return False
    gruppe = _gruppe_fuer_rolle(rolle_norm)
    if gruppe is not None:
        return any(_enthaelt_als_wort(titel_norm, _normalisieren(s))
                    or _enthaelt_als_wort(_normalisieren(s), titel_norm)
                    for s in gruppe)
    return _enthaelt_als_wort(titel_norm, rolle_norm) or _enthaelt_als_wort(rolle_norm, titel_norm)




# "<Suchbegriff/Kategorie> - "-Praefix wie ihn Google-Maps-Titel manchmal
# voranstellen, siehe _firmenname_saeubern().
_TRENNER_MUSTER = r"\s*[-–—:|]\s*"


def _firmenname_saeubern(maps_name: str, maps_suche: str) -> str:
    """Rueckfallebene fuer den Firmennamen, wenn Apollo keine Organisation
    gefunden hat (siehe source_leads()): bereinigt einen Google-Maps-Titel
    um ein Suchbegriff-/Kategorie-Praefix, z.B. "IT-Dienstleister Hannover -
    Ihre Helden" (mit maps_suche "IT-Dienstleister Hannover") -> "Ihre
    Helden". Bewusst konservativ: schneidet NUR ab, wenn der Praefix-Teil
    erkennbar mit dem Suchbegriff zusammenhaengt - ein echter Firmenname mit
    Bindestrich (z.B. "Müller - Schmidt GbR") bleibt unangetastet, weil
    "müller" nicht zum Suchbegriff passt. Ein bereits sauberer Name kommt
    unveraendert zurueck."""
    name = (maps_name or "").strip()
    if not name:
        return name
    suche = (maps_suche or "").strip()
    suche_norm = suche.lower()

    # Fall 1: Name beginnt EXAKT mit dem Suchbegriff (ggf. gefolgt von einem
    # Trennzeichen) - der haeufigste Fall.
    if suche_norm and name.lower().startswith(suche_norm):
        rest = re.sub(rf"^{_TRENNER_MUSTER}", "", name[len(suche):])
        if rest.strip():
            return rest.strip(" -–—")
        # MINOR-Fix: Name ist (nach Bereinigen) EXAKT der Suchbegriff plus
        # einem verwaisten Trennzeichen ohne echten Rest dahinter (z.B.
        # "IT-Dienstleister Hannover -"). Bewusst HIER direkt zurueckgeben
        # (nicht nach Fall 2 weiterfallen lassen) - Fall 2 wuerde sonst am
        # ERSTEN Bindestrich INNERHALB des Suchbegriffs selbst (z.B.
        # "IT-Dienstleister") trennen und faelschlich den Namensanfang
        # abschneiden.
        return name.strip(" -–—:|")

    # Fall 2: allgemeineres "<Praefix> - <Rest>"-Muster, bei dem der
    # Praefix-Teil zum Suchbegriff passt (Teilstring in beide Richtungen) -
    # deckt leicht abweichende Schreibweisen ab, OHNE echte Firmennamen mit
    # Bindestrich anzufassen.
    treffer = re.match(rf"^(.+?){_TRENNER_MUSTER}(.+)$", name)
    if treffer and suche_norm:
        praefix_norm, rest = treffer.group(1).strip().lower(), treffer.group(2).strip()
        if praefix_norm and (praefix_norm in suche_norm or suche_norm in praefix_norm) and rest:
            return rest

    # MINOR-Fix: verwaiste fuehrende/abschliessende Trennzeichen entfernen
    # (z.B. falls ein Name zufaellig mit " -" endet), ohne echte Namen
    # anzutasten - strip() greift nur an den Raendern, nie in der Mitte.
    return name.strip(" -–—:|")


def _qualifiziert(person: dict, kontakt_rollen: list) -> bool:
    """Ein von Hunter gefundener Kontakt kommt nur als Entscheider infrage,
    wenn Hunter ihn selbst als Entscheider markiert hat (decision_maker) ODER
    sein Titel zu einer gewuenschten Rolle (kontakt_rollen) passt. So wird
    kein zufaelliger Junior-Mitarbeiter angeschrieben - passt keiner, faellt
    die Firma bewusst in die info@-Regel (Zuverlaessigkeit/Qualitaet zuerst)."""
    if person.get("decision_maker"):
        return True
    return any(_rolle_passt(person.get("title", ""), rolle) for rolle in kontakt_rollen)


def _nach_rollen_sortieren(personen: list, kontakt_rollen: list) -> list:
    """Stabile Sortierung: Personen, deren Titel zu einer gewuenschten Rolle
    (kontakt_rollen, z.B. Geschaeftsfuehrer/IT-Leiter) passt, kommen nach vorn -
    in der Reihenfolge der kontakt_rollen. Der Rest behaelt Hunters
    Reihenfolge nach Entscheider-Wahrscheinlichkeit. So wird zuerst der
    gewuenschte Entscheider verifiziert, nicht irgendein Mitarbeiter."""
    def rang(person):
        for i, rolle in enumerate(kontakt_rollen):
            if _rolle_passt(person.get("title", ""), rolle):
                return i
        return len(kontakt_rollen)
    return sorted(personen, key=rang)


def _verifizierte_email(person: dict, firma: dict, dropcontact) -> dict | None:
    """Holt die persoenliche Mail eines von Hunter gefundenen Entscheiders:
    zuerst ueber Dropcontact (baut + verifiziert aus Name + Webseite), sonst
    ueber Hunters eigene Mail - aber NUR, wenn Hunter sie selbst als 'valid'
    verifiziert hat. Findet keine der beiden Quellen eine gepruefte Adresse,
    kommt None zurueck (lieber keine Mail als eine ungepruefte - Ruecklaeufer
    schaedigen den Ruf der Absender-Postfaecher, siehe AGENTS.md).
    Gibt {"wert", "quelle"} zurueck."""
    ergebnis = dropcontact.email_bauen(
        person.get("first_name", ""), person.get("last_name", ""),
        firma.get("website", ""), company=firma.get("name", ""))
    if ergebnis:
        return {"wert": ergebnis["email"], "quelle": "dropcontact"}
    if person.get("email") and person.get("verification_status") == "valid":
        return {"wert": person["email"], "quelle": "hunter"}
    return None


def _entscheider_kontakte(firma: dict, kontakt_rollen: list, max_pro_firma: int,
                          hunter, dropcontact) -> list:
    """Stufe 2 (Weg A, siehe AGENTS.md): Hunter findet die Entscheider einer
    Firma aus ihrer Domain, Dropcontact baut/prueft deren persoenliche Mail.
    Gibt bis zu max_pro_firma Kontakte als {"first_name","last_name","email",
    "title","source"}-Dicts zurueck - nur mit einer verifizierten Mail. Leere
    Liste, wenn die Firma keine Domain hat, Hunter niemanden findet oder fuer
    keinen Gefundenen eine Mail verifiziert werden kann (dann greift in
    source_leads() die info@-Regel)."""
    domain = firma.get("domain")
    if not domain:
        return []
    personen = [p for p in hunter.entscheider_finden(domain)
                if _qualifiziert(p, kontakt_rollen)]
    kontakte = []
    for person in _nach_rollen_sortieren(personen, kontakt_rollen):
        if len(kontakte) >= max_pro_firma:
            break
        email = _verifizierte_email(person, firma, dropcontact)
        if email:
            kontakte.append({
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "email": email["wert"], "title": person.get("title", ""),
                "source": email["quelle"]})
    return kontakte


def _qualifiziert_prospeo(person: dict, kontakt_rollen: list) -> bool:
    """Gegenstueck zu _qualifiziert() fuer Prospeo-Personen: Entscheider ist,
    wessen Seniority als Entscheider-Stufe gilt ODER wessen Jobtitel zu einer
    gewuenschten Rolle passt."""
    if person.get("seniority") in ENTSCHEIDER_SENIORITIES:
        return True
    return any(_rolle_passt(person.get("title", ""), rolle) for rolle in kontakt_rollen)


def _prospeo_kontakte(firma: dict, kontakt_rollen: list, max_pro_firma: int,
                      prospeo) -> list:
    """Prospeo-Stufe der Kaskade: findet die Personen einer Firma ueber die
    Domain und deckt fuer die passendsten Entscheider die persoenliche Mail
    auf - nur geprueft zustellbare Adressen (only_verified_email in
    ProspeoSource). Gleiche Rueckgabeform wie _entscheider_kontakte()."""
    domain = firma.get("domain")
    if not domain:
        return []
    personen = [p for p in prospeo.entscheider_finden(domain)
                if _qualifiziert_prospeo(p, kontakt_rollen)]
    kontakte = []
    for person in _nach_rollen_sortieren(personen, kontakt_rollen):
        if len(kontakte) >= max_pro_firma:
            break
        mail = prospeo.email_anreichern(person.get("person_id", ""))
        if mail:
            kontakte.append({
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "email": mail["email"], "title": person.get("title", ""),
                "source": "prospeo"})
    return kontakte


def _impressum_kontakte(firma: dict, max_pro_firma: int, impressum,
                        dropcontact) -> list:
    """Impressum-Stufe der Kaskade (Bauplan 2026-07-27): liest die
    Geschaeftsfuehrer-Namen von der Firmen-Webseite (ImpressumQuelle, KI)
    und laesst Dropcontact daraus die gepruefte persoenliche Mail bauen.
    Kein Rollen-Filter: Das Impressum nennt per Gesetz die Geschaeftsfuehrung,
    also genau die Rueckfall-Person der Kaskade. Ein Namens-Hinweis aus einer
    importierten Lead-Liste (firma["gf_name_liste"]) wird der KI zur Pruefung
    mitgegeben - Hinweis, nicht Fakt (Stichproben-Fund: Listen irren)."""
    website = firma.get("website")
    if not website:
        return []
    text = impressum.impressum_text(website)
    if not text:
        return []
    ergebnis = impressum.entscheider_lesen(
        text, firma.get("name", ""), domain=firma.get("domain", ""),
        hinweis_name=firma.get("gf_name_liste", ""))
    mail_domain = ergebnis.get("mail_domain")
    ziel_website = f"https://{mail_domain}" if mail_domain else website
    kontakte = []
    for person in ergebnis.get("personen") or []:
        if len(kontakte) >= max_pro_firma:
            break
        mail = dropcontact.email_bauen(person["vorname"], person["nachname"],
                                       ziel_website, company=firma.get("name", ""))
        if mail:
            kontakte.append({
                "first_name": person["vorname"], "last_name": person["nachname"],
                "email": mail["email"],
                "title": "Geschäftsführung (laut Impressum)",
                "source": "impressum"})
    return kontakte


def _pruefe_kunde(kunde):
    fehlend = [f for f in ("maps_suche", "kontakt_rollen") if not getattr(kunde, f, None)]
    if fehlend:
        raise ValueError(
            f"Für die Lead-Beschaffung fehlen im Kunden '{kunde.name}': "
            f"{', '.join(fehlend)}. 'maps_suche' ist der Google-Maps-Suchbegriff "
            f"(z.B. 'IT-Dienstleister Hannover'), 'kontakt_rollen' die gewünschten "
            f"Job-Titel (z.B. [Geschäftsführer, IT-Leiter]). Bitte in der Kunden-"
            f"Konfigurationsdatei ergänzen.")


def _stufen_bauen(kunde, hunter, dropcontact, prospeo_key, prospeo_source,
                  impressum_quelle, max_pro_firma) -> list:
    """Baut die Stufenliste [(name, kontakt_funktion)] aus
    Kunde.anbieter_reihenfolge. Unbekannte Stufennamen und eine
    Prospeo-Stufe ohne Quelle/Key scheitern laut mit deutscher Erklaerung -
    NICHT still als 'keine Kontakte' (das wuerde die Deckungsquote
    verfaelschen, wie damals der leere Apollo-Account)."""
    reihenfolge = list(getattr(kunde, "anbieter_reihenfolge", None)
                       or STANDARD_REIHENFOLGE)
    unbekannt = [s for s in reihenfolge if s not in GUELTIGE_STUFEN]
    if unbekannt:
        raise ValueError(
            f"Unbekannte Anbieter-Stufe(n) in anbieter_reihenfolge des Kunden "
            f"'{kunde.name}': {', '.join(unbekannt)}. Gültig sind: "
            f"{', '.join(GUELTIGE_STUFEN)}.")
    prospeo = prospeo_source
    if "prospeo" in reihenfolge and prospeo is None:
        if not prospeo_key:
            raise ValueError(
                f"Die Stufe 'prospeo' steht in der anbieter_reihenfolge des "
                f"Kunden '{kunde.name}', aber es wurde weder eine "
                f"Prospeo-Quelle noch ein PROSPEO_API_KEY übergeben. Bitte "
                f"PROSPEO_API_KEY in .env eintragen (siehe .env.example).")
        prospeo = ProspeoSource(prospeo_key)
    if "impressum" in reihenfolge and impressum_quelle is None:
        raise ValueError(
            f"Die Stufe 'impressum' steht in der anbieter_reihenfolge des "
            f"Kunden '{kunde.name}', aber es wurde keine impressum_quelle "
            f"übergeben (pipeline.sources.impressum.ImpressumQuelle, braucht "
            f"den KI-Baustein).")
    stufen = []
    for name in reihenfolge:
        if name == "hunter_dropcontact":
            stufen.append((name, lambda firma: _entscheider_kontakte(
                firma, kunde.kontakt_rollen, max_pro_firma, hunter, dropcontact)))
        elif name == "prospeo":
            stufen.append((name, lambda firma: _prospeo_kontakte(
                firma, kunde.kontakt_rollen, max_pro_firma, prospeo)))
        else:
            stufen.append((name, lambda firma: _impressum_kontakte(
                firma, max_pro_firma, impressum_quelle, dropcontact)))
    return stufen


def source_leads(kunde, limit, apify_key, hunter_key, dropcontact_key,
                  apify_source=None, hunter_source=None, dropcontact_source=None,
                  prospeo_key=None, prospeo_source=None,
                  impressum_quelle=None) -> tuple:
    """Fuehrt alle Stufen aus und liefert (leads, deckung, firmen_mit_ausgang):
    - leads: Liste von pipeline.models.Lead (bestehende Form, downstream
      unveraendert nutzbar).
    - deckung: {"firmen_gesamt": int, "firmen_mit_kontakt": int,
      "quote_prozent": float, "je_stufe": {stufenname: int, "info@": int}} -
      die Deckungsquote fuer den Bericht. "mit Kontakt" zaehlt eine
      persoenliche Entscheider-Mail ODER die info@-Rueckfallebene; "je_stufe"
      zaehlt, welche Kaskaden-Stufe die Firma geliefert hat (die
      100/80/20-Aufschluesselung aus der Chef-Vorgabe vom 23.07.2026).
    - firmen_mit_ausgang: die Stufe-1-Firmenliste aus Apify, JEDE Firma
      zusaetzlich um ein "ausgang"-Feld ergaenzt: einer von
      "mit_entscheider" (persoenliche, gepruefte Mail; dazu "stufe" = Name
      der liefernden Kaskaden-Stufe) / "info_fallback" (kein persoenlicher
      Treffer, aber info@ als Rueckfall; dazu ggf. "info_pruefstatus") /
      "info_ungueltig" (info@ wurde geprueft und ist NICHT versandtauglich)
      / "keine_webseite" / "kein_entscheider" (Webseite da, aber keine Stufe
      lieferte eine gepruefte Person) / "fehler". Zweck: sauber unterscheiden,
      WARUM eine Firma so endete. __main__.lauf() persistiert diese Liste als
      firmen.json und zaehlt daraus die Aufschluesselung fuer den Bericht.

    Kaskaden-Ablauf (Chef-Vorgabe 23.07.2026): Google Maps liefert die Firmen
    (uebernommen wird v.a. die Website/Domain) -> die Anbieter-Stufen aus
    Kunde.anbieter_reihenfolge versuchen NACHEINANDER, Entscheider samt
    geprueft zustellbarer persoenlicher Mail zu finden (jede Stufe nur fuer
    die Firmen, bei denen die vorherige leer ausging) -> wer danach noch ohne
    Kontakt ist, bekommt info@<domain> als Rueckfall - GEPRUEFT ueber Hunters
    Email Verifier, sofern die Hunter-Quelle das kann (Projektregel: keine
    ungepruefte Adresse in den Versand). Quellen sind fuer Tests injizierbar;
    im echten Betrieb baut diese Funktion die echten Klassen selbst."""
    _pruefe_kunde(kunde)
    apify = apify_source or ApifyMapsSource(apify_key)
    hunter = hunter_source or HunterSource(hunter_key)
    dropcontact = dropcontact_source or DropcontactSource(dropcontact_key)
    max_pro_firma = getattr(kunde, "max_kontakte_pro_firma", None) or MAX_KONTAKTE_PRO_FIRMA_STANDARD
    stufen = _stufen_bauen(kunde, hunter, dropcontact, prospeo_key,
                           prospeo_source, impressum_quelle, max_pro_firma)
    # info@-Pruefer: Hunters Email Verifier, wenn die (ggf. gefakte) Quelle
    # ihn anbietet. Aeltere Test-Fakes ohne email_pruefen behalten das alte
    # Verhalten (info@ ungeprueft uebernehmen) - Rueckwaerts-Kompatibilitaet.
    email_pruefer = getattr(hunter, "email_pruefen", None)

    firmen = apify.search(kunde.maps_suche, limit)
    leads, firmen_mit_kontakt, firmen_mit_ausgang = [], 0, []
    je_stufe = {name: 0 for name, _ in stufen}
    je_stufe["info@"] = 0
    for firma in firmen:
        try:
            kontakte, liefernde_stufe = [], None
            for name, kontakt_funktion in stufen:
                kontakte = kontakt_funktion(firma)
                if kontakte:
                    liefernde_stufe = name
                    break
        except Exception as fehler:
            # Eine einzelne fehlerhafte Firma (ein Anbieter dauerhaft 4xx/5xx,
            # oder Dropcontact lehnt den Batch ab - z.B. leere Credits) darf
            # bei ~50 Firmen pro Lauf nicht den ganzen Lauf mitreissen: sonst
            # sind alle bereits gefundenen Leads UND das verbrauchte
            # Kontingent futsch. Diese Firma zaehlt weiter zu firmen_gesamt
            # (Nenner der Deckungsquote), aber nicht zu firmen_mit_kontakt.
            # Die Fehlermeldungen enthalten keine Secrets (API-Key steht im
            # Header bzw. Query, nicht im geloggten Text).
            print(f"Firma '{firma.get('name') or firma.get('domain') or '?'}' "
                  f"übersprungen (Fehler bei der Entscheider-Suche): {fehler}")
            firmen_mit_ausgang.append({**firma, "ausgang": "fehler"})
            continue

        firmenname = _firmenname_saeubern(firma.get("name", ""), kunde.maps_suche)

        ausgang = "kein_entscheider" if firma.get("website") else "keine_webseite"
        zusatz = {}
        if kontakte:
            for k in kontakte:
                leads.append(Lead(
                    first_name=k["first_name"], last_name=k["last_name"],
                    email=k["email"], company=firmenname, title=k["title"],
                    website=firma["website"], source=k["source"]))
            firmen_mit_kontakt += 1
            ausgang = "mit_entscheider"
            je_stufe[liefernde_stufe] += 1
            zusatz["stufe"] = liefernde_stufe
        elif firma.get("domain"):
            # info@-Regel: keine Stufe fand einen persoenlichen Entscheider,
            # aber die Domain ist da -> info@ als letzter Ausweg. Unsere
            # Zielgruppe sind kleine Firmen, bei denen info@ oft direkt beim
            # Inhaber landet. Vorher pruefen (Projektregel!), sofern ein
            # Pruefer verfuegbar ist; nicht versandtaugliche Adressen werden
            # verworfen ("info_ungueltig") statt still versendet.
            info_email = f"info@{firma['domain']}"
            pruefstatus = None
            if email_pruefer:
                try:
                    pruefstatus = (email_pruefer(info_email) or {}).get("status", "")
                except Exception as fehler:
                    # Zuverlaessigkeit zuerst: laesst sich die Adresse nicht
                    # pruefen, geht sie NICHT in den Versand.
                    print(f"Firma '{firma.get('name') or firma.get('domain')}' "
                          f"übersprungen (Fehler bei der info@-Prüfung): {fehler}")
                    firmen_mit_ausgang.append({**firma, "ausgang": "fehler"})
                    continue
            if pruefstatus is not None:
                zusatz["info_pruefstatus"] = pruefstatus
            if pruefstatus is None or pruefstatus in INFO_OK_STATUS:
                leads.append(Lead(
                    first_name="", last_name="", email=info_email,
                    company=firmenname, title="", website=firma["website"],
                    source="info@"))
                firmen_mit_kontakt += 1
                ausgang = "info_fallback"
                je_stufe["info@"] += 1
            else:
                ausgang = "info_ungueltig"

        firmen_mit_ausgang.append({**firma, "ausgang": ausgang, **zusatz})

    anzahl_firmen = len(firmen)
    quote = (firmen_mit_kontakt / anzahl_firmen * 100) if anzahl_firmen else 0.0
    deckung = {"firmen_gesamt": anzahl_firmen, "firmen_mit_kontakt": firmen_mit_kontakt,
               "quote_prozent": round(quote, 1), "je_stufe": je_stufe}
    return leads, deckung, firmen_mit_ausgang

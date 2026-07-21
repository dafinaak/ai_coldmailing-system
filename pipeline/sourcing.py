"""Orchestriert die 3-stufige Lead-Beschaffung (Kern-Umbau).

Stufe 1: Firmen ueber Google Maps finden (pipeline.sources.apify_maps.
         ApifyMapsSource).
Stufe 2: Pro Firma Kontakte in den gewuenschten Rollen anreichern
         (pipeline.sources.apollo.ApolloSource.unternehmen_anreichern) -
         E-Mail-Suche JE UNTERNEHMEN, nicht die alte kriterien-basierte
         Massensuche (ApolloSource.search() bleibt fuer Rueckwaertskompatibilitaet
         bestehen, wird vom neuen Ablauf aber nicht mehr genutzt).
Stufe 3: Steckplatz fuer eine kuenftige dritte Datenbank (Hunter/Lusha/Clay
         - noch NICHT ausgewaehlt, siehe Auftrag). Aktuell ein reiner
         No-Op-Durchreicher (NoOpDrittquelle unten): liefert nie zusaetzliche
         Kontakte, macht den Ablauf aber unabhaengig davon, WOHER ein
         fehlender Kontakt irgendwann zusaetzlich kommen koennte - eine
         echte Implementierung ersetzt spaeter nur `drittquelle`.

info@-Regel: Findet Apollo fuer eine kleine Firma (<= 3 Mitarbeiter laut
Apollos "estimated_num_employees") keinen persoenlichen Kontakt, wird
info@<domain> als Lead-E-Mail verwendet (source="info@"). Greift NUR bei
tatsaechlich bekannter kleiner Mitarbeiterzahl (nicht bei unbekannter
Zahl - kein Rate-ins-Blaue) und nur, wenn eine Domain bekannt ist.

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
   Jobtiteln abgeglichen wurden. Fix: _rolle_passt()/_kontakte_auswaehlen()
   unten matchen ueber eine Synonym-Tabelle (deutsch<->englisch) und
   deckeln auf kunde.max_kontakte_pro_firma (Default 2), sortiert nach
   Rollen-Prioritaet aus kontakt_rollen (erste Rolle zuerst).
2) Ein Google-Maps-Titel enthielt den Suchbegriff als Praefix
   ("IT-Dienstleister Hannover - Ihre Helden" statt "Ihre Helden"). Fix:
   _firmenname_saeubern() unten - genutzt wird der Name aber nur als
   Rueckfallebene, bevorzugt wird Apollos kanonischer Organisationsname
   (ergebnis["name"]), wenn Apollo die Organisation gefunden hat."""
import re
from pipeline.models import Lead
from pipeline.sources.apify_maps import ApifyMapsSource
from pipeline.sources.apollo import ApolloSource

MITARBEITERZAHL_KLEINFIRMA = 3
MAX_KONTAKTE_PRO_FIRMA_STANDARD = 2  # siehe Kunde.max_kontakte_pro_firma (pipeline.config)

# Rollen-Synonym-Tabelle (Lead-Qualitaets-Fix): jede Gruppe fasst eine
# gewuenschte Rolle mit ihren deutschen UND englischen Entsprechungen
# zusammen, wie sie in echten Apollo-Jobtiteln vorkommen. Bewusst klein
# gehalten und leicht erweiterbar (einfach eine weitere Menge ergaenzen) -
# eine gewuenschte Rolle, die in KEINER Gruppe steckt, faellt in
# _rolle_passt() auf einen einfachen, verlustfreien Teilstring-Abgleich
# zurueck, matcht also weiterhin, nur eben ohne Synonyme.
ROLLEN_GRUPPEN = [
    {"geschäftsführer", "geschäftsführung", "managing director", "ceo",
     "inhaber", "owner", "gründer", "founder"},
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
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


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
    if not titel_norm or not rolle_norm:
        return False
    gruppe = _gruppe_fuer_rolle(rolle_norm)
    if gruppe is not None:
        return any(_enthaelt_als_wort(titel_norm, _normalisieren(s))
                    or _enthaelt_als_wort(_normalisieren(s), titel_norm)
                    for s in gruppe)
    return _enthaelt_als_wort(titel_norm, rolle_norm) or _enthaelt_als_wort(rolle_norm, titel_norm)


def _kontakte_auswaehlen(kontakte: list, kontakt_rollen: list, max_pro_firma: int) -> list:
    """Waehlt aus Apollos Rohkontakten einer Firma nur die aus, die zu einer
    gewuenschten Rolle passen (_rolle_passt), sortiert nach Rollen-Prioritaet
    (erste Rolle aus kontakt_rollen zuerst) und gedeckelt auf max_pro_firma.
    Ein Kontakt, der zu mehreren Rollen passt, wird nur einmal gezaehlt (bei
    der zuerst gefundenen, hoechst-priorisierten Rolle). Liefert eine LEERE
    Liste, wenn kein Kontakt zu irgendeiner gewuenschten Rolle passt - das
    Fallback-Verhalten dafuer (info@-Regel bzw. Best-Effort-1) entscheidet
    source_leads() unten, nicht diese Funktion."""
    passende = []
    for rolle in kontakt_rollen:
        for kontakt in kontakte:
            if kontakt in passende:
                continue
            if _rolle_passt(kontakt.get("title", ""), rolle):
                passende.append(kontakt)
    return passende[:max_pro_firma]


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


class NoOpDrittquelle:
    """Stufe-3-Steckplatz: liefert nie Kontakte. Sobald ein drittes Tool
    (Hunter/Lusha/Clay - noch nicht entschieden) feststeht, ersetzt eine
    echte Implementierung mit derselben Schnittstelle
    (finde_kontakte(firma) -> Liste von Kontakt-Dicts) diese Klasse."""
    def finde_kontakte(self, firma: dict) -> list:
        return []


def _pruefe_kunde(kunde):
    fehlend = [f for f in ("maps_suche", "kontakt_rollen") if not getattr(kunde, f, None)]
    if fehlend:
        raise ValueError(
            f"Für die Lead-Beschaffung fehlen im Kunden '{kunde.name}': "
            f"{', '.join(fehlend)}. 'maps_suche' ist der Google-Maps-Suchbegriff "
            f"(z.B. 'IT-Dienstleister Hannover'), 'kontakt_rollen' die gewünschten "
            f"Job-Titel (z.B. [Geschäftsführer, IT-Leiter]). Bitte in der Kunden-"
            f"Konfigurationsdatei ergänzen.")


def source_leads(kunde, limit, apify_key, apollo_key,
                  apify_source=None, apollo_source=None, drittquelle=None) -> tuple:
    """Fuehrt alle 3 Stufen aus und liefert (leads, deckung, firmen_mit_ausgang):
    - leads: Liste von pipeline.models.Lead (bestehende Form, downstream
      unveraendert nutzbar).
    - deckung: {"firmen_gesamt": int, "firmen_mit_kontakt": int,
      "quote_prozent": float} - die Deckungsquote fuer den Bericht.
    - firmen_mit_ausgang: die Stufe-1-Firmenliste aus Apify, JEDE Firma
      zusaetzlich um ein "ausgang"-Feld ergaenzt (Apollo-422-Fix): einer von
      "mit_kontakt" / "keine_webseite" / "apollo_kein_treffer" / "fehler".
      Zweck: kuenftige Laeufe sollen sauber unterscheiden koennen, WARUM eine
      Firma ohne Kontakt blieb (fehlende Webseite vs. Apollo hat wirklich
      nichts gefunden vs. ein technischer Fehler bei der Anreicherung) -
      vorher landete das alles ungetrennt in einer einzigen "kein Kontakt"-
      Zahl, was den echten Bug (422 bei Firmen ohne Webseite) verschleiert
      hat. __main__.lauf() persistiert diese Liste als firmen.json und
      zaehlt daraus die Aufschluesselung fuer den Bericht.

    `apify_source`/`apollo_source`/`drittquelle` sind fuer Tests injizierbar;
    im echten Betrieb baut diese Funktion die echten Klassen selbst mit den
    uebergebenen API-Keys."""
    _pruefe_kunde(kunde)
    apify = apify_source or ApifyMapsSource(apify_key)
    apollo = apollo_source or ApolloSource(apollo_key)
    dritt = drittquelle or NoOpDrittquelle()

    firmen = apify.search(kunde.maps_suche, limit)
    leads, firmen_mit_kontakt, firmen_mit_ausgang = [], 0, []
    for firma in firmen:
        try:
            ergebnis = apollo.unternehmen_anreichern(firma, kunde.kontakt_rollen)
        except Exception as fehler:
            # Eine einzelne fehlerhafte Firma (401/422 dauerhaft, oder ein
            # 500 das auch die Retries in ApolloSource ueberlebt hat) darf
            # bei ~50 Firmen pro Lauf nicht den kompletten Lauf mitreissen -
            # sonst sind alle bereits gefundenen Leads UND das bereits
            # verbrauchte Apify-/Apollo-Kontingent futsch. Diese Firma zaehlt
            # weiter zu firmen_gesamt (Nenner der Deckungsquote), aber nicht
            # zu firmen_mit_kontakt - sie verschlechtert nur die Zahl, statt
            # den Lauf zu sprengen. Die Fehlermeldungen aus ApolloSource
            # enthalten keine Secrets (Api-Key steht im Header, nicht im
            # geloggten Text), daher unbedenklich mitzuloggen.
            print(f"Firma '{firma.get('name') or firma.get('domain') or '?'}' "
                  f"übersprungen (Fehler bei der Kontakt-Anreicherung): {fehler}")
            firmen_mit_ausgang.append({**firma, "ausgang": "fehler"})
            continue

        kontakte_roh = ergebnis["kontakte"]
        mitarbeiterzahl = ergebnis["mitarbeiterzahl"]
        ist_kleinfirma = (mitarbeiterzahl is not None
                           and mitarbeiterzahl <= MITARBEITERZAHL_KLEINFIRMA)
        max_pro_firma = getattr(kunde, "max_kontakte_pro_firma", None) or MAX_KONTAKTE_PRO_FIRMA_STANDARD

        if kontakte_roh:
            # Apollo hat Kontakte geliefert - erst rollenbewusst filtern +
            # deckeln (Lead-Qualitaets-Fix), NICHT einfach alle uebernehmen.
            kontakte = _kontakte_auswaehlen(kontakte_roh, kunde.kontakt_rollen, max_pro_firma)
            if not kontakte and not ist_kleinfirma:
                # Kein einziger gelieferter Kontakt passt zu einer
                # gewuenschten Rolle, UND die Firma ist nicht klein genug
                # fuer die info@-Regel unten: statt die Firma komplett zu
                # verlieren, wird bewusst EIN Best-Effort-Kontakt behalten -
                # der erste von Apollo gelieferte (keine weitere Wertung,
                # da ohnehin keiner der Rollen entspricht).
                kontakte = kontakte_roh[:1]
            # Ist die Firma klein UND kein Kontakt passt zu einer Rolle,
            # bleibt `kontakte` bewusst leer: die Firma faellt unten in die
            # info@-Regel (nicht in die Drittquelle - Apollo hat ja
            # tatsaechlich geantwortet, nur eben ohne passenden Kontakt).
        else:
            # Apollo hat ueberhaupt keine Kontakte gefunden - hier (und nur
            # hier) kommt Stufe 3 (Drittquelle) zum Zug.
            kontakte = dritt.finde_kontakte(firma)

        # Firmenname: Apollos kanonischer Organisationsname wird bevorzugt
        # (Lead-Qualitaets-Fix - Apollo kennt den echten Namen, nicht nur
        # einen evtl. verunreinigten Google-Maps-Titel); nur wenn Apollo
        # keine Organisation gefunden hat (ergebnis["name"] ist None/leer),
        # wird der Maps-Titel als Rueckfallebene bereinigt.
        firmenname = ergebnis.get("name") or _firmenname_saeubern(
            firma.get("name", ""), kunde.maps_suche)

        hat_kontakt = False
        if kontakte:
            for k in kontakte:
                leads.append(Lead(
                    first_name=k.get("first_name", ""), last_name=k.get("last_name", ""),
                    email=k["email"], company=firmenname, title=k.get("title", ""),
                    website=firma["website"], source="apollo"))
            firmen_mit_kontakt += 1
            hat_kontakt = True
        elif ist_kleinfirma and firma.get("domain"):
            leads.append(Lead(
                first_name="", last_name="", email=f"info@{firma['domain']}",
                company=firmenname, title="", website=firma["website"], source="info@"))
            firmen_mit_kontakt += 1
            hat_kontakt = True

        # Ausgang-Aufschluesselung (Apollo-422-Fix): "keine_webseite" trennt
        # Firmen, die schon in Stufe 1 (Google Maps) ohne Webseite/Domain
        # ankamen, von "apollo_kein_treffer" (Domain/Webseite vorhanden,
        # aber weder Enrich noch Namens-Suche fanden eine Organisation bzw.
        # keiner der gefundenen Kontakte passte) - genau die Unterscheidung,
        # die vor dem Fix fehlte.
        if hat_kontakt:
            ausgang = "mit_kontakt"
        elif not firma.get("website"):
            ausgang = "keine_webseite"
        else:
            ausgang = "apollo_kein_treffer"
        firmen_mit_ausgang.append({**firma, "ausgang": ausgang})

    anzahl_firmen = len(firmen)
    quote = (firmen_mit_kontakt / anzahl_firmen * 100) if anzahl_firmen else 0.0
    deckung = {"firmen_gesamt": anzahl_firmen, "firmen_mit_kontakt": firmen_mit_kontakt,
               "quote_prozent": round(quote, 1)}
    return leads, deckung, firmen_mit_ausgang

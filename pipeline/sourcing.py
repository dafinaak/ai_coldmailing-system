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
geforderte "mindestens 80%"-Zahl (siehe pipeline.report)."""
from pipeline.models import Lead
from pipeline.sources.apify_maps import ApifyMapsSource
from pipeline.sources.apollo import ApolloSource

MITARBEITERZAHL_KLEINFIRMA = 3


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
    """Fuehrt alle 3 Stufen aus und liefert (leads, deckung):
    - leads: Liste von pipeline.models.Lead (bestehende Form, downstream
      unveraendert nutzbar).
    - deckung: {"firmen_gesamt": int, "firmen_mit_kontakt": int,
      "quote_prozent": float} - die Deckungsquote fuer den Bericht.

    `apify_source`/`apollo_source`/`drittquelle` sind fuer Tests injizierbar;
    im echten Betrieb baut diese Funktion die echten Klassen selbst mit den
    uebergebenen API-Keys."""
    _pruefe_kunde(kunde)
    apify = apify_source or ApifyMapsSource(apify_key)
    apollo = apollo_source or ApolloSource(apollo_key)
    dritt = drittquelle or NoOpDrittquelle()

    firmen = apify.search(kunde.maps_suche, limit)
    leads, firmen_mit_kontakt = [], 0
    for firma in firmen:
        ergebnis = apollo.unternehmen_anreichern(firma, kunde.kontakt_rollen)
        kontakte = ergebnis["kontakte"] or dritt.finde_kontakte(firma)
        if kontakte:
            for k in kontakte:
                leads.append(Lead(
                    first_name=k.get("first_name", ""), last_name=k.get("last_name", ""),
                    email=k["email"], company=firma["name"], title=k.get("title", ""),
                    website=firma["website"], source="apollo"))
            firmen_mit_kontakt += 1
        elif (ergebnis["mitarbeiterzahl"] is not None
              and ergebnis["mitarbeiterzahl"] <= MITARBEITERZAHL_KLEINFIRMA
              and firma.get("domain")):
            leads.append(Lead(
                first_name="", last_name="", email=f"info@{firma['domain']}",
                company=firma["name"], title="", website=firma["website"], source="info@"))
            firmen_mit_kontakt += 1

    anzahl_firmen = len(firmen)
    quote = (firmen_mit_kontakt / anzahl_firmen * 100) if anzahl_firmen else 0.0
    deckung = {"firmen_gesamt": anzahl_firmen, "firmen_mit_kontakt": firmen_mit_kontakt,
               "quote_prozent": round(quote, 1)}
    return leads, deckung

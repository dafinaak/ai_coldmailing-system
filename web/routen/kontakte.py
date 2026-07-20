"""Route fuer den Kontakte-Bereich (Task 8): eine rein lesende,
durchsuchbare Liste aller je gefundenen Kontakte ueber alle Kunden/Laeufe
hinweg. Die Aggregation selbst steckt in web.kontakte.sammle_kontakte
(Dateisystem-only, kein Instantly-Zugriff) - diese Route filtert das
Ergebnis nur noch nach der Suche aus dem GET-Parameter 'q' (serverseitig,
wie im Plan gefordert: 'Suche (ein Feld, filtert über alle Spalten,
serverseitig)'). Keine POST-Route - der Bereich ist bewusst rein lesend."""
from __future__ import annotations

from fastapi import APIRouter, Request

from web import auth
from web.kontakte import sammle_kontakte
from web.nav import nav_kontext

router = APIRouter()

# Alle Spalten der Tabelle (siehe kontakte.html) - die Suche durchsucht sie
# alle, nicht nur die drei im Platzhaltertext genannten (Name/Firma/
# E-Mail-Adresse), damit z.B. auch "nie angeschrieben" oder ein Kunden-/
# Kampagnen-Name als Suchbegriff funktionieren.
_SUCH_FELDER = ("name", "firma", "email", "kunde", "kampagne", "zuletzt")


def _passt_zur_suche(kontakt: dict, suche_klein: str) -> bool:
    return any(suche_klein in str(kontakt.get(feld, "")).lower() for feld in _SUCH_FELDER)


@router.get("/kontakte")
async def kontakte_liste(request: Request):
    daten_dir = request.app.state.daten_dir
    suche = request.query_params.get("q", "").strip()
    kontakte = sammle_kontakte(daten_dir)
    if suche:
        suche_klein = suche.lower()
        kontakte = [k for k in kontakte if _passt_zur_suche(k, suche_klein)]

    return request.app.state.templates.TemplateResponse(
        request, "kontakte.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "kontakte": kontakte,
            "kontakte_leer": len(kontakte) == 0,
            "kontakt_suche": suche,
            "anzahl": len(kontakte),
        },
    )

"""Route fuer die Einstiegsseite "So funktioniert's" (Copy-Rework,
20.07.2026, siehe docs/copy-rework-brief.md): zeigt die vier Schritte des
Systems in Alltagssprache. web.routen.dashboard leitet einen angemeldeten
Nutzer OHNE das Cookie 'intro_gesehen' beim Aufruf von '/' einmalig hierher
um (siehe INTRO_COOKIE dort importiert); danach ist die Seite jederzeit
ueber den Seitenleisten-Eintrag "So funktioniert's" (web.nav.NAV_BEREICHE)
wieder erreichbar. Der Knopf "Verstanden, los geht's" setzt das Cookie
(POST statt GET, damit ein einfacher Seiten-Reload/Prefetch es nicht aus
Versehen auf 'gesehen' setzt) und schickt zurueck aufs Dashboard.

Bewusst rein Cookie-basiert, kein Server-State pro Nutzer (Plan-Vorgabe:
"No per-user server state needed") - einfach, robust, jederzeit erneut
wegklickbar."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from web import auth
from web.nav import nav_kontext

router = APIRouter()

INTRO_COOKIE = "intro_gesehen"
INTRO_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 Jahr - lang genug, dass es praktisch nicht abläuft


@router.get("/so-funktionierts")
async def so_funktionierts(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "so_funktionierts.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
        },
    )


@router.post("/so-funktionierts/verstanden")
async def so_funktionierts_verstanden(request: Request):
    antwort = RedirectResponse("/", status_code=303)
    antwort.set_cookie(
        INTRO_COOKIE, "1",
        max_age=INTRO_COOKIE_MAX_AGE,
        httponly=False,  # rein informativ, kein Sicherheits-Cookie - darf clientseitig lesbar sein
        samesite="lax",
    )
    return antwort

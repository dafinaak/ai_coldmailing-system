"""FastAPI-Fabrik fuers Team-Interface. `create_app(daten_dir)` baut eine
App fuer genau ein Datenverzeichnis - dort liegen users.yaml, kunden/,
laeufe/ und sperrliste-global.yaml (letztere drei kommen erst in spaeteren
Paketen dazu, dieses Paket legt nur das Geruest mit Anmeldung an)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer

from . import auth
from .nav import NAV_BEREICHE, nav_kontext
from .routen import auftraege as auftraege_routen
from .routen import dashboard as dashboard_routen
from .routen import freigabe as freigabe_routen
from .routen import kampagnen as kampagnen_routen
from .routen import kunden as kunden_routen
from .routen import sperrliste as sperrliste_routen

BASIS = Path(__file__).resolve().parent

# NAV_BEREICHE (siehe web/nav.py) listet alle sieben Bereiche - solange das
# zugehoerige Paket zu einem Bereich noch nicht gebaut ist, zeigt er nur
# eine Platzhalterseite, damit die Navigation nie ins Leere (404) laeuft.
# Bereiche mit eigenem Routen-Modul werden unten aus dieser Liste
# ausgenommen, sobald ihre echte Route registriert ist.
BEREICHE_MIT_EIGENER_ROUTE = {"dashboard", "domains", "kunden", "pruefen", "kampagnen"}


def create_app(daten_dir: Path) -> FastAPI:
    daten_dir = Path(daten_dir)
    daten_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI()
    app.state.daten_dir = daten_dir
    app.state.secret = auth.hole_secret()
    app.state.serializer = URLSafeTimedSerializer(app.state.secret, salt=auth.SESSION_SALT)

    app.mount("/static", StaticFiles(directory=str(BASIS / "static")), name="static")
    templates = Jinja2Templates(directory=str(BASIS / "templates"))
    app.state.templates = templates

    app.add_middleware(auth.AnmeldePflicht)

    app.include_router(sperrliste_routen.router)
    app.include_router(kunden_routen.router)
    app.include_router(auftraege_routen.router)
    app.include_router(freigabe_routen.router)
    app.include_router(kampagnen_routen.router)
    app.include_router(dashboard_routen.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/login")
    async def login_form(request: Request):
        if auth.aktueller_nutzer(request) is not None:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(request, "login.html", {"fehler": None})

    @app.post("/login")
    async def login_absenden(
        request: Request, name: str = Form(...), passwort: str = Form(...)
    ):
        nutzer = auth.lade_nutzer(daten_dir)
        if not auth.pruefe_passwort(nutzer, name, passwort):
            return templates.TemplateResponse(
                request,
                "login.html",
                {"fehler": "Name oder Passwort stimmt nicht."},
                status_code=401,
            )
        antwort = RedirectResponse("/", status_code=303)
        auth.setze_session_cookie(antwort, request, name)
        return antwort

    @app.post("/logout")
    async def logout(request: Request):
        antwort = RedirectResponse("/login", status_code=303)
        auth.loesche_session_cookie(antwort)
        return antwort

    def mache_platzhalter_route(label: str):
        async def route(request: Request):
            return templates.TemplateResponse(
                request,
                "platzhalter.html",
                {
                    "titel": label,
                    "nutzer": auth.aktueller_nutzer(request),
                    "nav": nav_kontext(request),
                },
            )

        return route

    for key, url, label in NAV_BEREICHE:
        if key in BEREICHE_MIT_EIGENER_ROUTE:
            continue
        app.add_api_route(url, mache_platzhalter_route(label), methods=["GET"])

    return app

"""FastAPI-Fabrik fuers Team-Interface. `create_app(daten_dir)` baut eine
App fuer genau ein Datenverzeichnis - dort liegen users.yaml, kunden/,
laeufe/ und sperrliste-global.yaml (letztere drei kommen erst in spaeteren
Paketen dazu, dieses Paket legt nur das Geruest mit Anmeldung an)."""
from __future__ import annotations

import os
import threading
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
from .routen import intro as intro_routen
from .routen import kontakte as kontakte_routen
from .routen import kunden as kunden_routen
from .routen import postfach as postfach_routen
from .routen import postfaecher as postfaecher_routen
from .routen import sperrliste as sperrliste_routen

BASIS = Path(__file__).resolve().parent

# NAV_BEREICHE (siehe web/nav.py) listet alle sieben Bereiche - solange das
# zugehoerige Paket zu einem Bereich noch nicht gebaut ist, zeigt er nur
# eine Platzhalterseite, damit die Navigation nie ins Leere (404) laeuft.
# Bereiche mit eigenem Routen-Modul werden unten aus dieser Liste
# ausgenommen, sobald ihre echte Route registriert ist.
BEREICHE_MIT_EIGENER_ROUTE = {"dashboard", "domains", "kunden", "pruefen", "kampagnen", "kontakte",
                               "postfach", "postfaecher", "so-funktionierts"}


def create_app(daten_dir: Path) -> FastAPI:
    daten_dir = Path(daten_dir)
    daten_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI()
    app.state.daten_dir = daten_dir
    app.state.secret = auth.hole_secret()
    app.state.serializer = URLSafeTimedSerializer(app.state.secret, salt=auth.SESSION_SALT)

    # IMPORTANT Review-Fund: EIN InstantlyLeser fuer die ganze App-Laufzeit
    # (statt einem frischen pro Request) - sonst ist der 60s-Cache in
    # web.instantly_leser.InstantlyLeser nie wirksam. app.state.instantly_
    # leser bleibt None, wenn INSTANTLY_API_KEY hier noch fehlt (dann baut
    # web.instantly_leser.geteilten_leser ihn beim ersten Bedarf, siehe
    # dort) - Tests setzen app.state.instantly_leser weiterhin selbst
    # (gewinnt in _hole_leser vor allem anderen, unveraendertes Muster).
    app.state.instantly_leser = None
    app.state._instantly_leser_lock = threading.Lock()
    app.state.instantly_antworter = None
    app.state._instantly_antworter_lock = threading.Lock()
    if os.environ.get("INSTANTLY_API_KEY"):
        from .instantly_leser import InstantlyLeser
        from .instantly_antworter import InstantlyAntworter

        app.state.instantly_leser = InstantlyLeser(os.environ["INSTANTLY_API_KEY"])
        app.state.instantly_antworter = InstantlyAntworter(
            os.environ["INSTANTLY_API_KEY"]
        )

    app.mount("/static", StaticFiles(directory=str(BASIS / "static")), name="static")
    templates = Jinja2Templates(directory=str(BASIS / "templates"))
    app.state.templates = templates

    app.add_middleware(auth.AnmeldePflicht)

    app.include_router(sperrliste_routen.router)
    app.include_router(kunden_routen.router)
    app.include_router(auftraege_routen.router)
    app.include_router(freigabe_routen.router)
    app.include_router(kampagnen_routen.router)
    app.include_router(kontakte_routen.router)
    app.include_router(postfach_routen.router)
    app.include_router(postfaecher_routen.router)
    app.include_router(dashboard_routen.router)
    app.include_router(intro_routen.router)

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

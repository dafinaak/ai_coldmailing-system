"""Anmeldung fuers Team-Interface: Nutzerliste aus users.yaml (bcrypt-Hashes),
signierte Session-Cookies (itsdangerous) und die Middleware, die alle Routen
ausser /login, /health und /static/* hinter die Anmeldung stellt - so erben
spaetere Pakete den Schutz automatisch, ohne ihn pro Route einzubauen."""
from __future__ import annotations

import os
from pathlib import Path

import yaml
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

COOKIE_NAME = "poleposition_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 14  # 14 Tage angemeldet bleiben
SESSION_SALT = "poleposition-session"

# Diese Pfade sind ohne Anmeldung erreichbar. /static/* traegt hier keine
# eigene Route, sondern ein Praefix - Bilder/CSS muessen auch auf der
# Login-Seite laden, bevor jemand angemeldet ist.
OFFENE_PFADE = {"/login", "/health"}
OFFENE_PRAEFIXE = ("/static/",)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hole_secret() -> str:
    """Liest WEB_SECRET aus der Umgebung. Bricht mit einer klaren deutschen
    Fehlermeldung ab, wenn die Variable fehlt - ohne eigenes Secret koennte
    jeder sich selbst eine gueltige Session faelschen."""
    secret = os.environ.get("WEB_SECRET")
    if not secret:
        raise RuntimeError(
            "Fehlende Umgebungsvariable: WEB_SECRET. Bitte in .env eintragen "
            "(ein zufaelliger Text als Wert reicht, z.B. erzeugt mit "
            "`openssl rand -hex 32`)."
        )
    return secret


def lade_nutzer(daten_dir: Path) -> list[dict]:
    """Liest users.yaml aus dem Datenverzeichnis: eine Liste aus
    {name, passwort_hash}. Fehlt die Datei, gibt es (noch) keine Nutzer -
    dann kann sich niemand anmelden, aber die App startet trotzdem."""
    pfad = Path(daten_dir) / "users.yaml"
    if not pfad.exists():
        return []
    return yaml.safe_load(pfad.read_text(encoding="utf-8")) or []


def pruefe_passwort(nutzer: list[dict], name: str, passwort: str) -> bool:
    """Prueft Name und Passwort gegen die geladene Nutzerliste."""
    for eintrag in nutzer:
        if eintrag.get("name") == name:
            return _pwd_context.verify(passwort, eintrag.get("passwort_hash", ""))
    return False


def aktueller_nutzer(request: Request) -> str | None:
    """Liest den Namen aus dem signierten Session-Cookie, falls vorhanden
    und gueltig. None heisst: nicht angemeldet (oder Session abgelaufen/
    manipuliert)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    serializer: URLSafeTimedSerializer = request.app.state.serializer
    try:
        return serializer.loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def setze_session_cookie(response, request: Request, name: str) -> None:
    """Schreibt den signierten Session-Cookie nach erfolgreichem Login."""
    serializer: URLSafeTimedSerializer = request.app.state.serializer
    response.set_cookie(
        COOKIE_NAME,
        serializer.dumps(name),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def loesche_session_cookie(response) -> None:
    """Loescht den Session-Cookie beim Abmelden."""
    response.delete_cookie(COOKIE_NAME)


class AnmeldePflicht(BaseHTTPMiddleware):
    """Verlangt fuer jede Route ausser den offenen Pfaden eine gueltige
    Session; sonst Redirect (303) auf /login. Als Middleware statt als
    Dependency pro Route, damit spaetere Pakete den Schutz automatisch
    mitbekommen, sobald sie eine neue Route hinzufuegen."""

    async def dispatch(self, request: Request, call_next):
        pfad = request.url.path
        if pfad in OFFENE_PFADE or pfad.startswith(OFFENE_PRAEFIXE):
            return await call_next(request)
        if aktueller_nutzer(request) is None:
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)

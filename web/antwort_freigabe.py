"""Signierte, einmalige Freigaben für schreibende Postfach-Antworten."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import secrets

from itsdangerous import BadData

TOKEN_SALT = "postfach-antwort"
TOKEN_MAX_AGE = 15 * 60
ERFOLG_SALT = "postfach-antwort-erfolg"
ERFOLG_MAX_AGE = 5 * 60
MAX_ANTWORT_ZEICHEN = 10_000


class AntwortFreigabeUngueltig(ValueError):
    pass


class AntwortFreigabeBenutzt(ValueError):
    pass


class AntwortTextUngueltig(ValueError):
    pass


def erstelle_antwort_freigabe(
    serializer, *, kontakt: str, reply_to_uuid: str
) -> str:
    daten = {
        "kontakt": kontakt.strip().casefold(),
        "reply_to_uuid": reply_to_uuid.strip(),
        "nonce": secrets.token_urlsafe(24),
    }
    if not daten["kontakt"] or not daten["reply_to_uuid"]:
        raise AntwortFreigabeUngueltig("Das Antwortziel ist unvollständig.")
    return serializer.dumps(daten, salt=TOKEN_SALT)


def pruefe_antwort_freigabe(serializer, token: str) -> dict:
    try:
        daten = serializer.loads(
            token, max_age=TOKEN_MAX_AGE, salt=TOKEN_SALT
        )
    except BadData as fehler:
        raise AntwortFreigabeUngueltig(
            "Die Antwortfreigabe ist abgelaufen oder ungültig."
        ) from fehler
    if not isinstance(daten, dict) or set(daten) != {
        "kontakt", "reply_to_uuid", "nonce"
    }:
        raise AntwortFreigabeUngueltig(
            "Die Antwortfreigabe ist unvollständig."
        )
    if not all(
        isinstance(daten[feld], str) and daten[feld] for feld in daten
    ):
        raise AntwortFreigabeUngueltig(
            "Die Antwortfreigabe ist unvollständig."
        )
    return daten


def erstelle_versandhinweis(
    serializer, *, kontakt: str, antwort_id: str
) -> str:
    return serializer.dumps(
        {
            "kontakt": kontakt.strip().casefold(),
            "antwort_id": antwort_id.strip(),
        },
        salt=ERFOLG_SALT,
    )


def pruefe_versandhinweis(
    serializer, token: str, *, kontakt: str
) -> bool:
    if not token:
        return False
    try:
        daten = serializer.loads(
            token, max_age=ERFOLG_MAX_AGE, salt=ERFOLG_SALT
        )
    except BadData:
        return False
    return (
        isinstance(daten, dict)
        and set(daten) == {"kontakt", "antwort_id"}
        and daten.get("kontakt") == kontakt.strip().casefold()
        and isinstance(daten.get("antwort_id"), str)
        and bool(daten["antwort_id"])
    )


def validiere_antworttext(text: str) -> str:
    bereinigt = text.strip()
    if not bereinigt:
        raise AntwortTextUngueltig("Die Antwort darf nicht leer sein.")
    if len(bereinigt) > MAX_ANTWORT_ZEICHEN:
        raise AntwortTextUngueltig(
            "Die Antwort darf höchstens 10.000 Zeichen lang sein."
        )
    return bereinigt


def verbrauche_antwort_freigabe(daten_dir: Path, nonce: str) -> Path:
    digest = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
    ordner = Path(daten_dir) / "postfach-antworten"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{digest}.verbraucht"
    try:
        datei = os.open(
            ziel,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError as fehler:
        raise AntwortFreigabeBenutzt(
            "Diese Antwortfreigabe wurde bereits benutzt."
        ) from fehler
    os.close(datei)
    return ziel

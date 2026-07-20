"""Produktions-Einstiegspunkt fuers Team-Interface: `uvicorn web.main:app`.

Baut die FastAPI-App ueber web.app.create_app mit dem Datenverzeichnis aus
der Umgebungsvariable DATEN_DIR - dort liegen users.yaml, kunden/, laeufe/
und sperrliste-global.yaml (siehe web.app.create_app-Docstring). DATEN_DIR
ist bewusst PFLICHT (kein stiller Default wie z.B. das aktuelle
Arbeitsverzeichnis): ein falsches/leeres Datenverzeichnis wuerde beim ersten
Seitenaufruf einfach "keine Kunden/Auftraege" zeigen statt klar zu sagen,
dass die Variable fehlt - im Deployment (eigenes Daten-Volume, siehe
web/laufmanager.py Modul-Kommentar zu Task 10) ist das ein Stolperstein, der
lange unbemerkt bleiben kann.

Fehlt DATEN_DIR, bricht der Import mit einer klaren deutschen Fehlermeldung
ab (gleiches Prinzip wie web.auth.hole_secret fuer WEB_SECRET) statt mit
einem kryptischen Fehler tief in create_app oder gar ohne jede Fehlermeldung
gegen das falsche Verzeichnis zu laufen.

Lokal ausserhalb von uvicorn ('python -m web.main' bzw. 'python
web/main.py') startet der `if __name__ == "__main__"`-Block einen
Entwicklungsserver."""
from __future__ import annotations

import os

from web.app import create_app

DATEN_DIR_FEHLER = (
    "Fehlende Umgebungsvariable: DATEN_DIR. Bitte DATEN_DIR auf das "
    "Datenverzeichnis setzen (dort liegen users.yaml, kunden/, laeufe/ und "
    "sperrliste-global.yaml), z.B. DATEN_DIR=/pfad/zu/daten "
    "uvicorn web.main:app."
)


def _daten_dir() -> str:
    wert = os.environ.get("DATEN_DIR")
    if not wert:
        raise RuntimeError(DATEN_DIR_FEHLER)
    return wert


app = create_app(_daten_dir())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

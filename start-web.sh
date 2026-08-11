#!/usr/bin/env bash
# Startet das Team-Interface lokal.
#
# Hintergrund: web/main.py liest die .env NICHT selbst (anders als die
# Pipeline). Die Variablen muessen also schon in der Shell stehen, bevor
# uvicorn startet - genau das macht dieses Skript.
#
# Benutzung:   ./start-web.sh          (Port 8000)
#              ./start-web.sh 8080     (anderer Port)
set -euo pipefail

PROJEKT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJEKT"

if [ ! -f .env ]; then
  echo "Es gibt keine .env im Projektordner. Bitte anlegen (Vorlage: .env.example)." >&2
  exit 1
fi

# .env einlesen und alle Werte an die App weitergeben
set -a
# shellcheck disable=SC1091
. ./.env
set +a

# Datenverzeichnis: hier liegen users.yaml, kunden/, laeufe/ und
# sperrliste-global.yaml - beim lokalen Arbeiten ist das der Projektordner.
export DATEN_DIR="${DATEN_DIR:-$PROJEKT}"

PORT="${1:-8000}"

echo "Interface laeuft gleich auf http://127.0.0.1:$PORT  (Beenden mit Strg+C)"
exec .venv/bin/python -m uvicorn web.main:app --host 127.0.0.1 --port "$PORT"

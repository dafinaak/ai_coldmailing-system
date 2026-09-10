#!/bin/sh
# Die zwei Rollen des DataWarehouse (Phase 3, 08.09.2026).
#
#     coldmail_sync   kern:     SELECT INSERT UPDATE DELETE
#                     historie: NUR SELECT und INSERT
#     coldmail_read   ueberall: NUR SELECT
#
# Warum coldmail_sync die Historie nicht aendern und nicht loeschen darf:
# ein Fehler im Sync der Phase 6 - eine falsche WHERE-Bedingung reicht -
# wuerde sonst Widersprueche wegraeumen. Danach schreiben wir Leuten, die
# Nein gesagt haben. Das ist der eine Schaden, den man nicht zuruecknehmen
# kann, also nimmt die Datenbank dem Sync die Moeglichkeit ganz weg.
#
# Ein .sh (kein .sql), weil die Passwoerter aus der Umgebung kommen und
# nicht im Git stehen sollen. Uebergeben werden sie als psql-Variablen
# und mit :'name' eingesetzt - psql zitiert dann selbst richtig.

set -e

: "${COLDMAIL_SYNC_PASSWORD:?COLDMAIL_SYNC_PASSWORD fehlt}"
: "${COLDMAIL_READ_PASSWORD:?COLDMAIL_READ_PASSWORD fehlt}"

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v sync_pw="$COLDMAIL_SYNC_PASSWORD" \
     -v read_pw="$COLDMAIL_READ_PASSWORD" <<'EOSQL'

CREATE ROLE coldmail_sync LOGIN PASSWORD :'sync_pw';
CREATE ROLE coldmail_read LOGIN PASSWORD :'read_pw';

-- Niemand bekommt etwas, was nicht ausdruecklich vergeben wird.
REVOKE ALL ON SCHEMA kern, historie FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA kern, historie FROM PUBLIC;

GRANT CONNECT ON DATABASE :"DBNAME" TO coldmail_sync, coldmail_read;
GRANT USAGE ON SCHEMA kern, historie TO coldmail_sync, coldmail_read;

-- Den Stand der Datenbank darf jeder lesen, der sich verbindet - sonst
-- muesste der Sync raten, welches Schema er vor sich hat. Schreiben darf
-- ihn nur der Eigentuemer: Migrationen sind keine Sync-Aufgabe.
GRANT USAGE ON SCHEMA public TO coldmail_sync, coldmail_read;
GRANT SELECT ON public.schema_version TO coldmail_sync, coldmail_read;


-- ---------------------------------------------------------- coldmail_sync

-- kern ist ein Spiegel: alles darin ist aus master.db wieder herstellbar,
-- also darf der Sync es umschreiben.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA kern TO coldmail_sync;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA kern TO coldmail_sync;

-- historie ist es NICHT. Lesen und anhaengen ja, aendern und loeschen
-- nein - genau hier liegt der Schutz.
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA historie TO coldmail_sync;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA historie TO coldmail_sync;


-- ---------------------------------------------------------- coldmail_read

GRANT SELECT ON ALL TABLES IN SCHEMA kern, historie TO coldmail_read;


-- --------------------------------------------------- kuenftige Tabellen
--
-- Ohne das haette eine spaeter angelegte Tabelle gar keine Rechte, und
-- jemand wuerde sie im Eifer mit einem breiten GRANT nachreichen. Die
-- Vorgaben halten die Trennung von selbst durch.

ALTER DEFAULT PRIVILEGES IN SCHEMA kern
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO coldmail_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA kern
    GRANT USAGE, SELECT ON SEQUENCES TO coldmail_sync;

ALTER DEFAULT PRIVILEGES IN SCHEMA historie
    GRANT SELECT, INSERT ON TABLES TO coldmail_sync;
ALTER DEFAULT PRIVILEGES IN SCHEMA historie
    GRANT USAGE, SELECT ON SEQUENCES TO coldmail_sync;

ALTER DEFAULT PRIVILEGES IN SCHEMA kern, historie
    GRANT SELECT ON TABLES TO coldmail_read;

EOSQL

echo "Rollen coldmail_sync und coldmail_read angelegt."

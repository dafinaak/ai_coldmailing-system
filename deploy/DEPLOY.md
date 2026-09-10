# Deployment des Team-Interface auf den Arbeitsserver

Server: prod-srv01-automations (Hetzner, 178.104.175.42), Zugang per SSH
(Schluessel im ViralLab-Ordner, Passwort im macOS-Schluesselbund:
`ssh-add --apple-use-keychain server/id_ed25519`).

## Aufbau auf dem Server

```
/opt/coldmailing/
├── app/              Code (rsync aus dem Projektordner, ohne .env/.venv/laeufe)
│   ├── Dockerfile
│   ├── deploy/…
│   ├── pipeline/  web/  prompts/
├── daten/            Volume: kunden/, laeufe/, sperrliste-global.yaml, users.yaml
├── .env              Schluessel (APIFY/HUNTER/DROPCONTACT/OPENROUTER|ANTHROPIC/INSTANTLY, WEB_SECRET)
│                     -> wird per compose env_file in den Container injiziert
└── ERSTZUGANG.txt    Start-Passwoerter (chmod 600) - nach Uebergabe LOESCHEN
```

## Ablauf (einmalig)

1. Code synchronisieren:
   `rsync -a --delete --exclude .venv --exclude .env --exclude laeufe --exclude .superpowers --exclude .git "AI Coldmailing system/" admin@178.104.175.42:/opt/coldmailing/app/`
2. `.env` auf dem Server anlegen (nie committen), `daten/`-Struktur anlegen,
   `users.yaml` mit Team-Namen + bcrypt-Hashes (Hash erzeugen:
   `python3 -c "from passlib.hash import bcrypt; print(bcrypt.hash('...'))"`)
3. Bauen + starten:
   `cd /opt/coldmailing/app && sudo docker compose -f deploy/docker-compose.coldmail.yml up -d --build`
4. nginx: `deploy/nginx-mailingsystem.conf` nach
   `/opt/content-intelligence/nginx/conf.d/mailingsystem.conf` kopieren,
   dann `sudo docker exec ci-nginx nginx -t && sudo docker exec ci-nginx nginx -s reload`
5. Smoke-Test: `https://mailingsystem.polepositionautomation.de/health`,
   Login, Kunden-Seite; PFLICHT laut Plan: ein Mini-Lauf (limit 1-2) der
   beweist, dass die Schluessel im Pipeline-Unterprozess ankommen.

## Update-Deployment (spaeter)

Schritt 1 + `up -d --build` genuegen. Daten unter /opt/coldmailing/daten
bleiben unangetastet. Empfehlung ans Team: daten/ in die Server-Backups
aufnehmen.

## DataWarehouse-Postgres (Phase 3, 08.09.2026) - EIGENER Stack

Zweiter, unabhaengiger Dienst: `deploy/docker-compose.postgres.yml`. Er
ist NICHT Teil von `docker-compose.coldmail.yml` und wird getrennt
gestartet:

```
cd /opt/coldmailing/app
sudo docker compose --env-file /opt/coldmailing/.env \
     -f deploy/docker-compose.postgres.yml up -d
```

**Er haengt bewusst NICHT im `content-intelligence_ci-network`.** Das ist
eine Sicherheitsentscheidung, keine Bequemlichkeit: die Bindung an
127.0.0.1 schuetzt nur vor dem Netz AUSSERHALB des Servers. Container im
selben Docker-Netz erreichen sich untereinander direkt auf Port 5432,
an der Host-Bindung vorbei. Im ci-network haetten also ci-nginx und
jeder andere ViralLab-Dienst freien Zugriff auf die Datenbank. Solange
niemand ihn braucht, bleibt der Postgres allein in seinem eigenen Netz.

Wer ihn spaeter doch verbinden muss (Phase 6, falls der Sync IM
coldmail-web-Container laeuft): ein eigenes Netz nur fuer diese zwei
Container anlegen - nicht den Postgres ins ci-network haengen. Laeuft
der Sync stattdessen als cron auf dem Host, genuegt 127.0.0.1:5433 und
es aendert sich gar nichts.

**Das Interface braucht diesen Dienst nicht.** Geprueft am 08.09.2026 mit
gestopptem Postgres: `/health` -> 200 `{"status":"ok"}`, `/login` -> 200,
geschuetzte Seiten -> 303 auf den Login, im Log kein einziger Hinweis auf
psycopg oder Postgres. Faellt die Datenbank aus, laeuft das Mailing
weiter; nur der Spiegel fuer Oliver ist dann veraltet.

### Zugangsdaten

In `/opt/coldmailing/.env` (nie committen), Vorlage in `.env.example`:
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`,
`COLDMAIL_SYNC_PASSWORD`, `COLDMAIL_READ_PASSWORD` und die drei URLs
`POSTGRES_URL` / `POSTGRES_SYNC_URL` / `POSTGRES_READ_URL`. Fehlt eines
der Passwoerter, startet der Container absichtlich nicht.

### Was Oliver liest

```
SELECT * FROM datawarehouse;
```

Eine Ansicht in `public` mit 46 Spalten in seiner Reihenfolge (Phase 4,
`deploy/postgres/03-datawarehouse.sql`). Nur `coldmail_read` darf sie
lesen; `coldmail_sync` bekommt bewusst kein Recht darauf.

Zusammengelegte Firmen (`zusammengelegt_in` gesetzt) erscheinen NICHT -
sonst saehe er die alte Zeile und die ueberlebende nebeneinander. Die
Zeile selbst bleibt in `kern.firma` stehen, damit ihre Historie lesbar
bleibt.

**Die Spaltenzahl 46 stimmt mit Olivers Feldliste ueberein** (Mail "AW:
DataWarehouse - Datenbank-Felder"): seine Liste hat genau 46 Eintraege,
jeder hat hier seine Spalte.

Olivers Bezeichnungen wurden ueberall dort uebernommen, wo der
Unterschied ein echter ist (Entscheidung Dafina, 08./09.09.2026):

| Olivers Name | vorher bei uns |
|---|---|
| `Daten-Ursprung (woher/von wem, wann)` | Datenquelle (woher, wann) |
| `Branche` | Sektor |
| `Selektions-Keywords` | Auswahl-Stichworte |
| `www` | Webseite |
| `A-E) Entscheider-Bereich (für welches Produkt)` | A-E) Bereich |
| `A-E) Entscheider-Position` | A-E) Rolle |

Bewusst NICHT geaendert, weil es reine Schreibweisen sind: `Straße`
(er schreibt Strasse), `Kurzbeschreibung`, `Mitarbeiterzahl`,
`E-Mail (allgemein)`, und die kurzen Ueberschriften `1./2./3. Kontakt` -
Olivers lange Klammern dort beschreiben den Inhalt des Feldes, sie sind
keine Spaltennamen.

Dass im A-E-Block nur `Entscheider-Bereich` und `Entscheider-Position`
das Praefix tragen, `Name`, `Tel` und `E-Mail` aber nicht, ist eine
bewusste Entscheidung von Dafina - kein Versehen. Nicht der Symmetrie
wegen angleichen.

`(für welches Produkt)` gehoert zu Olivers Feldnamen. Geliefert wird
unveraendert der Bereich der Person aus ihrer Rolle
(`pipeline/bereich.py`); ein Produkt wird NICHT erfunden, dazu gaebe es
in unseren Daten auch nichts.

Offen ist nur noch, ob Oliver mit den beibehaltenen Namen einverstanden
ist. Kommt eine Korrektur, aendern sich `pipeline/master_db.py`,
`03-datawarehouse.sql` und `tests/postgres/test_datawarehouse.py`
zusammen - der Provenance-Test haelt sie aneinander.

### Schema-Aenderungen

Die Skripte in `deploy/postgres/` laufen NUR beim allerersten Start mit
leerem Volume. Auf einem Server mit Daten ist eine Aenderung deshalb ein
`ALTER` von Hand - und dabei gehoert eine Zeile in
`public.schema_version` (Version hochzaehlen, Notiz dazu), sonst weiss
niemand mehr, welchen Stand eine Datenbank hat.

Stand heute: **Version 2** (1 = Schema und Rollen, 2 = Ansicht
datawarehouse). Auf einer Datenbank, die schon auf Version 1 laeuft,
wird `03-datawarehouse.sql` einmal von Hand eingespielt:

```
sudo docker exec -i coldmail-postgres psql -U coldmail -d coldmail \
     < deploy/postgres/03-datawarehouse.sql
```

Das Skript traegt seine Version selbst ein. Pruefen mit
`SELECT MAX(version) FROM public.schema_version;`

`down -v` loescht das Volume und spielt das Schema neu ein. Auf dem
Server heisst das: alle gespiegelten Daten weg. `down` ohne `-v` ist
harmlos.

### Backup

`stamm.db` und `historie.db` unter `/opt/coldmailing/daten` sind die
Quellen, die sich NICHT wiederherstellen lassen - sie gehoeren ins
Backup. Der Postgres selbst ist ein Spiegel und liesse sich neu
befuellen, das Backup davon ist Komfort, keine Pflicht.

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

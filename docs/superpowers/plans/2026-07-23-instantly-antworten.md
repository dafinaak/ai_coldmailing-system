# Instantly-Antworten im internen Postfach – Bauplan

> **Für ausführende Agenten:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Ziel:** Ein angemeldetes Teammitglied kann im vorhandenen internen
Kampagnenpostfach genau einmal auf eine belegte empfangene Instantly-Mail
antworten, ohne Gmail oder Microsoft mit dem Tool zu verbinden.

**Aufbau:** `InstantlyLeser` erhält die für eine Antwort nötigen belegten
Mailfelder. Ein neuer, kleiner `InstantlyAntworter` kapselt ausschließlich den
offiziellen Instantly-Antwort-Endpunkt. Eine getrennte Freigabekomponente
signiert das Ziel und verbraucht jede Freigabe vor dem externen Aufruf atomar,
damit Doppelklicks und wiederholte Formularaufrufe keinen zweiten Versand
auslösen.

**Technik:** Python 3.14, FastAPI, Jinja2, requests, itsdangerous, pytest,
vorhandenes CSS ohne neue Laufzeit-Abhängigkeit.

## Globale Regeln

- Instantly bleibt der einzige Mail-Zugang und Versand-Motor.
- Keine Gmail-/Microsoft-Anmeldung, keine Google-/Microsoft-Zugangsdaten.
- Nur Antworten auf eine bestehende empfangene Instantly-Mail; kein freier
  Versand, kein Weiterleiten und keine automatische KI-Antwort.
- Der Server übernimmt Absenderpostfach, Zielkennung und Betreff aus belegten
  Instantly-Daten, niemals ungeprüft aus versteckten Formularfeldern.
- Jede Formularfreigabe gilt 15 Minuten und kann serverseitig genau einmal
  verbraucht werden.
- Ein Netzwerkfehler, Zeitablauf, HTTP-5xx oder unvollständiger HTTP-Erfolg
  wird als unklar behandelt und niemals automatisch wiederholt.
- Tests und Bildschirmfotos benutzen nur feste Testdaten.
- Eine echte Testantwort braucht eine neue ausdrückliche Freigabe.
- Jede Fachänderung beginnt mit einem sichtbar fehlschlagenden Test.
- Nach jedem Task laufen die betroffenen Tests; vor „fertig“ laufen alle
  Tests und die sichtbare Desktop-/390-px-Prüfung.

## Dateigrenzen

- `web/instantly_leser.py`: liest und bewahrt belegte Instantly-Mailfelder;
  kann den Cache genau einer Kampagne verwerfen.
- `web/instantly_antworter.py`: führt ausschließlich
  `POST /api/v2/emails/reply` aus und unterscheidet sichere Ablehnung von
  unklarem Ausgang.
- `web/antwort_freigabe.py`: Antworttext-Prüfung, signierte 15-Minuten-
  Freigabe und atomarer Einmalverbrauch im Datenverzeichnis.
- `web/routen/postfach.py`: wählt das belegte Antwortziel, koordiniert
  Prüfung/Verbrauch/Versand und baut ehrliche Seitenzustände.
- `web/templates/postfach.html`: zeigt Antwortfeld, Absender, Erfolg,
  Ablehnung und unklaren Ausgang.
- `web/static/stil.css`: fügt nur die Postfach-Antwortdarstellung hinzu.
- `web/app.py`: hält einen geteilten, in Tests ersetzbaren
  `InstantlyAntworter`.

---

### Task 1: Antwort-Metadaten vollständig durch den Leser führen

**Dateien:**

- Ändern: `tests/web/test_instantly_leser.py`
- Ändern: `web/instantly_leser.py`

**Schnittstellen:**

- Verwendet: rohe `/emails`-Einträge mit `id`, `eaccount` und
  `campaign_id`.
- Liefert: Jede Anzeige-Nachricht trägt zusätzlich `id`, `eaccount` und
  `campaign_id`.
- Liefert: `InstantlyLeser.verwerfe_email_cache(campaign_id: str) -> None`.

- [ ] **Schritt 1: Fehlende Metadaten mit einem Test festhalten**

In `tests/web/test_instantly_leser.py` ergänzen:

```python
def test_empfangene_nachricht_behaelt_belegte_antwort_metadaten():
    session = FakeSession({
        "/emails": FakeResponse(200, {"items": [
            _email(
                campaign_id="camp-1",
                ue_type=2,
                frm="anna@firma.de",
                betreff="Re: Anschreiben",
            ),
        ]}),
    })

    nachricht = InstantlyLeser(
        "key", session=session
    ).konversationen(["camp-1"])[0]["nachrichten"][0]

    assert nachricht["id"] == "mail-1"
    assert nachricht["eaccount"] == "wir@digitaldiamonds.de"
    assert nachricht["campaign_id"] == "camp-1"
```

- [ ] **Schritt 2: Den Metadaten-Test rot ausführen**

```bash
'.venv/bin/python' -m pytest \
  tests/web/test_instantly_leser.py::test_empfangene_nachricht_behaelt_belegte_antwort_metadaten -q
```

Erwartet: `FAIL` wegen des fehlenden Schlüssels `id`.

- [ ] **Schritt 3: Nur belegte Metadaten ergänzen**

`_nachricht_aus_email` erhält die Fallback-Kampagnen-ID:

```python
def _nachricht_aus_email(
    email: dict, richtung: str, campaign_id: str | None = None
) -> dict | None:
    zeit = _parse_zeit(email.get("timestamp_email") or email.get("timestamp_created"))
    if zeit is None:
        return None
    body = email.get("body") or {}
    text = (body.get("text") or "").strip() or (
        email.get("content_preview") or ""
    ).strip()
    return {
        "id": email.get("id"),
        "campaign_id": email.get("campaign_id") or campaign_id,
        "eaccount": email.get("eaccount"),
        "richtung": richtung,
        "zeit": zeit,
        "betreff": email.get("subject") or "",
        "text": text,
    }
```

Die Schleife in `konversationen_aus_email_stand` behält die äußere Kampagnen-
ID als sichere Herkunft:

```python
for campaign_id, eintrag in stand_by_id.items():
    for roh in eintrag.get("items") or []:
        ergebnis = _richtung_und_kontakt(roh)
        if ergebnis is None:
            continue
        richtung, kontakt_email = ergebnis
        nachricht = _nachricht_aus_email(roh, richtung, campaign_id)
```

- [ ] **Schritt 4: Fehlenden gezielten Cache-Verwurf testen**

```python
def test_email_cache_kann_fuer_genau_eine_kampagne_verworfen_werden():
    session = FakeSession({
        "/emails": [
            FakeResponse(200, {"items": [_email(text="Vorher")]}),
            FakeResponse(200, {"items": [_email(text="Nachher")]}),
        ],
    })
    leser = InstantlyLeser("key", session=session)

    assert leser.emails_stand(["camp-1"])["camp-1"]["items"][0]["body"]["text"] == "Vorher"
    leser.verwerfe_email_cache("camp-1")
    assert leser.emails_stand(["camp-1"])["camp-1"]["items"][0]["body"]["text"] == "Nachher"
    assert len(session.aufrufe) == 2
```

- [ ] **Schritt 5: Cache-Verwurf minimal bauen**

Direkt nach `emails_stand`:

```python
def verwerfe_email_cache(self, campaign_id: str) -> None:
    """Erzwingt beim nächsten Abruf frische Mails für genau eine Kampagne."""
    self._email_cache.pop(campaign_id, None)
```

- [ ] **Schritt 6: Alle Lesertests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_instantly_leser.py -q
```

Erwartet: alle Tests in der Datei bestehen.

- [ ] **Schritt 7: Task committen**

```bash
git add web/instantly_leser.py tests/web/test_instantly_leser.py
git commit -m "feat: preserve Instantly reply metadata"
```

---

### Task 2: Den offiziellen Instantly-Antwort-Endpunkt sicher kapseln

**Dateien:**

- Erstellen: `tests/web/test_instantly_antworter.py`
- Erstellen: `web/instantly_antworter.py`
- Ändern: `web/app.py`

**Schnittstellen:**

- Liefert:
  `InstantlyAntworter.antworten(*, eaccount: str, reply_to_uuid: str,
  betreff: str, text: str) -> dict`.
- Wirft: `InstantlyAntwortAbgelehnt` nur bei HTTP 4xx.
- Wirft: `InstantlyAntwortStatusUnklar` bei Netzwerkfehlern, HTTP 5xx und
  einem unvollständigen HTTP-Erfolg.
- Liefert: `geteilten_antworter(app) -> InstantlyAntworter`.

- [ ] **Schritt 1: Exakten Erfolgsaufruf als roten Test schreiben**

`tests/web/test_instantly_antworter.py` anlegen:

```python
class FakeAntwort:
    def __init__(self, status_code=200, daten=None):
        self.status_code = status_code
        self._daten = daten if daten is not None else {"id": "antwort-1"}

    def json(self):
        return self._daten


class FakeSession:
    def __init__(self, antwort=None, fehler=None):
        self.antwort = antwort or FakeAntwort()
        self.fehler = fehler
        self.aufrufe = []

    def post(self, url, **kwargs):
        self.aufrufe.append((url, kwargs))
        if self.fehler is not None:
            raise self.fehler
        return self.antwort


def test_antworten_nutzt_offiziellen_endpunkt_und_genaue_nutzlast():
    session = FakeSession()
    ergebnis = InstantlyAntworter("key", session=session).antworten(
        eaccount="wir@digitaldiamonds.de",
        reply_to_uuid="mail-1",
        betreff="Re: Anschreiben",
        text="Danke für die Antwort.",
    )

    assert ergebnis == {"id": "antwort-1"}
    assert session.aufrufe == [(
        "https://api.instantly.ai/api/v2/emails/reply",
        {
            "headers": {
                "Authorization": "Bearer key",
                "Content-Type": "application/json",
            },
            "json": {
                "eaccount": "wir@digitaldiamonds.de",
                "reply_to_uuid": "mail-1",
                "subject": "Re: Anschreiben",
                "body": {"text": "Danke für die Antwort."},
            },
            "timeout": 60,
        },
    )]
```

- [ ] **Schritt 2: Fehlerklassen mit roten Tests festlegen**

```python
def test_http_4xx_ist_sicher_abgelehnt_ohne_antwortinhalt_im_fehler():
    session = FakeSession(FakeAntwort(422, {"message": "vertraulicher Inhalt"}))
    with pytest.raises(InstantlyAntwortAbgelehnt, match="422") as fehler:
        InstantlyAntworter("key", session=session).antworten(
            eaccount="wir@digitaldiamonds.de",
            reply_to_uuid="mail-1",
            betreff="Re: Anschreiben",
            text="Antwort",
        )
    assert "vertraulicher Inhalt" not in str(fehler.value)


@pytest.mark.parametrize("antwort", [
    FakeAntwort(500, {}),
    FakeAntwort(200, {}),
])
def test_serverfehler_oder_unvollstaendiger_erfolg_bleibt_unklar(antwort):
    with pytest.raises(InstantlyAntwortStatusUnklar):
        InstantlyAntworter(
            "key", session=FakeSession(antwort)
        ).antworten(
            eaccount="wir@digitaldiamonds.de",
            reply_to_uuid="mail-1",
            betreff="Re: Anschreiben",
            text="Antwort",
        )


def test_timeout_bleibt_unklar_und_wird_nicht_wiederholt():
    session = FakeSession(fehler=requests.exceptions.Timeout("zu langsam"))
    with pytest.raises(InstantlyAntwortStatusUnklar):
        InstantlyAntworter("key", session=session).antworten(
            eaccount="wir@digitaldiamonds.de",
            reply_to_uuid="mail-1",
            betreff="Re: Anschreiben",
            text="Antwort",
        )
    assert len(session.aufrufe) == 1
```

- [ ] **Schritt 3: Neue Tests rot ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_instantly_antworter.py -q
```

Erwartet: `ERROR` beim Import, weil das Modul noch fehlt.

- [ ] **Schritt 4: Kleinen API-Baustein implementieren**

`web/instantly_antworter.py`:

```python
from __future__ import annotations

import os
import requests

BASIS = "https://api.instantly.ai/api/v2"


class InstantlyAntwortAbgelehnt(RuntimeError):
    pass


class InstantlyAntwortStatusUnklar(RuntimeError):
    pass


class InstantlyAntworter:
    def __init__(self, api_key: str, session=None):
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def antworten(
        self, *, eaccount: str, reply_to_uuid: str, betreff: str, text: str
    ) -> dict:
        try:
            antwort = self.session.post(
                f"{BASIS}/emails/reply",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "eaccount": eaccount,
                    "reply_to_uuid": reply_to_uuid,
                    "subject": betreff,
                    "body": {"text": text},
                },
                timeout=60,
            )
        except requests.exceptions.RequestException as fehler:
            raise InstantlyAntwortStatusUnklar(
                "Der Versandstatus ist wegen eines Netzwerkfehlers unklar."
            ) from fehler

        if 400 <= antwort.status_code < 500:
            raise InstantlyAntwortAbgelehnt(
                f"Instantly hat die Antwort mit HTTP {antwort.status_code} abgelehnt."
            )
        if antwort.status_code >= 500:
            raise InstantlyAntwortStatusUnklar(
                f"Der Versandstatus ist nach HTTP {antwort.status_code} unklar."
            )
        try:
            daten = antwort.json()
        except ValueError as fehler:
            raise InstantlyAntwortStatusUnklar(
                "Instantly hat keinen auswertbaren Versandnachweis geliefert."
            ) from fehler
        if not isinstance(daten, dict) or not daten.get("id"):
            raise InstantlyAntwortStatusUnklar(
                "Instantly hat keinen vollständigen Versandnachweis geliefert."
            )
        return daten


def geteilten_antworter(app) -> InstantlyAntworter:
    antworter = getattr(app.state, "instantly_antworter", None)
    if antworter is not None:
        return antworter
    with app.state._instantly_antworter_lock:
        antworter = getattr(app.state, "instantly_antworter", None)
        if antworter is None:
            api_key = os.environ.get("INSTANTLY_API_KEY")
            if not api_key:
                raise RuntimeError("INSTANTLY_API_KEY fehlt.")
            antworter = InstantlyAntworter(api_key)
            app.state.instantly_antworter = antworter
        return antworter
```

- [ ] **Schritt 5: Geteilten Antworter in der App vorbereiten**

Neben dem geteilten Leser in `web/app.py`:

```python
app.state.instantly_antworter = None
app.state._instantly_antworter_lock = threading.Lock()
if os.environ.get("INSTANTLY_API_KEY"):
    from .instantly_antworter import InstantlyAntworter

    app.state.instantly_antworter = InstantlyAntworter(
        os.environ["INSTANTLY_API_KEY"]
    )
```

- [ ] **Schritt 6: API- und App-Tests ausführen**

```bash
'.venv/bin/python' -m pytest \
  tests/web/test_instantly_antworter.py tests/web/test_main.py -q
```

Erwartet: alle Tests bestehen.

- [ ] **Schritt 7: Task committen**

```bash
git add web/instantly_antworter.py web/app.py tests/web/test_instantly_antworter.py
git commit -m "feat: add safe Instantly reply client"
```

---

### Task 3: Signierte Einmal-Freigabe und Antworttext absichern

**Dateien:**

- Erstellen: `tests/web/test_antwort_freigabe.py`
- Erstellen: `web/antwort_freigabe.py`
- Ändern: `.gitignore`

**Schnittstellen:**

- `erstelle_antwort_freigabe(serializer, *, kontakt, reply_to_uuid) -> str`
- `pruefe_antwort_freigabe(serializer, token: str) -> dict`
- `erstelle_versandhinweis(serializer, *, kontakt, antwort_id) -> str`
- `pruefe_versandhinweis(serializer, token: str, *, kontakt: str) -> bool`
- `validiere_antworttext(text: str) -> str`
- `verbrauche_antwort_freigabe(daten_dir: Path, nonce: str) -> Path`
- Fehler: `AntwortFreigabeUngueltig`, `AntwortFreigabeBenutzt`,
  `AntwortTextUngueltig`.

- [ ] **Schritt 1: Signatur, Ablauf und Manipulation rot testen**

`tests/web/test_antwort_freigabe.py`:

```python
from pathlib import Path
import stat

import pytest
from itsdangerous import BadSignature, URLSafeTimedSerializer

from web.antwort_freigabe import (
    AntwortFreigabeBenutzt,
    AntwortFreigabeUngueltig,
    AntwortTextUngueltig,
    erstelle_antwort_freigabe,
    erstelle_versandhinweis,
    pruefe_antwort_freigabe,
    pruefe_versandhinweis,
    validiere_antworttext,
    verbrauche_antwort_freigabe,
)


def test_signierte_freigabe_traegt_nur_ziel_und_einmalige_kennung():
    serializer = URLSafeTimedSerializer("test-secret")
    token = erstelle_antwort_freigabe(
        serializer,
        kontakt=" Anna@Firma.de ",
        reply_to_uuid="mail-1",
    )

    daten = pruefe_antwort_freigabe(serializer, token)
    assert daten["kontakt"] == "anna@firma.de"
    assert daten["reply_to_uuid"] == "mail-1"
    assert isinstance(daten["nonce"], str) and len(daten["nonce"]) >= 24
    assert set(daten) == {"kontakt", "reply_to_uuid", "nonce"}

    with pytest.raises(AntwortFreigabeUngueltig):
        pruefe_antwort_freigabe(serializer, token + "manipuliert")


def test_pruefung_verlangt_exakt_15_minuten_maximalalter():
    class PruefSerializer:
        def loads(self, token, *, max_age, salt):
            assert token == "token"
            assert max_age == 15 * 60
            assert salt == "postfach-antwort"
            raise BadSignature("abgelaufen oder falsch")

    with pytest.raises(AntwortFreigabeUngueltig):
        pruefe_antwort_freigabe(PruefSerializer(), "token")


def test_erfolgshinweis_ist_fuenf_minuten_signiert_und_kontaktgebunden():
    serializer = URLSafeTimedSerializer("test-secret")
    token = erstelle_versandhinweis(
        serializer,
        kontakt="anna@firma.de",
        antwort_id="antwort-1",
    )

    assert pruefe_versandhinweis(
        serializer, token, kontakt="anna@firma.de"
    ) is True
    assert pruefe_versandhinweis(
        serializer, token + "manipuliert", kontakt="anna@firma.de"
    ) is False
    assert pruefe_versandhinweis(
        serializer, token, kontakt="bob@firma.de"
    ) is False
```

- [ ] **Schritt 2: Antworttext und atomaren Einmalverbrauch rot testen**

```python
@pytest.mark.parametrize("text", ["", "   ", "\\n\\t"])
def test_leerer_antworttext_wird_abgelehnt(text):
    with pytest.raises(AntwortTextUngueltig, match="nicht leer"):
        validiere_antworttext(text)


def test_antworttext_wird_getrimmt_und_auf_10000_zeichen_begrenzt():
    assert validiere_antworttext("  Danke.  ") == "Danke."
    with pytest.raises(AntwortTextUngueltig, match="10.000"):
        validiere_antworttext("x" * 10_001)


def test_freigabe_kann_dateisystemweit_nur_einmal_verbraucht_werden(tmp_path):
    ziel = verbrauche_antwort_freigabe(tmp_path, "nonce-1")
    assert ziel.parent == tmp_path / "postfach-antworten"
    assert stat.S_IMODE(ziel.stat().st_mode) == 0o600

    with pytest.raises(AntwortFreigabeBenutzt):
        verbrauche_antwort_freigabe(tmp_path, "nonce-1")
```

- [ ] **Schritt 3: Neue Tests rot ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_antwort_freigabe.py -q
```

Erwartet: `ERROR` beim Import, weil das Modul fehlt.

- [ ] **Schritt 4: Freigabebaustein vollständig implementieren**

`web/antwort_freigabe.py`:

```python
from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

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
        raise AntwortFreigabeUngueltig("Die Antwortfreigabe ist unvollständig.")
    if not all(isinstance(daten[feld], str) and daten[feld] for feld in daten):
        raise AntwortFreigabeUngueltig("Die Antwortfreigabe ist unvollständig.")
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
```

- [ ] **Schritt 5: Betriebsmarkierungen vom Git-Stand fernhalten**

In `.gitignore` ergänzen:

```gitignore
# Einmalige Versandfreigaben aus dem laufenden Datenverzeichnis
postfach-antworten/
```

- [ ] **Schritt 6: Freigabetests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_antwort_freigabe.py -q
```

Erwartet: alle Tests bestehen.

- [ ] **Schritt 7: Task committen**

```bash
git add .gitignore web/antwort_freigabe.py tests/web/test_antwort_freigabe.py
git commit -m "feat: guard mailbox replies against duplicate sends"
```

---

### Task 4: Antwortziel serverseitig prüfen und genau einmal senden

**Dateien:**

- Ändern: `tests/web/test_postfach.py`
- Ändern: `web/routen/postfach.py`

**Schnittstellen:**

- Neue Route:
  `POST /postfach/antworten`
- Formfelder: `kontakt`, `antwort_token`, `antwort_text`.
- Der POST übernimmt niemals `eaccount`, `campaign_id`, `reply_to_uuid` oder
  `subject` direkt aus dem Formular.

- [ ] **Schritt 1: Test-Fakes um Cache-Verwurf und Antworter ergänzen**

`FakeInstantlyLeser` in `tests/web/test_postfach.py`:

```python
self.verworfen: list[str] = []

def verwerfe_email_cache(self, campaign_id):
    self.verworfen.append(campaign_id)
```

Zusätzlich:

```python
class FakeInstantlyAntworter:
    def __init__(self, fehler=None):
        self.fehler = fehler
        self.aufrufe = []

    def antworten(self, **daten):
        self.aufrufe.append(daten)
        if self.fehler is not None:
            raise self.fehler
        return {"id": "antwort-1"}


def _antwort_token(html):
    treffer = re.search(
        r'name="antwort_token" value="([^"]+)"',
        html,
    )
    assert treffer is not None
    return treffer.group(1)


def _bereite_antwortfall_vor(
    angemeldeter_client,
    daten_dir,
    *,
    eaccount="wir@digitaldiamonds.de",
    fehler=None,
):
    _lauf(
        daten_dir,
        "demo-gmbh",
        "demo-gmbh.yaml",
        "20260720-090000",
        leads=[_lead("Anna", "Muster", "anna@firma.de", "Demo GmbH")],
        campaign_id="camp-1",
    )
    empfangen = _email(
        ue_type=2,
        frm="anna@firma.de",
        betreff="Anschreiben",
        text="Klingt gut.",
    )
    empfangen["eaccount"] = eaccount
    leser = FakeInstantlyLeser(
        emails_by_campaign={"camp-1": [empfangen]}
    )
    antworter = FakeInstantlyAntworter(fehler)
    angemeldeter_client.app.state.instantly_leser = leser
    angemeldeter_client.app.state.instantly_antworter = antworter
    return leser, antworter
```

Die Testdatei importiert dafür `re` sowie
`parse_qs`/`urlparse`, `erstelle_versandhinweis`,
`pruefe_versandhinweis`,
`InstantlyAntwortAbgelehnt` und `InstantlyAntwortStatusUnklar`.

- [ ] **Schritt 2: Erfolgsweg als roten Routentest schreiben**

```python
def test_antwort_wird_genau_einmal_aus_belegten_instantly_daten_gesendet(
    angemeldeter_client, daten_dir
):
    leser, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )

    seite = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    token = _antwort_token(seite.text)
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token,
            "antwort_text": "  Danke für die Rückmeldung.  ",
        },
        follow_redirects=False,
    )

    assert antwort.status_code == 303
    ziel = urlparse(antwort.headers["location"])
    parameter = parse_qs(ziel.query)
    assert ziel.path == "/postfach"
    assert parameter["kontakt"] == ["anna@firma.de"]
    assert pruefe_versandhinweis(
        angemeldeter_client.app.state.serializer,
        parameter["versand"][0],
        kontakt="anna@firma.de",
    ) is True
    assert "antwort" not in parameter
    assert antworter.aufrufe == [{
        "eaccount": "wir@digitaldiamonds.de",
        "reply_to_uuid": "mail-1",
        "betreff": "Re: Anschreiben",
        "text": "Danke für die Rückmeldung.",
    }]
    assert leser.verworfen == ["camp-1"]

    zweite_antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token,
            "antwort_text": "Danke für die Rückmeldung.",
        },
    )
    assert zweite_antwort.status_code == 409
    assert len(antworter.aufrufe) == 1
```

- [ ] **Schritt 3: Manipulation und ungültige Texte rot testen**

```python
@pytest.mark.parametrize("text", ["", " ", "x" * 10_001])
def test_ungueltiger_text_sendet_nichts(
    angemeldeter_client, daten_dir, text
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )
    seite = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    token = _antwort_token(seite.text)
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token,
            "antwort_text": text,
        },
    )
    assert antwort.status_code == 400
    assert antworter.aufrufe == []
```

Zusätzlich ein eigener Manipulationstest:

```python
def test_kontakt_oder_token_manipulation_sendet_nichts(
    angemeldeter_client, daten_dir
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir
    )
    seite = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    token = _antwort_token(seite.text)
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "bob@firma.de",
            "antwort_token": token + "manipuliert",
            "antwort_text": "Antwort",
        },
    )
    assert antwort.status_code == 400
    assert antworter.aufrufe == []
```

- [ ] **Schritt 4: Sichere Ablehnung und unklaren Ausgang rot testen**

```python
@pytest.mark.parametrize(
    ("fehler", "status", "text", "formular_erwartet"),
    [
        (
            InstantlyAntwortAbgelehnt("HTTP 422"),
            502,
            "Instantly hat die Antwort nicht angenommen.",
            True,
        ),
        (
            InstantlyAntwortStatusUnklar("Timeout"),
            502,
            "Der Versandstatus ist unklar.",
            False,
        ),
    ],
)
def test_fehlerzustand_bleibt_ehrlich_und_text_bleibt_sichtbar(
    angemeldeter_client, daten_dir, fehler, status, text, formular_erwartet
):
    _, antworter = _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir, fehler=fehler
    )
    seite = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    token = _antwort_token(seite.text)
    antwort = angemeldeter_client.post(
        "/postfach/antworten",
        data={
            "kontakt": "anna@firma.de",
            "antwort_token": token,
            "antwort_text": "Mein nicht verlorener Entwurf",
        },
    )
    assert antwort.status_code == status
    assert text in antwort.text
    assert "Mein nicht verlorener Entwurf" in antwort.text
    assert ('name="antwort_token"' in antwort.text) is formular_erwartet
    assert len(antworter.aufrufe) == 1
```

- [ ] **Schritt 5: Routentests rot ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_postfach.py -q
```

Erwartet: mehrere `FAIL`, weil POST-Route und Antwortziel noch fehlen.

- [ ] **Schritt 6: Antwortziel und Betreff als reine Helfer bauen**

In `web/routen/postfach.py`:

```python
def _antwortziel(konversation: dict, reply_to_uuid: str | None = None):
    for nachricht in reversed(konversation["nachrichten"]):
        if nachricht.get("richtung") != "empfangen":
            continue
        if reply_to_uuid is not None and nachricht.get("id") != reply_to_uuid:
            continue
        if not all(
            isinstance(nachricht.get(feld), str) and nachricht[feld].strip()
            for feld in ("id", "eaccount", "campaign_id")
        ):
            continue
        return nachricht
    return None


def _antwort_betreff(betreff: str) -> str:
    bereinigt = betreff.strip()
    if bereinigt.casefold().startswith("re:"):
        return bereinigt
    return f"Re: {bereinigt or '(ohne Betreff)'}"
```

Die vorhandene Nachrichten-Aufbereitung übernimmt keine dieser Werte in
veränderbare Formularfelder. Nur der ausgewählte Ziel-Datensatz wird
serverseitig weitergereicht.

- [ ] **Schritt 7: GET-/POST-Kontext ohne zweiten Datenweg refaktorieren**

Die bisherige GET-Logik wird in diese beiden Helfer zerlegt:

```python
def _lade_postfach(request: Request, gewuenscht: str) -> dict:
    daten_dir = request.app.state.daten_dir
    laeufe = kampagnen_routen._alle_laeufe(daten_dir)
    campaign_ids = sorted({
        lauf["campaign_id"] for lauf in laeufe if lauf["campaign_id"]
    })
    leser = _hole_leser(request)
    stand_by_id = leser.emails_stand(campaign_ids)
    konversationen = konversationen_aus_email_stand(stand_by_id)
    live_stand_hinweis = kampagnen_routen._live_stand_hinweis(
        list(stand_by_id.values())
    )
    treffer = next(
        (
            eintrag for eintrag in konversationen
            if eintrag["kontakt_email"] == gewuenscht
        ),
        None,
    )
    ausgewaehlt = treffer or (
        konversationen[0] if konversationen else None
    )
    return {
        "daten_dir": daten_dir,
        "campaign_ids": campaign_ids,
        "leser": leser,
        "konversationen": konversationen,
        "live_stand_hinweis": live_stand_hinweis,
        "ausgewaehlt": ausgewaehlt,
    }


def _render_postfach(
    request: Request,
    daten: dict,
    *,
    antwort_text: str = "",
    antwort_fehler: str | None = None,
    antwort_unsicher: bool = False,
    status_code: int = 200,
):
    ausgewaehlt = daten["ausgewaehlt"]
    kontakt_info = _kontakt_info_je_email(daten["daten_dir"])
    ausgewaehlte_email = (
        ausgewaehlt["kontakt_email"] if ausgewaehlt else None
    )
    zeilen = _konversations_zeilen(
        daten["konversationen"], kontakt_info, ausgewaehlte_email
    )

    detail = None
    if ausgewaehlt is not None:
        info = kontakt_info.get(ausgewaehlt["kontakt_email"], {})
        kontakt_name = info.get("name") or ausgewaehlt["kontakt_email"]
        ziel = _antwortziel(ausgewaehlt)
        antwort = None
        if ziel is not None and not antwort_unsicher:
            antwort = {
                "konto": ziel["eaccount"],
                "token": erstelle_antwort_freigabe(
                    request.app.state.serializer,
                    kontakt=ausgewaehlt["kontakt_email"],
                    reply_to_uuid=ziel["id"],
                ),
            }
        detail = {
            "kontakt_email": ausgewaehlt["kontakt_email"],
            "name": kontakt_name,
            "firma": info.get("firma", ""),
            "betreff": ausgewaehlt["betreff"],
            "letzte_zeit": _format_zeit(ausgewaehlt["letzte_zeit"]),
            "nachrichten": _nachrichten_zeilen(
                ausgewaehlt["nachrichten"], kontakt_name
            ),
            "antwort": antwort,
        }

    versand_token = request.query_params.get("versand") or ""
    antwort_erfolg = bool(
        ausgewaehlte_email
        and pruefe_versandhinweis(
            request.app.state.serializer,
            versand_token,
            kontakt=ausgewaehlte_email,
        )
    )
    keine_antworten_hinweis = (
        KEINE_ANTWORTEN_HINWEIS
        if (
            daten["campaign_ids"]
            and not daten["live_stand_hinweis"]
            and not zeilen
        )
        else None
    )
    return request.app.state.templates.TemplateResponse(
        request,
        "postfach.html",
        {
            "nutzer": auth.aktueller_nutzer(request),
            "nav": nav_kontext(request),
            "postfach_hinweis": POSTFACH_HINWEIS,
            "konversationen": zeilen,
            "konversationen_leer": len(zeilen) == 0,
            "keine_antworten_hinweis": keine_antworten_hinweis,
            "live_stand_hinweis": daten["live_stand_hinweis"],
            "detail": detail,
            "instantly_link": INSTANTLY_LINK,
            "instantly_knopf_text": INSTANTLY_KNOPF_TEXT,
            "antwort_text": antwort_text,
            "antwort_fehler": antwort_fehler,
            "antwort_unsicher": antwort_unsicher,
            "antwort_erfolg": antwort_erfolg,
        },
        status_code=status_code,
    )
```

Der GET-Endpunkt wird dadurch klein:

```python
@router.get("/postfach")
def postfach(request: Request):
    gewuenscht = (request.query_params.get("kontakt") or "").strip().casefold()
    return _render_postfach(
        request,
        _lade_postfach(request, gewuenscht),
    )
```

- [ ] **Schritt 8: POST-Ablauf in der festgelegten Reihenfolge bauen**

Neue Imports: `Form`, `RedirectResponse`, `urlencode`,
`erstelle_antwort_freigabe`, `pruefe_antwort_freigabe`,
`erstelle_versandhinweis`, `pruefe_versandhinweis`,
`validiere_antworttext`, `verbrauche_antwort_freigabe` und ihre drei
Fehlerklassen sowie `geteilten_antworter`, `InstantlyAntwortAbgelehnt` und
`InstantlyAntwortStatusUnklar`.

Der Kern der Route:

```python
@router.post("/postfach/antworten")
def postfach_antworten(
    request: Request,
    kontakt: str = Form(""),
    antwort_token: str = Form(""),
    antwort_text: str = Form(""),
):
    kontakt = kontakt.strip().casefold()
    daten = _lade_postfach(request, kontakt)
    try:
        text = validiere_antworttext(antwort_text)
        freigabe = pruefe_antwort_freigabe(
            request.app.state.serializer, antwort_token
        )
    except (AntwortTextUngueltig, AntwortFreigabeUngueltig) as fehler:
        return _render_postfach(
            request, daten, antwort_text=antwort_text,
            antwort_fehler=str(fehler), status_code=400,
        )

    if freigabe["kontakt"] != kontakt:
        return _render_postfach(
            request, daten, antwort_text=antwort_text,
            antwort_fehler="Die Antwortfreigabe gehört zu einem anderen Kontakt.",
            status_code=400,
        )

    konversation = daten.get("ausgewaehlt")
    ziel = (
        _antwortziel(konversation, freigabe["reply_to_uuid"])
        if konversation is not None else None
    )
    if ziel is None:
        return _render_postfach(
            request, daten, antwort_text=antwort_text,
            antwort_fehler="Die empfangene Nachricht ist nicht mehr verfügbar.",
            status_code=400,
        )

    try:
        antworter = geteilten_antworter(request.app)
    except RuntimeError:
        return _render_postfach(
            request, daten, antwort_text=antwort_text,
            antwort_fehler="Antworten ist gerade nicht eingerichtet.",
            status_code=503,
        )

    try:
        verbrauche_antwort_freigabe(
            request.app.state.daten_dir, freigabe["nonce"]
        )
    except AntwortFreigabeBenutzt as fehler:
        return _render_postfach(
            request, daten, antwort_text=antwort_text,
            antwort_fehler=str(fehler), status_code=409,
        )

    try:
        api_antwort = antworter.antworten(
            eaccount=ziel["eaccount"],
            reply_to_uuid=ziel["id"],
            betreff=_antwort_betreff(ziel["betreff"]),
            text=text,
        )
    except InstantlyAntwortAbgelehnt:
        return _render_postfach(
            request, daten, antwort_text=text,
            antwort_fehler=(
                "Instantly hat die Antwort nicht angenommen. "
                "Es wurde kein erfolgreicher Versand bestätigt."
            ),
            status_code=502,
        )
    except InstantlyAntwortStatusUnklar:
        return _render_postfach(
            request, daten, antwort_text=text,
            antwort_fehler=(
                "Der Versandstatus ist unklar. Bitte prüfe den Verlauf "
                "in Instantly, bevor du erneut sendest."
            ),
            antwort_unsicher=True,
            status_code=502,
        )

    daten["leser"].verwerfe_email_cache(ziel["campaign_id"])
    versandhinweis = erstelle_versandhinweis(
        request.app.state.serializer,
        kontakt=kontakt,
        antwort_id=api_antwort["id"],
    )
    query = urlencode({"kontakt": kontakt, "versand": versandhinweis})
    return RedirectResponse(f"/postfach?{query}", status_code=303)
```

- [ ] **Schritt 9: Alle Postfach-Routentests ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_postfach.py -q
```

Erwartet: alle Tests bestehen; kein Test berührt das Netzwerk.

- [ ] **Schritt 10: Task committen**

```bash
git add web/routen/postfach.py tests/web/test_postfach.py
git commit -m "feat: send guarded replies from internal mailbox"
```

---

### Task 5: Antwortfeld und ehrliche Zustände im Wholix-Stil zeigen

**Dateien:**

- Ändern: `tests/web/test_postfach.py`
- Ändern: `web/templates/postfach.html`
- Ändern: `web/static/stil.css`

**Schnittstellen:**

- Jinja erhält in `detail.antwort` nur `konto` und `token`.
- Jinja erhält `antwort_text`, `antwort_fehler`, `antwort_unsicher` und
  `antwort_erfolg`.
- Kein verstecktes Feld enthält Absenderkonto, Kampagnen-ID, Betreff oder
  Instantly-Zielkennung.

- [ ] **Schritt 1: Sichtbare Zustände rot testen**

Folgende Tests vollständig in `tests/web/test_postfach.py` ergänzen:

```python
def test_empfangene_mail_zeigt_antwortfeld_und_absender_ohne_rohe_zieldaten(
    angemeldeter_client, daten_dir
):
    _bereite_antwortfall_vor(angemeldeter_client, daten_dir)
    antwort = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    assert antwort.status_code == 200
    assert "<textarea" in antwort.text
    assert "Antwort endgültig senden" in antwort.text
    assert "Gesendet über wir@digitaldiamonds.de" in antwort.text
    assert 'name="antwort_token"' in antwort.text
    assert 'name="eaccount"' not in antwort.text
    assert 'name="campaign_id"' not in antwort.text
    assert 'name="reply_to_uuid"' not in antwort.text
    assert 'name="subject"' not in antwort.text


def test_ohne_vollstaendiges_empfangsziel_gibt_es_nur_instantly_ausweichweg(
    angemeldeter_client, daten_dir
):
    _bereite_antwortfall_vor(
        angemeldeter_client, daten_dir, eaccount=None
    )
    antwort = angemeldeter_client.get("/postfach?kontakt=anna@firma.de")
    assert "<textarea" not in antwort.text
    assert "Für dieses Gespräch ist Antworten nur in Instantly möglich." in antwort.text
    assert "In Instantly öffnen ↗" in antwort.text


def test_nur_signierter_erfolgsnachweis_zeigt_versandhinweis(
    angemeldeter_client, daten_dir
):
    _bereite_antwortfall_vor(angemeldeter_client, daten_dir)
    token = erstelle_versandhinweis(
        angemeldeter_client.app.state.serializer,
        kontakt="anna@firma.de",
        antwort_id="antwort-1",
    )
    antwort = angemeldeter_client.get(
        "/postfach",
        params={"kontakt": "anna@firma.de", "versand": token},
    )
    assert "Antwort wurde über Instantly gesendet." in antwort.text

    manipuliert = angemeldeter_client.get(
        "/postfach",
        params={"kontakt": "anna@firma.de", "versand": token + "falsch"},
    )
    assert "Antwort wurde über Instantly gesendet." not in manipuliert.text
```

- [ ] **Schritt 2: Sichttests rot ausführen**

```bash
'.venv/bin/python' -m pytest tests/web/test_postfach.py -q
```

Erwartet: `FAIL`, weil das Template noch kein Formular zeigt.

- [ ] **Schritt 3: Antwortbereich in das bestehende Detail einfügen**

Der Linktext wird zu „In Instantly öffnen ↗“. Direkt nach
`.postfach-nachrichten`:

```html
{% if antwort_erfolg %}
<div class="postfach-antwort-erfolg">Antwort wurde über Instantly gesendet.</div>
{% endif %}

{% if antwort_fehler %}
<div class="postfach-antwort-fehler">{{ antwort_fehler }}</div>
{% endif %}

{% if antwort_unsicher %}
<div class="postfach-antwort-entwurf">
  <div class="postfach-antwort-label">Dein nicht verlorener Entwurf</div>
  <div class="postfach-antwort-entwurf-text">{{ antwort_text }}</div>
</div>
{% elif detail.antwort %}
<form method="post"
      action="/postfach/antworten"
      class="postfach-antwort-form"
      onsubmit="this.querySelector('button[type=submit]').disabled=true">
  <input type="hidden" name="kontakt" value="{{ detail.kontakt_email }}">
  <input type="hidden" name="antwort_token" value="{{ detail.antwort.token }}">
  <label class="postfach-antwort-label" for="antwort_text">Deine Antwort</label>
  <div class="postfach-antwort-konto">
    Gesendet über {{ detail.antwort.konto }}
  </div>
  <textarea id="antwort_text"
            name="antwort_text"
            maxlength="10000"
            required>{{ antwort_text }}</textarea>
  <div class="postfach-antwort-aktionen">
    <button type="submit" class="knopf-primaer">Antwort endgültig senden</button>
  </div>
</form>
{% else %}
<div class="hinweis-kasten">
  Für dieses Gespräch ist Antworten nur in Instantly möglich.
</div>
{% endif %}
```

- [ ] **Schritt 4: Antwortbereich ohne Seitenüberlauf gestalten**

In `web/static/stil.css` direkt bei den bestehenden Postfach-Regeln:

```css
.postfach-antwort-form,
.postfach-antwort-entwurf {
  margin-top: 20px;
  border-top: 1px solid var(--farbe-rand);
  padding-top: 18px;
}
.postfach-antwort-label {
  display: block;
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 6px;
}
.postfach-antwort-konto {
  color: var(--farbe-gedaempft);
  font-size: 12px;
  margin-bottom: 10px;
}
.postfach-antwort-form textarea {
  display: block;
  width: 100%;
  min-height: 150px;
  resize: vertical;
  box-sizing: border-box;
}
.postfach-antwort-aktionen {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.postfach-antwort-erfolg,
.postfach-antwort-fehler {
  margin-top: 18px;
  border-radius: 9px;
  padding: 11px 13px;
  font-size: 13px;
}
.postfach-antwort-erfolg {
  color: #20613d;
  background: #eaf7ef;
  border: 1px solid #bfe2cc;
}
.postfach-antwort-fehler {
  color: #8a2f2f;
  background: #fff0f0;
  border: 1px solid #efc4c4;
}
.postfach-antwort-entwurf-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  border: 1px solid var(--farbe-rand);
  border-radius: 8px;
  padding: 12px;
  background: #fbfaf4;
}
```

Unter dem vorhandenen 390-px-Bereich:

```css
@media (max-width: 600px) {
  .postfach-antwort-aktionen,
  .postfach-antwort-aktionen .knopf-primaer {
    width: 100%;
  }
}
```

- [ ] **Schritt 5: Postfach- und CSS-nahe Tests ausführen**

```bash
'.venv/bin/python' -m pytest \
  tests/web/test_postfach.py tests/web/test_main.py -q
```

Erwartet: alle Tests bestehen.

- [ ] **Schritt 6: Task committen**

```bash
git add web/templates/postfach.html web/static/stil.css tests/web/test_postfach.py
git commit -m "feat: add Wholix-style mailbox reply form"
```

---

### Task 6: Gesamtnachweis, Bildschirmprüfung und dauerhafter Abschluss

**Dateien:**

- Ändern: `project-context.md`
- Ändern: `docs/wholix-nachbau-roadmap.md`
- Nur lokal/ignoriert:
  `.superpowers/phase_3/postfach_antwort_demo.py`
- Jira: `AP-201`

**Schnittstellen:**

- Keine neue Produktionsschnittstelle.
- Nachweis: vollständige Tests, Desktop-/390-px-Bildschirmfoto und Jira-
  Abschluss.

- [ ] **Schritt 1: Alle betroffenen Tests frisch ausführen**

```bash
'.venv/bin/python' -m pytest \
  tests/web/test_instantly_antworter.py \
  tests/web/test_antwort_freigabe.py \
  tests/web/test_instantly_leser.py \
  tests/web/test_postfach.py \
  tests/web/test_main.py -q
```

Erwartet: alle betroffenen Tests bestehen.

- [ ] **Schritt 2: Vollständige Testsammlung ausführen**

```bash
'.venv/bin/python' -m pytest -q
```

Erwartet: alle Tests bestehen; nur die bereits bekannte
Starlette/httpx-Abkündigungswarnung darf verbleiben.

- [ ] **Schritt 3: Rein lokale Sichtvorlage mit festen Daten starten**

`.superpowers/phase_3/postfach_antwort_demo.py` wird mit `apply_patch` als
kleiner FastAPI-Testserver angelegt. Er bindet die echten Templates und das
echte CSS ein, besitzt aber keine POST-Route:

```python
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

PROJEKT = Path(__file__).resolve().parents[2]
app = FastAPI()
app.mount(
    "/static",
    StaticFiles(directory=str(PROJEKT / "web" / "static")),
    name="static",
)
templates = Jinja2Templates(directory=str(PROJEKT / "web" / "templates"))


@app.get("/postfach")
def postfach(request: Request, zustand: str = "formular"):
    detail = {
        "kontakt_email": "anna@firma.de",
        "name": "Anna Muster",
        "firma": "Demo GmbH",
        "betreff": "Re: Anschreiben",
        "letzte_zeit": "23.07.2026, 10:10",
        "nachrichten": [
            {
                "richtung": "gesendet",
                "wer": "Wir",
                "zeit": "23.07.2026, 10:09",
                "betreff": "Anschreiben",
                "text": "Hallo Anna, dies ist eine feste Testnachricht.",
            },
            {
                "richtung": "empfangen",
                "wer": "Anna Muster",
                "zeit": "23.07.2026, 10:10",
                "betreff": "Re: Anschreiben",
                "text": "Danke, ich freue mich über weitere Informationen.",
            },
        ],
        "antwort": {
            "konto": "wir@digitaldiamonds.de",
            "token": "nur-lokale-sichtpruefung",
        },
    }
    fehler = None
    unsicher = False
    entwurf = ""
    if zustand == "abgelehnt":
        fehler = (
            "Instantly hat die Antwort nicht angenommen. "
            "Es wurde kein erfolgreicher Versand bestätigt."
        )
        entwurf = "Danke für die Rückmeldung."
    elif zustand == "unklar":
        fehler = (
            "Der Versandstatus ist unklar. Bitte prüfe den Verlauf "
            "in Instantly, bevor du erneut sendest."
        )
        unsicher = True
        entwurf = "Danke für die Rückmeldung."

    konversation = {
        "kontakt_email": "anna@firma.de",
        "name": "Anna Muster",
        "firma": "Demo GmbH",
        "betreff": "Re: Anschreiben",
        "letzte_zeit": "23.07.2026, 10:10",
        "richtung_letzte": "empfangen",
        "aktiv": True,
    }
    return templates.TemplateResponse(
        request,
        "postfach.html",
        {
            "nutzer": "Lena Hartmann",
            "nav": [
                {
                    "url": "/postfach",
                    "label": "Postfach",
                    "aktiv": True,
                    "badge": None,
                },
            ],
            "postfach_hinweis": (
                "Alle Gespräche an einem Ort: unsere Mails und die "
                "Antworten darauf."
            ),
            "konversationen": [konversation],
            "konversationen_leer": False,
            "keine_antworten_hinweis": None,
            "live_stand_hinweis": None,
            "detail": detail,
            "instantly_link": "https://app.instantly.ai/app/unibox",
            "instantly_knopf_text": "In Instantly öffnen ↗",
            "antwort_text": entwurf,
            "antwort_fehler": fehler,
            "antwort_unsicher": unsicher,
            "antwort_erfolg": zustand == "erfolg",
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
```

Start:

```bash
'.venv/bin/python' .superpowers/phase_3/postfach_antwort_demo.py
```

- [ ] **Schritt 4: Desktop und 390 px sichtbar prüfen**

Im Browser öffnen:

```text
http://127.0.0.1:8765/postfach
```

Nachweise unter `.superpowers/phase_3/`:

- `postfach-antwort-desktop.png` bei 1440 × 1000
- `postfach-antwort-390.png` bei 390 × 844
- `postfach-antwort-erfolg-desktop.png` bei 1440 × 1000 mit
  `?zustand=erfolg`
- `postfach-antwort-unklar-390.png` bei 390 × 844 mit
  `?zustand=unklar`

Prüfliste:

- Absenderkonto ist sichtbar.
- Antwortfeld und endgültiger Sendeknopf sind eindeutig.
- Verlauf und Antwortbereich bleiben lesbar getrennt.
- Erfolg wird grün und der unklare Ausgang ohne Sendeknopf gezeigt.
- Bei 390 px läuft die gesamte Seite nicht seitlich über.
- Der Button bleibt vollständig sichtbar.
- Es sind ausschließlich feste Testdaten zu sehen.

- [ ] **Schritt 5: Projektstand und Roadmap auf „gebaut“ setzen**

`project-context.md` erhält:

- gebaute Instantly-Antwortfunktion
- Schutz durch 15-Minuten-Signatur und atomaren Einmalverbrauch
- Ergebnis der vollständigen Tests
- Pfade der vier sichtbaren Nachweise
- ausdrücklich: kein Gmail-/Microsoft-Zugang und noch kein echter Versandtest
- nächster Schritt: CRM-Entwurf für Verkaufs-Stufen

In `docs/wholix-nachbau-roadmap.md` wird bei Phase 3
„Auf eine bestehende empfangene Mail antworten“ von
„Entwurf freigegeben“ auf „Gebaut und lokal geprüft“ geändert.

- [ ] **Schritt 6: Jira erst nach dem Nachweis abschließen**

`AP-201` zuerst auf `Testing`, nach allen Nachweisen auf `Done` setzen. Der
abschließende Kommentar ist auf Englisch und beschreibt sichtbare Ergebnisse:

```text
Implemented the approved Instantly reply flow in the internal campaign mailbox.

- Team members can reply only to an existing received Instantly email.
- The sending account is visible and derived from Instantly data.
- Signed 15-minute forms and an atomic one-time marker prevent tampered or duplicate sends.
- Rejections and uncertain network outcomes are shown without claiming success or retrying automatically.
- Gmail and Microsoft remain disconnected from the product.
- All automated tests passed and desktop plus 390 px checks used fixed local test data.
- No real email was sent during implementation or verification.
```

- [ ] **Schritt 7: Abschlussänderungen committen**

```bash
git add project-context.md docs/wholix-nachbau-roadmap.md
git commit -m "docs: record Instantly mailbox reply proof"
```

- [ ] **Schritt 8: Sauberen Git-Stand belegen**

```bash
git status --short
git log -6 --oneline
```

Erwartet: `git status --short` bleibt leer; die Task-Commits und der
Abschlusscommit stehen oben im Verlauf.

## Plan-Selbstprüfung

- Jede Anforderung der freigegebenen Spezifikation ist einem Task zugeordnet.
- Keine direkte Gmail-/Microsoft-Anbindung und kein freier Mailversand wird
  eingeführt.
- Erfolgs-, Ablehnungs- und unklare Zustände sind getrennt.
- Der grüne Erfolgshinweis erscheint nur mit einem fünf Minuten gültigen,
  kontaktgebundenen Versandnachweis.
- Doppelklick und wiederholter POST sind auch über mehrere Prozesse durch
  `O_EXCL` abgesichert.
- Die externe Anfrage wird bei unklarem Ausgang nicht wiederholt.
- Der echte Versand bleibt außerhalb dieses Plans und braucht eine neue
  ausdrückliche Freigabe.
- Das CRM ist absichtlich ein späteres, eigenes Arbeitspaket.

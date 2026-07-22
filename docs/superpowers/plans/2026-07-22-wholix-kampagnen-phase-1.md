# Wholix-Kampagnenansicht Phase 1 – Bauplan

> **Für die Ausführung:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ziel:** Die Kampagnenübersicht und die Kampagnendetails zeigen die belegten Instantly-Zahlen und den Betriebsstand im Aussehen der Wholix-Vorlagen.

**Aufbau:** `InstantlyLeser` vereinheitlicht alle externen Daten und behält den vorhandenen 60-Sekunden-Zwischenspeicher. Die Kampagnenroute baut daraus kleine Anzeigeformen; Jinja zeigt nur vorbereitete Werte. Unbekannte Werte bleiben `None` und erscheinen als „—“.

**Technik:** Python 3.14, FastAPI, Jinja2, requests, pytest, vorhandenes CSS ohne neue Laufzeit-Abhängigkeit.

## Globale Regeln

- Instantly bleibt Versand-Motor; `pipeline/` wird nicht geändert.
- Nur lesende Instantly-Aufrufe werden ergänzt.
- Kampagnen-Einstellungen bleiben ein Link zu Instantly.
- Fehlende externe Werte werden niemals als Null oder aus anderen Zahlen erraten.
- Jede Fachänderung beginnt mit einem sichtbar fehlschlagenden Test.
- Nach jeder sichtbaren Einheit laufen die betroffenen Tests; am Ende laufen alle Tests.
- Bildschirmfotos werden ausschließlich mit Testdaten erzeugt.

---

### Task 1: Belegte Kampagnenzahlen und Betriebsdaten lesen

**Dateien:**

- Ändern: `tests/web/test_instantly_leser.py:43-69`
- Ändern: `web/instantly_leser.py:328-400`

**Schnittstellen:**

- Verwendet: `InstantlyLeser._get(pfad, params)` und den bestehenden Cache je Kampagnen-ID.
- Liefert: `kampagnen_stand()[id]` mit `empfaenger`, `geoeffnet`, `unzustellbar`, `heute_versendet`, `absender`, `sendefenster` und Schrittwert `geoeffnet` zusätzlich zu den vorhandenen Feldern.

- [ ] **Schritt 1: Fakes um die neu gelesenen Endpunkte ergänzen**

In `_standard_antworten()` bekommen Kampagne, Gesamtstatistik und Schrittstatistik die belegten Felder; außerdem kommt die Tagesstatistik hinzu:

```python
def _standard_antworten(campaign_id="camp-1", status=0, name="[TEST] Demo GmbH",
                         emails_sent_count=5):
    return {
        f"/campaigns/{campaign_id}": FakeResponse(200, {
            "id": campaign_id,
            "name": name,
            "status": status,
            "email_list": ["sender@firma.de"],
            "campaign_schedule": {"schedules": [{
                "name": "Werktage",
                "timing": {"from": "08:00", "to": "19:00"},
                "days": {"0": False, "1": True, "2": True, "3": True,
                         "4": True, "5": True, "6": False},
                "timezone": "Europe/Berlin",
            }]},
        }),
        "/campaigns/analytics": FakeResponse(200, [{
            "campaign_id": campaign_id,
            "emails_sent_count": emails_sent_count,
            "leads_count": 12,
            "open_count": 4,
            "reply_count": 2,
            "bounced_count": 1,
            "completed_count": 3,
        }]),
        "/campaigns/analytics/steps": FakeResponse(200, [
            {"step": "1", "variant": "A", "sent": 5, "opened": 4},
            {"step": "2", "variant": "A", "sent": 2, "opened": 1},
        ]),
        "/campaigns/analytics/daily": FakeResponse(200, [
            {"date": "2026-07-22", "sent": 3},
        ]),
    }
```

- [ ] **Schritt 2: Fehlenden Test schreiben**

```python
def test_kampagnen_stand_liefert_wholix_kennzahlen_und_betriebsdaten():
    jetzt = datetime(2026, 7, 22, 10, 30)
    session = FakeSession(_standard_antworten())
    eintrag = InstantlyLeser("key", session=session, jetzt=lambda: jetzt).kampagnen_stand(["camp-1"])["camp-1"]

    assert eintrag["empfaenger"] == 12
    assert eintrag["geoeffnet"] == 4
    assert eintrag["antworten"] == 2
    assert eintrag["unzustellbar"] == 1
    assert eintrag["heute_versendet"] == 3
    assert eintrag["absender"] == ["sender@firma.de"]
    assert eintrag["sendefenster"] == [{
        "name": "Werktage", "von": "08:00", "bis": "19:00",
        "tage": {"0": False, "1": True, "2": True, "3": True,
                 "4": True, "5": True, "6": False},
        "zeitzone": "Europe/Berlin",
    }]
    assert eintrag["schritte"] == [
        {"schritt": 1, "versendet": 5, "geoeffnet": 4},
        {"schritt": 2, "versendet": 2, "geoeffnet": 1},
    ]
    assert ("/campaigns/analytics/daily", {
        "campaign_id": "camp-1", "start_date": "2026-07-22", "end_date": "2026-07-22",
    }) in session.aufrufe
```

- [ ] **Schritt 3: Test ausführen und den erwarteten Fehler sehen**

Ausführen:

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_instantly_leser.py::test_kampagnen_stand_liefert_wholix_kennzahlen_und_betriebsdaten -q
```

Erwartet: `FAIL` wegen fehlender Schlüssel wie `empfaenger`.

- [ ] **Schritt 4: Minimale Lese- und Übersetzungslogik bauen**

Vor der Klasse wird das Sendefenster ohne Annahmen vereinheitlicht:

```python
def _sendefenster_aus_campaign(campaign: dict) -> list[dict]:
    ergebnis = []
    for eintrag in (campaign.get("campaign_schedule") or {}).get("schedules") or []:
        timing = eintrag.get("timing") or {}
        ergebnis.append({
            "name": eintrag.get("name"),
            "von": timing.get("from"),
            "bis": timing.get("to"),
            "tage": eintrag.get("days") or {},
            "zeitzone": eintrag.get("timezone"),
        })
    return ergebnis
```

`_hole_frisch()` liest die drei neuen Gesamtwerte, die Tagesstatistik und die Öffnungen je Schritt. Der Rückgabewert lautet vollständig:

```python
return {
    "status": status,
    "name": name,
    "empfaenger": analytics_eintrag.get("leads_count"),
    "versendet": analytics_eintrag.get("emails_sent_count"),
    "geoeffnet": analytics_eintrag.get("open_count"),
    "antworten": analytics_eintrag.get("reply_count"),
    "unzustellbar": analytics_eintrag.get("bounced_count"),
    "abgeschlossen": analytics_eintrag.get("completed_count"),
    "heute_versendet": sum((zeile.get("sent") or 0) for zeile in tageswerte),
    "absender": campaign.get("email_list") or [],
    "sendefenster": _sendefenster_aus_campaign(campaign),
    "schritte": schritte,
}
```

Der leere Fehlerdatensatz in `kampagnen_stand()` erhält dieselben Schlüssel mit `None`, `[]` beziehungsweise `{}` in derselben Form.

- [ ] **Schritt 5: Betroffene Lesertests ausführen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_instantly_leser.py -q
```

Erwartet: alle Tests in der Datei bestehen.

- [ ] **Schritt 6: Aufgabe festhalten**

```bash
git add web/instantly_leser.py tests/web/test_instantly_leser.py
git commit -m "feat: read Wholix campaign metrics from Instantly"
```

---

### Task 2: Zuverlässige Anzeigeformen für Übersicht und Details

**Dateien:**

- Ändern: `tests/web/test_kampagnen.py:75-100`
- Ändern: `tests/web/test_kampagnen.py` im Bereich Liste und Detail
- Ändern: `web/routen/kampagnen.py:251-395`

**Schnittstellen:**

- Verwendet: erweiterter `kampagnen_stand()` und vorhandener `postfaecher()`.
- Liefert: `kennzahlen`, gefilterte `kampagnen`, `kd_kennzahlen`, `kd_warteschlange`, `kd_sendefenster` und `kd_tageslimit` für Jinja.

- [ ] **Schritt 1: Kampagnen-Fake vollständig machen**

`FakeInstantlyLeser` bekommt neben `kampagnen_stand()` eine feste Postfachantwort:

```python
def postfaecher(self):
    return {
        "erreichbar": True,
        "stand": datetime(2026, 7, 22, 10, 30),
        "postfaecher": [{
            "email": "sender@firma.de", "status": "verbunden",
            "warmup": "an", "daily_limit": 20,
        }],
    }
```

`_stand()` ergänzt alle neuen Felder und behält passende Vorgaben:

```python
"empfaenger": 12,
"geoeffnet": 4,
"unzustellbar": 1,
"abgeschlossen": 3,
"heute_versendet": 7,
"absender": ["sender@firma.de"],
"sendefenster": [{
    "name": "Werktage", "von": "08:00", "bis": "19:00",
    "tage": {"0": False, "1": True, "2": True, "3": True,
             "4": True, "5": True, "6": False},
    "zeitzone": "Europe/Berlin",
}],
```

- [ ] **Schritt 2: Fehlende Routentests schreiben**

Die neuen Tests prüfen:

```python
def test_liste_zeigt_wholix_kennzahlen_und_filtert_nach_status(angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-a": _stand(status="aktiv", name="Aktive Runde"),
        "camp-b": _stand(status="abgeschlossen", name="Fertige Runde"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-090000", campaign_id="camp-a")
    _lauf_anlegen(daten_dir, "moveo", "moveo.yaml",
                  ts="20260720-091500", campaign_id="camp-b")

    html = angemeldeter_client.get("/kampagnen?status=aktiv").text
    assert "Geöffnet" in html
    assert "Unzustellbar" in html
    assert "Instantly liefert keinen verlässlichen Zähler" in html
    assert "Aktive Kampagnen" in html
    assert "Aktive Runde" in html
    assert "Fertige Runde" not in html


def test_detail_zeigt_warteschlange_sendefenster_und_tageslimit(angemeldeter_client, daten_dir):
    angemeldeter_client.app.state.instantly_leser = FakeInstantlyLeser({
        "camp-1": _stand(status="aktiv"),
    })
    _lauf_anlegen(daten_dir, "demo-gmbh", "demo-gmbh.yaml",
                  ts="20260720-093000", campaign_id="camp-1")

    html = angemeldeter_client.get("/kampagnen/demo-gmbh/20260720-093000").text
    assert "Warteschlange" in html
    assert "Nicht getrennt verfügbar" in html
    assert "Heute 7 von 20 versendet" in html
    assert "Mo–Fr · 08:00–19:00" in html
    assert "Europe/Berlin" in html
```

- [ ] **Schritt 3: Tests ausführen und die erwarteten Fehler sehen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_kampagnen.py -q
```

Erwartet: Die neuen sichtbaren Texte fehlen.

- [ ] **Schritt 4: Reine Helfer für unbekannte Summen und Sendefenster bauen**

```python
def _summe_oder_unbekannt(zeilen: list[dict], feld: str):
    werte = [zeile.get(feld) for zeile in zeilen]
    if not werte or any(wert is None for wert in werte):
        return None
    return sum(werte)


def _warteschlange(gesamt_empfaenger: int, schritt_anzahl: int, stand: dict) -> dict:
    moeglich = gesamt_empfaenger * schritt_anzahl
    versendet = stand.get("versendet")
    unzustellbar = stand.get("unzustellbar")
    if versendet is None or unzustellbar is None:
        return {"gesamt": moeglich, "versendet": versendet,
                "unzustellbar": unzustellbar, "ungetrennt": None}
    gesamt = max(moeglich, versendet + unzustellbar)
    return {"gesamt": gesamt, "versendet": versendet,
            "unzustellbar": unzustellbar,
            "ungetrennt": max(gesamt - versendet - unzustellbar, 0)}
```

Für die Tageslimits werden nur Postfächer aus `stand["absender"]` summiert.
Sobald eines davon kein `daily_limit` hat, bleibt die Summe `None`. Das
Sendefenster wird mit der Zuordnung `0=So`, `1=Mo`, …, `6=Sa` formatiert;
unvollständige Zeit- oder Zonenangaben ergeben den festgelegten Hinweis statt
einer Ausnahme.

- [ ] **Schritt 5: Listen- und Detailkontext erweitern**

`kampagnen_liste()` akzeptiert `suche: str = ""` und `status: str = "alle"`.
Die Kennzahlen werden vor dem Filtern aus allen Zeilen berechnet; Suche und
Status wirken nur auf die Tabelle. `_detail_kontext()` ruft `postfaecher()`
einmal auf und übergibt die fertigen Anzeigeformen an Jinja.

- [ ] **Schritt 6: Routentests erneut ausführen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_kampagnen.py -q
```

Erwartet: alle Kampagnentests bestehen.

- [ ] **Schritt 7: Aufgabe festhalten**

```bash
git add web/routen/kampagnen.py tests/web/test_kampagnen.py
git commit -m "feat: prepare reliable Wholix campaign views"
```

---

### Task 3: Kampagnenübersicht im Wholix-Muster

**Dateien:**

- Ändern: `tests/web/test_kampagnen.py`
- Ändern: `web/templates/kampagnen_liste.html`
- Ändern: `web/static/stil.css`

**Schnittstellen:**

- Verwendet: `kennzahlen`, `suche`, `status_filter`, `kampagnen` und `vorbereitung`.
- Liefert: serverseitig lesbare Kennzahlenkarten, Filterform und Tabelle.

- [ ] **Schritt 1: Sichtbaren Web-Test ergänzen**

Der Test prüft die acht Kartenbezeichnungen, die vorausgefüllte Suche, den
Statusfilter, Tabellenüberschriften und den weiterhin vorhandenen
Vorbereitungsbereich. Die Abfrage `?suche=demo&status=aktiv` muss den Suchwert
und die aktive Auswahl im HTML zurückgeben.

- [ ] **Schritt 2: Test ausführen und den erwarteten Fehler sehen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_kampagnen.py -q
```

Erwartet: neue Klassen und Karten fehlen.

- [ ] **Schritt 3: Übersichtsvorlage umbauen**

Die Vorlage erhält in dieser Reihenfolge:

```html
<section class="wholix-karten" aria-label="Kampagnen-Kennzahlen">
  <div class="wholix-karte wholix-karte--violett"><strong>{{ kennzahlen.kampagnen }}</strong><span>Kampagnen</span></div>
  <div class="wholix-karte wholix-karte--gruen"><strong>{{ kennzahlen.aktiv }}</strong><span>Aktive Kampagnen</span></div>
  <div class="wholix-karte wholix-karte--blau"><strong>{{ kennzahlen.empfaenger }}</strong><span>Empfänger</span></div>
  <div class="wholix-karte wholix-karte--mint"><strong>{{ kennzahlen.geoeffnet if kennzahlen.geoeffnet is not none else '—' }}</strong><span>Geöffnet</span></div>
  <div class="wholix-karte wholix-karte--orange"><strong>{{ kennzahlen.versendet if kennzahlen.versendet is not none else '—' }}</strong><span>Versendet</span></div>
  <div class="wholix-karte wholix-karte--violett"><strong>{{ kennzahlen.antworten if kennzahlen.antworten is not none else '—' }}</strong><span>Antworten</span></div>
  <div class="wholix-karte wholix-karte--rot" title="Instantly liefert keinen verlässlichen Zähler"><strong>—</strong><span>Fehlgeschlagen</span></div>
  <div class="wholix-karte wholix-karte--orange"><strong>{{ kennzahlen.unzustellbar if kennzahlen.unzustellbar is not none else '—' }}</strong><span>Unzustellbar</span></div>
</section>
```

Danach folgen Filterform, Vorbereitungsbereich und eine weiße, horizontal
rollbare Tabelle mit Status, Empfängern, geöffnet, versendet, Antworten und
unzustellbar.

- [ ] **Schritt 4: Kampagnen-CSS ergänzen**

Es werden ausschließlich kampagnenspezifische Klassen ergänzt: ein Raster
mit `repeat(auto-fit, minmax(132px, 1fr))`, 14-Pixel-Radius, helle
`#E7E9F0`-Ränder, orange Hauptaktion `#F5A000`, farbige Zahlen und ein
horizontal rollbarer Tabellenrahmen. Unter `760px` stehen Kopf und Filter
untereinander; Karten bleiben mindestens zweispaltig.

- [ ] **Schritt 5: Übersichtstests ausführen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_kampagnen.py -q
```

Erwartet: alle Kampagnentests bestehen.

- [ ] **Schritt 6: Aufgabe festhalten**

```bash
git add web/templates/kampagnen_liste.html web/static/stil.css tests/web/test_kampagnen.py
git commit -m "feat: match Wholix campaign overview"
```

---

### Task 4: Kampagnendetails mit Warteschlange und Sendefenster

**Dateien:**

- Ändern: `tests/web/test_kampagnen.py`
- Ändern: `web/templates/kampagne_detail.html`
- Ändern: `web/static/stil.css`

**Schnittstellen:**

- Verwendet: `kd_kennzahlen`, `kd_warteschlange`, `kd_schritte`, `kd_sendefenster`, `kd_tageslimit` sowie die vorhandenen Kampagnenaktionen.
- Liefert: Wholix-nahe Detailfläche ohne JavaScript-Datenabruf.

- [ ] **Schritt 1: Fehler- und Leerzustände zuerst testen**

Ein Test setzt alle neuen Live-Werte auf `None` und prüft „—“, „Instantly
liefert keinen verlässlichen Zähler“ und „Nicht in Instantly hinterlegt“.
Ein weiterer Test behält die vorhandenen Aktivieren-/Pausieren-Aktionen bei.

- [ ] **Schritt 2: Tests ausführen und die erwarteten Fehler sehen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web/test_kampagnen.py -q
```

Erwartet: die neuen Leerzustandstexte fehlen.

- [ ] **Schritt 3: Detailvorlage in vier ruhige Blöcke gliedern**

1. Kopf und sieben Kennzahlenkarten;
2. „Kampagnenangaben“ mit vorhandenen Freigabe- und Absenderwerten;
3. „Warteschlange“ mit Ring, Legende und Schrittbalken;
4. „Tageslimit und Sendefenster“ mit Statuspunkt und Instantly-Link.

Der Ring verwendet ein serverseitig berechnetes CSS-Verhältnis. Wenn die
Zahlen unbekannt sind, wird ein neutraler Ring ohne Prozentangabe gezeigt.
„Fehlgeschlagen“ bleibt immer `—` mit Erklärung. Bestehende Formulare für
Aktivieren/Pausieren und ihre Bestätigungssätze bleiben unverändert.

- [ ] **Schritt 4: Detail-CSS ergänzen**

Der Detailbereich erhält eine maximale Breite von `1180px`, weiße
Abschnittskarten mit `14px` Radius, einen `160px` großen Ring, eine
zweispaltige Warteschlangenfläche und schlanke Schrittbalken. Unter `820px`
werden Ring, Angaben und Limitbereich einspaltig. Fokusrahmen verwenden das
Wholix-Orange und `prefers-reduced-motion` wird respektiert.

- [ ] **Schritt 5: Alle Web-Tests ausführen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest tests/web -q
```

Erwartet: alle Web-Tests bestehen.

- [ ] **Schritt 6: Aufgabe festhalten**

```bash
git add web/templates/kampagne_detail.html web/static/stil.css tests/web/test_kampagnen.py
git commit -m "feat: add Wholix campaign operation details"
```

---

### Task 5: Vollprüfung, Bildschirmfotos und Projektstand

**Dateien:**

- Ändern: `docs/wholix-nachbau-roadmap.md`
- Ändern: `project-context.md`
- Erzeugen: Bildschirmfotos unter `.superpowers/` (bleiben durch `.gitignore` außerhalb des Commits)

**Schnittstellen:**

- Verwendet: fertige Testanwendung mit Testdaten.
- Liefert: frischer Testnachweis, sichtbarer Vergleich und fortsetzbarer Projektstand.

- [ ] **Schritt 1: Vollständige Testsammlung ausführen**

```bash
'/Users/mehremegashi/Desktop/AI Coldmailing system/.venv/bin/python' -m pytest -q
```

Erwartet: 0 Fehler; die genaue Anzahl wird im Abschluss festgehalten.

- [ ] **Schritt 2: Testanwendung lokal starten**

Die App wird mit einem nur lokal erreichbaren Test-Datenordner gestartet.
Es werden keine echten Postfächer verbunden, keine Kampagne aktiviert und
keine E-Mail versendet.

- [ ] **Schritt 3: Übersicht und Detail als Bildschirmfoto prüfen**

Je ein Bildschirmfoto wird bei großer Breite und eines bei schmaler Breite
aufgenommen. Geprüft werden: Kartenreihenfolge, Tabellenlesbarkeit,
Warteschlangenring, Sendefenster, Leerzustände und sichtbare Fokusführung.

- [ ] **Schritt 4: Fahrplan und Projektkontext aktualisieren**

In der Roadmap wird Phase 1 mit dem tatsächlichen Stand versehen. In
`project-context.md` kommen die vier Abschnitte „Worum es geht“, „Aktueller
Stand“, „Entscheidungen“ und „Nächste Schritte“ mit dem Wholix-Nachbau als
aktuellem Projektstand.

- [ ] **Schritt 5: Schlussprüfung und Dokumentations-Commit**

```bash
git diff --check
git status --short
git add docs/wholix-nachbau-roadmap.md project-context.md
git commit -m "docs: record Wholix campaign phase 1 result"
```

Erwartet: nur beabsichtigte Dateien sind festgehalten; `.superpowers/` bleibt
unverfolgt und ignoriert.

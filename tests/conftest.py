"""Gemeinsame Vorgaben für alle Tests.

## Warum es diese Datei gibt (21.08.2026)

Seit die Automatisierungs-Prüfung Pflicht ist (Dafinas Auftrag), muss
JEDE Firma ein Urteil haben, bevor ein bezahlter Schritt passieren darf.
Wer nicht eindeutig als "keine Automatisierung" beurteilt werden kann,
gilt als unsicher und kommt in keine Kampagne - genau das war vorher das
Leck.

Für die Kaskaden-Tests (Hunter, Dropcontact, Impressum, info@-Regel,
Schnelllauf ...) ist diese Prüfung nur ein Tor davor, nicht ihr Thema.
Damit sie weiter das prüfen, wofür sie geschrieben wurden, tut diese
Datei so, als hätte die Pool-Klassifikation (Phase 2) bereits ALLE
Firmen als "keine Automatisierung" beurteilt. Das ist keine Abkürzung um
die Regel herum, sondern der normale Produktionsfall: die Datei
`daten/automation-klassifikation.json` kennt heute 4.964 Firmen.

Die Tests, in denen die Prüfung SELBST das Thema ist
(`test_automation_pflicht.py`, `test_wettbewerber_ausschluss.py`),
überschreiben das - sie setzen `laden` selbst auf einen leeren Stand und
sehen damit das echte Verhalten.

Wer eine neue Kaskaden-Prüfung schreibt, muss also wissen: hier gilt
standardmäßig "alle schon geprüft, alle unbedenklich".
"""
import pytest

import pipeline.automation_klassifikation as _klassifikation


UNBEDENKLICH = {"offers_automation_services": "no",
                "automation_check_reason": "Testvorgabe (tests/conftest.py)",
                "automation_check_source": "test",
                "automation_checked_at": "2026-08-21T00:00:00"}


class _PoolMitVorgabe(dict):
    """Der Pool-Stand des Tests, plus 'unbekannt = unbedenklich'.

    Es bleibt ein echtes dict: `items()` liefert genau das, was der Test
    selbst hinterlegt hat (pipeline.master_db mischt darüber die
    Pool-Urteile ein). Nur die Nachfrage nach einer NICHT hinterlegten
    Firma bekommt die Vorgabe.
    """

    def get(self, kennung, default=None):
        if dict.__contains__(self, kennung):
            return dict.__getitem__(self, kennung)
        return {"name": kennung, **UNBEDENKLICH}


@pytest.fixture(autouse=True)
def _pool_kennt_alle_firmen(monkeypatch):
    echt = _klassifikation.laden

    def _laden(daten_dir="."):
        # Der ECHTE Projekt-Pool (daten/automation-klassifikation.json,
        # 1,8 MB, 4.964 Firmen) hat in Tests nichts verloren - Tests
        # dürfen nicht von gewachsenen Echtdaten abhängen. Legt ein Test
        # selbst einen Stand an (tmp_path), wird der gelesen.
        stand = {} if str(daten_dir) == "." else echt(daten_dir)
        return _PoolMitVorgabe(stand)

    monkeypatch.setattr(_klassifikation, "laden", _laden)

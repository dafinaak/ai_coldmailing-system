"""Geteilte Test-Fakes fuer HTTP-Antworten und -Sitzungen.

Historie: Diese beiden Klassen lebten in tests/test_apollo.py und wurden von
mehreren Testdateien importiert. Mit dem Entfernen der Apollo-Anbindung
(Kaskade Prospeo/Impressum ersetzt Apollo, 27.07.2026) sind sie hierher
umgezogen - unveraendert, damit die bestehenden Tests gleich bleiben."""


class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text
    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, antworten):
        self.antworten, self.aufrufe, self.urls = list(antworten), [], []
    def post(self, url, json=None, data=None, headers=None, timeout=None):
        # json ODER data (Formular-Feld, z. B. Overpass) - was gesetzt ist,
        # wird festgehalten; bestehende Tests bleiben unveraendert.
        self.aufrufe.append(json if json is not None else data)
        self.urls.append(url)
        antwort = self.antworten.pop(0)
        if isinstance(antwort, Exception):
            raise antwort            # simuliert Netzwerk-Abrisse/Timeouts
        return antwort
    def get(self, url, params=None, headers=None, timeout=None):
        self.aufrufe.append(params)
        self.urls.append(url)
        return self.antworten.pop(0)

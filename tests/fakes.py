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
    def post(self, url, json=None, headers=None, timeout=None):
        self.aufrufe.append(json)
        self.urls.append(url)
        return self.antworten.pop(0)
    def get(self, url, params=None, headers=None, timeout=None):
        self.aufrufe.append(params)
        self.urls.append(url)
        return self.antworten.pop(0)

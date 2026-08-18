"""Der Knopf "In Instantly öffnen" muss auch wirklich dort landen.

Gefunden am 17.08.2026: Der Knopf führte auf 404. Die Adresse stammte aus
der Design-Skizze und war nie geöffnet worden - es fehlte die Endung
"/analytics". Sie stand an ZWEI Stellen im Code und war an beiden falsch.

Deshalb jetzt eine einzige Definition, die beide Vorlagen benutzen.
"""
from web.app import instantly_kampagne_url


ECHTE_ADRESSE = ("https://app.instantly.ai/app/campaign/"
                 "2b3d5c9d-caad-48e0-a684-43e26e74ff6a/analytics")


def test_adresse_entspricht_der_echten_oberflaeche():
    # Wörtlich die Adresse, die Instantly am 17.08.2026 im Browser zeigte.
    assert instantly_kampagne_url("2b3d5c9d-caad-48e0-a684-43e26e74ff6a") == ECHTE_ADRESSE


def test_endung_analytics_fehlt_nicht():
    # Ohne diese Endung antwortet Instantly mit 404 - genau der alte Fehler.
    assert instantly_kampagne_url("camp-1").endswith("/analytics")


def test_kampagnen_nummer_steht_drin():
    assert "/camp-1/" in instantly_kampagne_url("camp-1")

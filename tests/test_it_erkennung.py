"""IT-Firmen aus einer Nicht-IT-Liste erkennen (Dafina, 15.10.2026:
"qka tken zona IT largoj ne fund se sna duhen").

Das Profil-Urteil soll sie schon draussen halten. Dieser Schritt ist das
Netz darunter: der Prozess-Prompt ist neu und an echten Firmen nie
erprobt, und in der Rohernte der Zone 32 waren 12 Prozent IT
(25 "IT-Berater", 24 "Softwareentwickler/-hersteller" von 400 Orten).

Der Name allein reicht nicht: "IT" steckt als Silbe in vielen deutschen
Woertern - Qualitaet, Sicherheit, Mitarbeiter. Darum Wortgrenzen.
"""
from pipeline.it_erkennung import ist_it_firma


def firma(**felder):
    basis = {"name": "Muster GmbH", "categories": [], "profil_typ": "",
             "profil_grund": ""}
    basis.update(felder)
    return basis


def test_eine_it_kategorie_faellt_auf():
    treffer, grund = ist_it_firma(firma(categories=["IT-Berater"]))
    assert treffer is True
    assert "IT-Berater" in grund


def test_softwarehersteller_faellt_auf():
    treffer, _ = ist_it_firma(
        firma(categories=["Softwareentwickler/-hersteller"]))
    assert treffer is True


def test_der_name_kann_es_verraten():
    assert ist_it_firma(firma(name="Labusch BusinessIT Solutions"))[0] is True
    assert ist_it_firma(firma(name="Meier EDV-Service"))[0] is True
    assert ist_it_firma(firma(name="Systemhaus Nord GmbH"))[0] is True


def test_das_urteil_kann_es_verraten():
    treffer, grund = ist_it_firma(
        firma(profil_typ="IT-Dienstleister mit Schwerpunkt IT-Support"))
    assert treffer is True
    assert "profil_typ" in grund


def test_ein_echter_prozessberater_bleibt_drin():
    for f in (firma(name="ThoR Management Consulting",
                    categories=["Unternehmensberater"]),
              firma(name="LQM Heers | Qualitätsmanagement | Lean Management",
                    categories=["Unternehmensberater"]),
              firma(name="REFA Beratung Westfalen",
                    profil_typ="Prozess- und Organisationsberatung"),
              firma(name="Sicherheitsberatung Peters"),
              firma(name="Mitarbeiterentwicklung Nord")):
        treffer, grund = ist_it_firma(f)
        assert treffer is False, f"{f['name']} -> {grund}"


def test_it_als_silbe_ist_kein_treffer():
    """"Qualitaet", "Sicherheit", "Mitarbeiter" tragen "it" in sich.

    Ohne Wortgrenzen wuerde jede Qualitaetsberatung als IT gelten - und
    genau die ist Zielprofil.
    """
    for name in ("Qualitätsmanagement Schmidt", "Arbeitssicherheit Nord",
                 "Mitarbeiterberatung Hansen", "Capital Beratung"):
        assert ist_it_firma(firma(name=name))[0] is False, name


def test_die_kategorie_allein_entscheidet_nicht_gegen_ein_klares_urteil():
    """Dafinas Regel vom 03.09.2026: die Webseite entscheidet, nicht die
    Kategorie der Karte - Google vergibt vier bis fuenf je Firma.

    Ein klares Prozess-Urteil schlaegt also eine IT-Kategorie. Der Fund
    wird trotzdem gemeldet, damit ein Mensch ihn sehen kann.
    """
    treffer, grund = ist_it_firma(
        firma(name="Prozesswerk Beratung", categories=["IT-Berater"],
              profil_typ="Prozess- und Organisationsberatung"))
    assert treffer is False
    assert "IT-Berater" in grund, "der Fund muss trotzdem sichtbar sein"

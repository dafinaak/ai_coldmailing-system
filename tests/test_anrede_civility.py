"""A known gender beats a guessed one.

baue_anrede() reads the first name against a list. A name that is not on
the list falls through to "Herr" - which is why on 03.09.2026 fourteen
women in our zones were addressed as "Herr Neuß", "Frau" nowhere in eight
lists. In a cold email that is not a rounding error, it is the first line
the reader sees.

Dropcontact returns "civility" ("MR"/"MRS") in the same paid row as the
address. These tests pin that this known value wins over the guess, and
that an absent or unknown value changes nothing - a wrong override would
be worse than the guess it replaces.
"""
from pipeline.anrede_spalte import baue_anrede


def test_civility_schlaegt_die_namensliste():
    """"Sonja" steht nicht auf der Frauenliste und wuerde als "Herr"
    durchfallen - genau der Fall aus Zone 33."""
    anrede, grund = baue_anrede("Sonja Neuß", civility="MRS")
    assert anrede == "Frau Neuß"
    assert "Dropcontact" in grund


def test_civility_bestaetigt_auch_maennlich():
    anrede, grund = baue_anrede("Peter Meier", civility="MR")
    assert anrede == "Herr Meier"
    assert "Dropcontact" in grund


def test_ohne_civility_bleibt_alles_wie_vorher():
    assert baue_anrede("Peter Meier") == baue_anrede("Peter Meier", civility="")
    assert baue_anrede("Peter Meier", civility=None)[0] == "Herr Meier"


def test_unbekannte_civility_wird_ignoriert():
    """Ein Wert, den wir nicht kennen, darf die Anrede nicht erfinden."""
    anrede, grund = baue_anrede("Peter Meier", civility="DR")
    assert anrede == "Herr Meier"
    assert "Dropcontact" not in grund


def test_civility_rettet_keinen_unvollstaendigen_namen():
    """Ohne vollen Namen gibt es keine Anrede - auch mit bekanntem
    Geschlecht nicht, denn es fehlt der Nachname zum Ansprechen."""
    anrede, grund = baue_anrede("Sonja", civility="MRS")
    assert anrede == ""
    assert grund == "kein vollstaendiger Name"


def test_civility_ueberschreibt_auch_den_neutralen_fall():
    """Bei einem uneindeutigen Vornamen liefern wir sonst den vollen Namen
    ohne Anrede. Ist das Geschlecht bekannt, ist das nicht mehr noetig."""
    anrede, _ = baue_anrede("Kim Berger", civility="MRS")
    assert anrede == "Frau Berger"

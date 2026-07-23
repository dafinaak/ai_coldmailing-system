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
    assert isinstance(daten["nonce"], str)
    assert len(daten["nonce"]) >= 24
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


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_leerer_antworttext_wird_abgelehnt(text):
    with pytest.raises(AntwortTextUngueltig, match="nicht leer"):
        validiere_antworttext(text)


def test_antworttext_wird_getrimmt_und_auf_10000_zeichen_begrenzt():
    assert validiere_antworttext("  Danke.  ") == "Danke."
    with pytest.raises(AntwortTextUngueltig, match="10.000"):
        validiere_antworttext("x" * 10_001)


def test_freigabe_kann_dateisystemweit_nur_einmal_verbraucht_werden(
    tmp_path,
):
    ziel = verbrauche_antwort_freigabe(tmp_path, "nonce-1")
    assert ziel.parent == tmp_path / "postfach-antworten"
    assert stat.S_IMODE(ziel.stat().st_mode) == 0o600

    with pytest.raises(AntwortFreigabeBenutzt):
        verbrauche_antwort_freigabe(tmp_path, "nonce-1")


def test_unvollstaendige_freigabe_wird_nicht_signiert():
    serializer = URLSafeTimedSerializer("test-secret")
    with pytest.raises(AntwortFreigabeUngueltig, match="unvollständig"):
        erstelle_antwort_freigabe(
            serializer, kontakt=" ", reply_to_uuid="mail-1"
        )

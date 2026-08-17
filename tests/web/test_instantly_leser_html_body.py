"""HTML-Mailbodies muessen im Postfach lesbar ankommen.

Gefunden am 13.08.2026 an der eigenen Zustellprobe: Instantly lieferte den
Body NUR als 'html' (kein 'text', kein 'content_preview'). Der Leser las
damals ausschliesslich body['text'] - der Nachrichtenbereich blieb leer und
man sah nur den Betreff, den man dann fuer die ganze Mail hielt.
"""
from web.instantly_leser import _nachricht_aus_email, _text_aus_html


def _email(body, **rest):
    grund = {"id": "1", "campaign_id": "c1", "eaccount": "wir@example.com",
             "subject": "Betreff", "timestamp_email": "2026-08-13T11:23:36.000Z",
             "body": body}
    grund.update(rest)
    return grund


def test_html_body_wird_gelesen_wenn_es_keinen_text_gibt():
    nachricht = _nachricht_aus_email(
        _email({"html": "<p>Guten Tag Frau Keqmezi,</p><p>was sagen Sie?</p>"}),
        "gesendet")

    # Absaetze bleiben durch eine Leerzeile getrennt - so liest sich die
    # Mail im Detailbereich wie im echten Postfach.
    assert nachricht["text"] == "Guten Tag Frau Keqmezi,\n\nwas sagen Sie?"


def test_reiner_text_hat_weiter_vorrang():
    nachricht = _nachricht_aus_email(
        _email({"text": "Klartext", "html": "<p>HTML-Fassung</p>"}), "gesendet")

    assert nachricht["text"] == "Klartext"


def test_content_preview_bleibt_die_letzte_rettung():
    nachricht = _nachricht_aus_email(
        _email({}, content_preview="Vorschau"), "gesendet")

    assert nachricht["text"] == "Vorschau"


def test_kein_markup_im_ergebnis():
    # Der Body kommt von aussen. Es darf NIE Markup durchgereicht werden -
    # angezeigt wird Text, nicht HTML.
    nachricht = _nachricht_aus_email(
        _email({"html": '<p>Hallo <a href="http://x.de">hier</a></p>'
                        '<script>alert(1)</script>'}), "empfangen")

    assert nachricht["text"] == "Hallo hier"
    assert "<" not in nachricht["text"]
    assert "alert" not in nachricht["text"]


def test_umbrueche_und_umlaute():
    assert _text_aus_html("Zeile eins<br>Zeile zwei") == "Zeile eins\nZeile zwei"
    assert _text_aus_html("<p>Gr&uuml;&szlig;e</p>") == "Grüße"


def test_leerzeilen_werden_nicht_endlos():
    # Mail-HTML ist voll von Einrueckungen und leeren Absaetzen: drei leere
    # Absaetze duerfen nicht drei Leerzeilen ergeben, sondern hoechstens eine.
    roh = "<div>Eins</div><p></p><p></p><p></p><div>Zwei</div>"

    assert _text_aus_html(roh) == "Eins\n\nZwei"


def test_kaputtes_html_reisst_die_seite_nicht():
    assert _text_aus_html("<p>Halb offen <b>fett") == "Halb offen fett"
    assert _text_aus_html("") == ""

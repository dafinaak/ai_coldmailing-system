from pipeline.kurzmeldung import kurzmeldung_text


ZAHLEN = {"leads_count": 60, "emails_sent_count": 40, "open_count": 18,
          "reply_count": 3, "bounced_count": 1}


def test_kurzmeldung_ist_deutsch_und_vollstaendig():
    text = kurzmeldung_text("Partnerschafts-Anfrage IT-Dienstleister",
                            ZAHLEN, stand="29.07.2026")
    assert "Partnerschafts-Anfrage IT-Dienstleister" in text
    assert "29.07.2026" in text
    assert "60" in text and "Kontakte" in text
    assert "40" in text and "versendet" in text
    assert "18" in text and "geöffnet" in text
    assert "3" in text and "geantwortet" in text
    assert "1" in text and "Rückläufer" in text


def test_fehlende_zahlen_werden_als_unbekannt_gezeigt_statt_erfunden():
    # Instantly liefert manchmal keine Zeile (live beobachtet 22.07.2026,
    # siehe project-context) - dann steht "unbekannt" da, nie eine
    # erfundene Null.
    text = kurzmeldung_text("Kampagne X", {}, stand="29.07.2026")
    assert "unbekannt" in text
    assert " 0 " not in f" {text} "

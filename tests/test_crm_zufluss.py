from web.crm_speicher import KontakteSpeicher
from web.crm_zufluss import antwortende_uebernehmen


def _speicher(tmp_path):
    return KontakteSpeicher(tmp_path / "kontakte.db",
                            uhr=lambda: "2026-07-29T12:00:00")


def _konversation(email="chef@firma.de", richtungen=("gesendet", "empfangen"),
                  campaign_id="camp-1"):
    # "empfangen" ist das Wort, das web.instantly_leser wirklich liefert.
    # Bis 17.08.2026 stand hier "erhalten" - ein Wort, das in echten Daten
    # nie vorkommt. Der Test war gruen, der CRM-Zufluss legte trotzdem nie
    # einen Kontakt an. Der Test hat sich selbst geprueft, nicht die Welt.
    return {"kontakt_email": email,
            "nachrichten": [{"richtung": r, "campaign_id": campaign_id}
                            for r in richtungen]}


def test_antwortende_werden_als_kontakt_angelegt(tmp_path):
    s = _speicher(tmp_path)
    neu = antwortende_uebernehmen(
        s, [_konversation()],
        kontakt_info={"chef@firma.de": {"name": "Max Chef", "firma": "Firma GmbH"}},
        kampagnen_namen={"camp-1": "Partnerschaft IT"})
    assert neu == 1
    k, = s.kontakte()
    assert k["email"] == "chef@firma.de"
    assert k["name"] == "Max Chef"
    assert k["firma"] == "Firma GmbH"
    assert k["kampagne"] == "Partnerschaft IT"
    assert k["stufe"] == "neuer_lead"


def test_nur_gesendete_nachrichten_erzeugen_keinen_kontakt(tmp_path):
    # Entscheidung 29.07.: ins CRM kommt NUR, wer geantwortet hat.
    s = _speicher(tmp_path)
    neu = antwortende_uebernehmen(s, [_konversation(richtungen=("gesendet",))])
    assert neu == 0 and s.kontakte() == []


def test_zweiter_durchlauf_erzeugt_keine_duplikate(tmp_path):
    s = _speicher(tmp_path)
    assert antwortende_uebernehmen(s, [_konversation()]) == 1
    assert antwortende_uebernehmen(s, [_konversation()]) == 0
    assert len(s.kontakte()) == 1


def test_ohne_lokale_kontaktdaten_bleibt_der_kontakt_nutzbar(tmp_path):
    s = _speicher(tmp_path)
    antwortende_uebernehmen(s, [_konversation(email="Unbekannt@Firma.DE")])
    k, = s.kontakte()
    assert k["email"] == "unbekannt@firma.de"   # normalisiert
    assert k["name"] == "" and k["firma"] == ""
    assert k["kampagne"] == "camp-1"            # Kampagnen-Nummer als Rückfall

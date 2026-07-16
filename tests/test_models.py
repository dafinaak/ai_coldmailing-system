from pipeline.models import Lead

def test_lead_normalisiert_email():
    lead = Lead(first_name="Anna", last_name="Muster", email="  Anna@Firma.DE ",
                company="Firma GmbH", title="CEO", website="https://firma.de", source="apollo")
    assert lead.email == "anna@firma.de"

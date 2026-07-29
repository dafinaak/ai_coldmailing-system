from pipeline.listen_fusion import fusionieren


def firma(name, domain="", plz="30159", quelle="maps", **extra):
    return {"name": name, "website": f"https://{domain}" if domain else "",
            "domain": domain, "address": extra.pop("address", ""),
            "plz": plz, "telefon": extra.pop("telefon", ""),
            "vorhandene_email": extra.pop("vorhandene_email", ""),
            "categories": extra.pop("categories", []),
            "quelle": quelle, **extra}


def test_gleiche_domain_wird_fusioniert_und_reichste_daten_bleiben():
    maps = [firma("Nordfalke IT", "nordfalke-it.de", telefon="0511 1")]
    gelbe = [firma("Nordfalke IT GmbH", "nordfalke-it.de", quelle="gelbe_seiten",
                   vorhandene_email="info@nordfalke-it.de")]
    firmen, bericht = fusionieren([maps, gelbe], plz_praefixe=("30", "31"))
    f, = firmen
    assert f["telefon"] == "0511 1"                       # aus Quelle 1
    assert f["vorhandene_email"] == "info@nordfalke-it.de"  # aus Quelle 2
    assert sorted(f["quellen"]) == ["gelbe_seiten", "maps"]
    assert bericht["je_quelle"] == {"maps": 1, "gelbe_seiten": 1}
    assert bericht["einzigartig"] == 1
    assert bericht["ueberschneidungen"] == 1


def test_ohne_domain_fusioniert_ueber_namenskern_und_plz():
    a = [firma("Falkenberg EDV Service", plz="30890")]
    b = [firma("Falkenberg EDV GmbH", plz="30890", quelle="overpass")]
    fremd = [firma("Falkenberg EDV", plz="10115", quelle="overpass")]
    firmen, bericht = fusionieren([a, b, fremd], plz_praefixe=("30", "31"))
    assert len(firmen) == 1                    # a+b fusioniert, fremd raus
    assert bericht["fremde_plz"] == 1


def test_ausschluss_filter_nach_olivers_vorgaben():
    firmen_liste = [
        firma("Nordfalke IT", "nordfalke-it.de"),
        firma("Hannover Webhosting GmbH", "hann-host.de"),
        firma("Blitz Elektro-Installation", "blitz-elektro.de"),
        firma("Rechenzentrum Nord", "rz-nord.de",
              categories=["Rechenzentren"]),
        firma("Muster Automationstechnik", "muster-auto.de"),
    ]
    firmen, bericht = fusionieren([firmen_liste], plz_praefixe=("30",))
    assert [f["name"] for f in firmen] == ["Nordfalke IT"]
    ausgeschlossen = {a["name"]: a["grund"] for a in bericht["ausgeschlossen"]}
    assert "Hannover Webhosting GmbH" in ausgeschlossen
    assert "Blitz Elektro-Installation" in ausgeschlossen
    assert "Rechenzentrum Nord" in ausgeschlossen
    assert "Muster Automationstechnik" in ausgeschlossen


def test_alte_liste_fuellt_auf_und_gf_hinweis_bleibt_erhalten():
    # Olivers Entscheidung 29.07.2026: Die alte 319er-Liste ist nicht mehr
    # die Basis, dient aber als Auffueller. Ihr Geschaeftsfuehrer-Hinweis
    # (gf_name_liste) muss die Fusion ueberleben - er hilft spaeter der
    # Impressum-Pruefung.
    gescrapte = [firma("Nordfalke IT", "nordfalke-it.de")]
    alte = [firma("Nordfalke IT GmbH", "nordfalke-it.de", quelle="alte_liste",
                  gf_name_liste="Nina Falke"),
            firma("Nur-Alt EDV", "nur-alt.de", quelle="alte_liste",
                  gf_name_liste="Otto Alt")]
    firmen, bericht = fusionieren([gescrapte, alte], plz_praefixe=("30",))
    nach_domain = {f["domain"]: f for f in firmen}
    assert len(firmen) == 2
    assert nach_domain["nordfalke-it.de"]["gf_name_liste"] == "Nina Falke"
    assert nach_domain["nur-alt.de"]["gf_name_liste"] == "Otto Alt"
    assert "alte_liste" in nach_domain["nur-alt.de"]["quellen"]


def test_bericht_zaehlt_firmen_ohne_webseite():
    firmen, bericht = fusionieren(
        [[firma("Mit Web", "mit-web.de"), firma("Ohne Web")]],
        plz_praefixe=("30",))
    assert len(firmen) == 2
    assert bericht["ohne_webseite"] == 1

import pytest
from pipeline.paket_schnueren import paket_schnueren, UngepruefteListe


def firma(name, domain, **extra):
    return {"name": name, "domain": domain, "website": f"https://{domain}",
            "plz": "30159", "telefon": extra.pop("telefon", "0511 1"),
            "categories": extra.pop("categories", ["IT-Berater"]),
            "quellen": extra.pop("quellen", ["maps"]),
            "gf_name_liste": extra.pop("gf_name_liste", ""), **extra}


def _namen(*domains):
    return {d: {"ausgang": "namen",
                "personen": [{"vorname": "Max", "nachname": "Muster"}]}
            for d in domains}


def _pruefung(passend=(), fremd=()):
    daten = {d: {"passt": True, "typ": "IT-Systemhaus", "grund": "ok"}
             for d in passend}
    daten.update({d: {"passt": False, "typ": "branchenfremd", "grund": "nein"}
                  for d in fremd})
    return daten


# Die Schutzregel: ohne Branchenpruefung gibt es kein Paket ----------------

def test_ohne_branchenpruefung_wird_hart_abgebrochen():
    """Kern-Lehre aus Olivers Beschwerde (30.07.2026): Eine Liste darf nie
    wieder ohne Branchenpruefung in ein Versand-Paket wandern."""
    firmen = [firma("Alpha IT", "alpha.de")]
    with pytest.raises(UngepruefteListe, match="Branchenprüfung"):
        paket_schnueren(firmen, _namen("alpha.de"), branchenpruefung={},
                        groesse=10)


def test_firma_ohne_pruefergebnis_kommt_nicht_ins_paket():
    firmen = [firma("Alpha IT", "alpha.de"), firma("Beta IT", "beta.de")]
    paket, bericht = paket_schnueren(
        firmen, _namen("alpha.de", "beta.de"),
        branchenpruefung=_pruefung(passend=["alpha.de"]),  # beta fehlt
        groesse=10)
    assert [f["domain"] for f in paket] == ["alpha.de"]
    assert bericht["ohne_pruefung"] == 1


def test_nur_geprueft_passende_firmen_mit_namen_kommen_ins_paket():
    firmen = [firma("Alpha IT", "alpha.de"), firma("Fremd GmbH", "fremd.de"),
              firma("Ohne Namen IT", "ohnename.de")]
    paket, bericht = paket_schnueren(
        firmen, _namen("alpha.de", "fremd.de"),   # ohnename.de hat keinen Namen
        branchenpruefung=_pruefung(passend=["alpha.de", "ohnename.de"],
                                   fremd=["fremd.de"]),
        groesse=10)
    assert [f["domain"] for f in paket] == ["alpha.de"]
    assert bericht["ausgeschlossen_branche"] == 1
    assert bericht["ohne_namen"] == 1


def test_paketgroesse_wird_eingehalten_und_reserve_gemeldet():
    firmen = [firma(f"IT {i}", f"it{i}.de") for i in range(5)]
    domains = [f"it{i}.de" for i in range(5)]
    paket, bericht = paket_schnueren(firmen, _namen(*domains),
                                     _pruefung(passend=domains), groesse=2)
    assert len(paket) == 2
    assert bericht["reserve"] == 3
    assert bericht["kandidaten"] == 5


def test_priorisierung_bestaetigter_hinweis_und_datenreichtum_zuerst():
    firmen = [
        firma("Schwach", "schwach.de", telefon="", quellen=["maps"]),
        firma("Reich", "reich.de", telefon="0511 9",
              quellen=["maps", "gelbe_seiten"]),
        firma("Bestaetigt", "bestaetigt.de", gf_name_liste="Max Muster"),
    ]
    domains = ["schwach.de", "reich.de", "bestaetigt.de"]
    paket, _ = paket_schnueren(firmen, _namen(*domains),
                               _pruefung(passend=domains), groesse=3)
    assert [f["domain"] for f in paket] == ["bestaetigt.de", "reich.de",
                                            "schwach.de"]


# Qualitaets-Bericht (der zweite Teil der Lehre: hinsehen, nicht hoffen) ---

def test_bericht_nennt_typen_und_stichprobe_fuer_die_sichtpruefung():
    firmen = [firma(f"IT {i}", f"it{i}.de") for i in range(3)]
    domains = [f"it{i}.de" for i in range(3)]
    paket, bericht = paket_schnueren(firmen, _namen(*domains),
                                     _pruefung(passend=domains), groesse=3)
    assert bericht["typen"] == {"IT-Systemhaus": 3}
    assert len(bericht["stichprobe"]) == 3
    assert all("name" in s and "typ" in s for s in bericht["stichprobe"])

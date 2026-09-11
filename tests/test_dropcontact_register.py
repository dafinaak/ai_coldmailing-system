"""The Dropcontact register: nobody gets paid for twice (Jira AP-216).

Across zones 32-39, 19 people were paid for in more than one zone - 22
payments too many - because every run only looked at its own zone. The
register reads every answer we already have from the files the runs
write anyway, and says for a person: found before (reuse it), asked
before without a result (do not ask again), or unknown (ask).

Decision Dafina, 10.09.2026: an answer counts for 90 days. Older ones
are asked again, so the address is checked once more before sending.
"""
import json
import os
from datetime import date, datetime

import pytest

from pipeline.dropcontact_register import REUSED_SOURCE, load_register

TODAY = date(2026, 9, 10)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _zone_run(root, folder, found=(), asked=(), zeit=None):
    """A zone Dropcontact folder as werkzeuge/zona32-dropcontact.py writes it."""
    run = root / "laeufe" / "leadquellen" / folder
    _write(run / "ergebnisse.json", [
        {"name": f"{last} GmbH", "website": website,
         "dropcontact": {"civility": "Frau"},
         "leads": [{"first_name": first, "last_name": last, "email": email,
                    "source": "dropcontact"}]}
        for first, last, website, email in found])
    request = {"request_id": "r1", "gesendet_nr": list(range(len(asked)))}
    if asked:
        request["gesendet"] = [{"first_name": f, "last_name": l, "website": w}
                               for f, l, w in asked]
    if zeit:
        request["zeit"] = zeit
    _write(run / "request-id.json", request)
    return run


@pytest.fixture
def project(tmp_path):
    _zone_run(tmp_path, "zona33-dropcontact-2026-08-28",
              found=[("Anna", "Alt", "https://www.alt.de/", "anna@alt.de")],
              asked=[("Anna", "Alt", "https://www.alt.de/"),
                     ("Bernd", "Leer", "https://leer.de")],
              zeit="2026-08-28T12:00:00")
    # The big run of 11.08.2026 keeps its paid addresses in a cache file.
    cache = (tmp_path / "laeufe" / "leadquellen" / "plr-30-31" / "paket-1"
             / "lauf-voll" / "zwischenstand.json")
    _write(cache, {"adressen": {
        "dora|dach|dach.de": {"email": "dora@dach.de",
                              "qualification": "nominative@pro"},
        "emil|ohne|ohne.de": None}})
    stamp = datetime(2026, 8, 11, 18, 0).timestamp()
    os.utime(cache, (stamp, stamp))
    # A campaign run: only addresses Dropcontact built count.
    _write(tmp_path / "laeufe" / "kunde-x" / "20260814-145946" / "leads.json",
           {"leads": [
               {"first_name": "Fritz", "last_name": "Form",
                "email": "fritz@form.de", "website": "https://www.form.de/",
                "source": "impressum"},
               {"first_name": "", "last_name": "", "email": "info@info.de",
                "website": "info.de", "source": "info@"},
               {"first_name": "Gerd", "last_name": "Apollo",
                "email": "gerd@apollo.de", "website": "apollo.de",
                "source": "apollo"}]})
    return tmp_path


def test_reuses_an_email_found_in_an_earlier_zone(project):
    register = load_register(project)

    # Spelled differently than in the file - still the same person.
    answer = register.lookup(" anna ", "ALT", "http://alt.de/impressum",
                             today=TODAY)

    assert answer["email"] == "anna@alt.de"
    assert answer["felder"] == {"civility": "Frau"}
    assert answer["run"] == "zona33-dropcontact-2026-08-28"
    assert answer["date"] == "2026-08-28"


def test_knows_who_was_asked_without_a_result(project):
    answer = load_register(project).lookup("Bernd", "Leer", "leer.de",
                                           today=TODAY)

    assert answer is not None
    assert answer["email"] is None


def test_a_person_never_asked_is_unknown(project):
    assert load_register(project).lookup("Zoe", "Neu", "neu.de",
                                         today=TODAY) is None


def test_reads_the_fast_run_cache_and_campaign_leads(project):
    register = load_register(project)

    assert register.lookup("Dora", "Dach", "dach.de",
                           today=TODAY)["email"] == "dora@dach.de"
    assert register.lookup("Emil", "Ohne", "ohne.de",
                           today=TODAY)["email"] is None
    assert register.lookup("Fritz", "Form", "form.de",
                           today=TODAY)["email"] == "fritz@form.de"
    # Apollo found this one, Dropcontact never checked it.
    assert register.lookup("Gerd", "Apollo", "apollo.de", today=TODAY) is None


def test_an_answer_counts_for_90_days_and_not_one_day_longer(tmp_path):
    _zone_run(tmp_path, "zona40-dropcontact-2026-06-12",
              found=[("Hans", "Grenze", "grenze.de", "hans@grenze.de")])
    _zone_run(tmp_path, "zona41-dropcontact-2026-06-11",
              found=[("Ida", "Alt", "alt-ida.de", "ida@alt-ida.de")])
    register = load_register(tmp_path)

    # 12.06. -> 10.09. is exactly 90 days, 11.06. is 91.
    assert register.lookup("Hans", "Grenze", "grenze.de",
                           today=TODAY)["email"] == "hans@grenze.de"
    assert register.lookup("Ida", "Alt", "alt-ida.de", today=TODAY) is None


def test_the_latest_answer_wins(tmp_path):
    # Found in August, but in September Dropcontact no longer had an
    # address - the old one is not reused.
    _zone_run(tmp_path, "zona33-dropcontact-2026-08-28",
              found=[("Anna", "Alt", "alt.de", "anna@alt.de")])
    _zone_run(tmp_path, "zona34-dropcontact-2026-09-03",
              asked=[("Anna", "Alt", "alt.de")])

    answer = load_register(tmp_path).lookup("Anna", "Alt", "alt.de",
                                            today=TODAY)

    assert answer["email"] is None
    assert answer["run"] == "zona34-dropcontact-2026-09-03"


def test_a_reused_address_keeps_the_date_of_its_real_check(tmp_path):
    # Checked on 12.06., reused by a zone run on 05.09. On 11.09. the real
    # check is 91 days old - the reuse must not have made it young again.
    _zone_run(tmp_path, "zona40-dropcontact-2026-06-12",
              found=[("Hans", "Grenze", "grenze.de", "hans@grenze.de")])
    run = _zone_run(tmp_path, "zona41-dropcontact-2026-09-05",
                    found=[("Hans", "Grenze", "grenze.de", "hans@grenze.de")])
    ergebnisse = json.loads((run / "ergebnisse.json").read_text("utf-8"))
    ergebnisse[0]["wiederverwendet_aus"] = {
        "lauf": "zona40-dropcontact-2026-06-12", "datum": "2026-06-12"}
    (run / "ergebnisse.json").write_text(json.dumps(ergebnisse), "utf-8")

    register = load_register(tmp_path)

    assert register.lookup("Hans", "Grenze", "grenze.de",
                           today=date(2026, 9, 11)) is None
    assert register.lookup("Hans", "Grenze", "grenze.de",
                           today=TODAY)["run"] == "zona40-dropcontact-2026-06-12"


def test_a_reused_campaign_lead_is_not_read_back(tmp_path):
    _write(tmp_path / "laeufe" / "kunde-x" / "20260909-101010" / "leads.json",
           {"leads": [{"first_name": "Jana", "last_name": "Neu",
                       "email": "jana@neu.de", "website": "neu.de",
                       "source": REUSED_SOURCE}]})

    assert load_register(tmp_path).lookup("Jana", "Neu", "neu.de",
                                          today=TODAY) is None


def test_the_current_run_folder_can_be_left_out(project):
    # A run that crashed after paying fetches its own batch again - its
    # own request list must not make it skip the people it paid for.
    current = project / "laeufe" / "leadquellen" / "zona33-dropcontact-2026-08-28"

    register = load_register(project, exclude=[current])

    assert register.lookup("Bernd", "Leer", "leer.de", today=TODAY) is None


def test_split_says_whom_to_ask_and_what_is_already_answered(project):
    register = load_register(project)
    requests = [
        {"first_name": "Anna", "last_name": "Alt", "website": "alt.de"},
        {"first_name": "Bernd", "last_name": "Leer", "website": "leer.de"},
        {"first_name": "Zoe", "last_name": "Neu", "website": "neu.de"},
    ]

    answered, to_ask = register.split(requests, today=TODAY)

    assert to_ask == [2]
    assert answered[0]["email"] == "anna@alt.de"
    assert answered[0]["reused_from"] == "zona33-dropcontact-2026-08-28"
    assert answered[1] is None

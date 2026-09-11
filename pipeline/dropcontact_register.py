"""Every Dropcontact answer we already have - so nobody is paid for twice.

Jira AP-216 (Dafina, 10.09.2026). Across zones 32-39, 19 people were paid
for in more than one zone - 22 payments too many - because each run only
looked at its own zone. Dropcontact bills "pay on success": an address
costs a credit every time it is found, also the second time.

This is not a new database. It reads the files the runs already write:

    zone runs        laeufe/leadquellen/*-dropcontact-*/ergebnisse.json
                     (addresses found) and request-id.json (who was asked,
                     also when nothing was found)
    the fast runner  laeufe/**/zwischenstand.json (addresses paid for)
    campaign runs    laeufe/<client>/<run>/leads.json - only the sources
                     whose address Dropcontact built

For one person - first name, last name, company domain - it answers:

    found before       reuse the address, do not pay again
    asked, no result   do not ask again (costs no credit, but time)
    unknown            ask

An answer counts for 90 days (decision Dafina, 10.09.2026). Older ones are
asked again, so the address is checked once more before anyone writes to
it - the project's rule for every address. When a person was asked more
than once, the latest answer wins: an address Dropcontact no longer
confirms is not reused.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

MAX_AGE_DAYS = 90

# Lead sources whose address Dropcontact built and verified. "apollo" and
# "info@" addresses never went through Dropcontact.
DROPCONTACT_SOURCES = frozenset(("impressum", "dropcontact", "hunter"))

# Source of a lead whose address was taken over from an earlier answer.
# Deliberately NOT one of DROPCONTACT_SOURCES: the register never reads
# such a lead back, so an old check never gets the date of the run that
# reused it - and never outlives its 90 days.
REUSED_SOURCE = "dropcontact_reused"


def reused_note(mail: dict) -> str:
    """The note a reused address carries, so a reader sees its age."""
    return (f"Address reused from {mail['reused_from']} "
            f"({mail['reused_date']}) - not paid for again")

_DATE_DASHED = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_COMPACT = re.compile(r"(\d{4})(\d{2})(\d{2})-\d{4,6}")


def _domain(website) -> str:
    bare = re.sub(r"^https?://", "", str(website or "").strip().lower())
    return re.sub(r"^www\.", "", bare).split("/")[0]


def person_key(first_name, last_name, website) -> tuple:
    """The same person, however the name or the website was written."""
    return (str(first_name or "").strip().casefold(),
            str(last_name or "").strip().casefold(),
            _domain(website))


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _date_in_name(name: str):
    for pattern in (_DATE_DASHED, _DATE_COMPACT):
        match = pattern.search(name)
        if match:
            try:
                return date(*map(int, match.groups()))
            except ValueError:
                pass
    return None


def _date_of(zeit):
    try:
        return datetime.fromisoformat(str(zeit)).date()
    except ValueError:
        return None


def _newer(entry: dict, current: dict) -> bool:
    if entry["date"] != current["date"]:
        return entry["date"] > current["date"]
    # Same day: the result file knows more than the list of requests.
    return bool(entry["email"]) and not current["email"]


class Register:
    def __init__(self):
        self._answers: dict = {}

    def add(self, key: tuple, when, email, run: str,
            qualification=None, felder=None) -> None:
        if not all(key) or when is None:
            return
        entry = {"email": email or None, "run": run, "date": when.isoformat()}
        if email:
            entry["qualification"] = qualification or "nominative@pro"
            entry["felder"] = dict(felder or {})
        current = self._answers.get(key)
        if current is None or _newer(entry, current):
            self._answers[key] = entry

    def lookup(self, first_name, last_name, website, today=None):
        """The latest answer for this person, or None: unknown or too old."""
        entry = self._answers.get(person_key(first_name, last_name, website))
        if entry is None:
            return None
        age = ((today or date.today()) - date.fromisoformat(entry["date"])).days
        if age > MAX_AGE_DAYS:
            return None
        return dict(entry)

    def reuse(self, first_name, last_name, website, today=None) -> tuple:
        """(known, address) for one person.

        The address has the form of a fresh Dropcontact answer plus where
        it came from; it is None when the person was asked before without
        a result. known=False means: ask Dropcontact.
        """
        entry = self.lookup(first_name, last_name, website, today=today)
        if entry is None:
            return False, None
        if not entry["email"]:
            return True, None
        return True, {"email": entry["email"],
                      "qualification": entry["qualification"],
                      "felder": entry["felder"],
                      "reused_from": entry["run"],
                      "reused_date": entry["date"]}

    def split(self, requests: list, today=None) -> tuple:
        """({position: address or None}, [positions to ask]) for a batch."""
        answered, to_ask = {}, []
        for nr, request in enumerate(requests):
            known, mail = self.reuse(request.get("first_name"),
                                     request.get("last_name"),
                                     request.get("website"), today=today)
            if known:
                answered[nr] = mail
            else:
                to_ask.append(nr)
        return answered, to_ask


def load_register(project_dir, exclude=()) -> Register:
    """Read every answer on disk. `exclude`: run folders to leave out -
    the current run, when it fetches its own paid batch again."""
    laeufe = Path(project_dir) / "laeufe"
    skip = {Path(p).resolve() for p in exclude}
    register = Register()
    if not laeufe.exists():
        return register

    for folder in sorted((laeufe / "leadquellen").glob("*-dropcontact-*")):
        if not folder.is_dir() or folder.resolve() in skip:
            continue
        request = _read_json(folder / "request-id.json") or {}
        when = _date_of(request.get("zeit")) or _date_in_name(folder.name)
        for asked in request.get("gesendet") or []:
            register.add(person_key(asked.get("first_name"),
                                    asked.get("last_name"),
                                    asked.get("website")),
                         when, None, folder.name)
        for company in _read_json(folder / "ergebnisse.json") or []:
            # An address this run took over from the register keeps the
            # day and the run of its real check - otherwise every reuse
            # would make an old check young again.
            origin = company.get("wiederverwendet_aus") or {}
            for lead in company.get("leads") or []:
                register.add(person_key(lead.get("first_name"),
                                        lead.get("last_name"),
                                        company.get("website")),
                             _date_of(origin.get("datum")) or when,
                             lead.get("email"),
                             origin.get("lauf") or folder.name,
                             felder=company.get("dropcontact"))

    for cache in sorted(laeufe.glob("**/zwischenstand.json")):
        if cache.parent.resolve() in skip:
            continue
        # The cache keeps no date per address; the file's last save is
        # the day those addresses were paid for, give or take the run.
        when = date.fromtimestamp(cache.stat().st_mtime)
        run = str(cache.parent.relative_to(laeufe))
        for text, mail in ((_read_json(cache) or {}).get("adressen") or {}).items():
            parts = str(text).split("|")
            if len(parts) != 3:
                continue
            mail = mail or {}
            register.add(person_key(*parts), when, mail.get("email"), run,
                         qualification=mail.get("qualification"),
                         felder=mail.get("felder"))

    for leads_file in sorted(laeufe.glob("*/*/leads.json")):
        run_dir = leads_file.parent
        if run_dir.parent.name == "leadquellen" or run_dir.resolve() in skip:
            continue
        data = _read_json(leads_file)
        leads = data.get("leads") if isinstance(data, dict) else data
        when = _date_in_name(run_dir.name)
        for lead in leads or []:
            if lead.get("source") not in DROPCONTACT_SOURCES:
                continue
            register.add(person_key(lead.get("first_name"),
                                    lead.get("last_name"),
                                    lead.get("website")),
                         when, lead.get("email"),
                         f"{run_dir.parent.name}/{run_dir.name}")
    return register

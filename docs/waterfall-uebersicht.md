# Company Master Database & Waterfall Enrichment — Overview

Status: 19 August 2026 (evening build), updated 10 September 2026 (Jira
AP-215 and AP-216). Plain-English companion to
`docs/bauplan-waterfall-master-db-2026-08-19.md` (build plan, Albanian).

## The workflow

```text
Search criteria (step 1+3 of the campaign form: count, region, services)
        ↓
Internal database first (existing company pool - free, nothing is lost)
        ↓
Google Maps  →  Overpass/OSM                      (discovery, region by
        ↓                                          region, or along the
Merge & de-duplicate (domain, else name+postcode;  postal-code list of a
        provenance kept per source)                zone)
        ↓
Zone gate: only a company with a postal code from the zone's list
        belongs to the zone (10 Sep 2026)
        ↓
Automation-service check (website + AI) — BEFORE any paid step
        ↓                    offers_automation_services: yes → stored,
        ↓                    marked, excluded from campaigns, no credits
Decision-maker discovery (website imprint + AI: names, roles;
        priority: Owner/Inhaber → CEO → Managing Director/GF → Founder)
        ↓
Dropcontact register: was this person answered before? (10 Sep 2026)
        ↓        found within 90 days → reuse, not paid again
        ↓        asked without result → not asked again
Personal email building & verification (Dropcontact, only the rest)
        ↓
Master database (companies / company_sources / decision_makers,
        completeness %, campaign_eligible + reason)
        ↓
Campaign eligibility (strict: automation check = no, decision-maker
        known, verified personal email)
        ↓
Campaign form → personalised texts → human approval per email
        ↓
Instantly (campaign created PAUSED — explicit activation only)
        ↓
Replies → internal inbox → CRM
```

## Providers (run `python -m pipeline anbieter` for the live status)

| Provider | Capabilities | Status |
|---|---|---|
| Internal pool | discovery, details | ready, always step 1, free |
| Google Maps (Apify) | discovery, address, phone, website | ready |
| Overpass / OSM | discovery, address, phone, website | ready (free, throttled) |
| Gelbe Seiten (Apify) | discovery, address, phone, website, general email | **removed from the chain** on 4 Sep 2026 — tested on zones 32–39, about 560 new companies and zero contacts. The tool stays built but nothing in the chain asks it. |
| MailCom (bought list) | company addresses, employee counts | imported for zones 33 and 34 (28 Aug 2026) |
| Imprint AI (own) | decision-makers (names + roles only) | ready |
| Dropcontact register (own) | every earlier Dropcontact answer, read from the run files | ready (10 Sep 2026) — free, always asked before Dropcontact |
| Hunter | email discovery + verification | ready (free tier: 50 searches + 100 verifications/month); today only checks info@ addresses |
| Dropcontact | builds + verifies personal emails | ready (paid credits, "pay on success") |
| LinkedIn | decision-makers | **not implemented** — needs access AND a terms-of-service decision |
| Apollo | discovery, decision-makers, emails | **not implemented** — tried in July, abandoned (broken endpoint) |
| Clay | contact enrichment | **not implemented** — no account |
| North Data | discovery, decision-makers, company details | **not implemented** — dropped 29.07.2026 ("no emails, only names"); reconsider for names/roles |
| Prospeo | decision-makers, emails | account died during provider's API rework |

## Key rules built in

- **Nothing is deleted.** New searches only add companies and fill empty
  fields; excluded companies stay stored with the reason.
- **Known vs. new is measured.** Every collection reports how many found
  companies were already in the pool and how many are new, plus what
  every source contributed per area.
- **Automation providers are competitors.** Checked before any paid
  step with a three-way verdict (Phase 2, 20.08.2026): `yes` (offers
  process/AI automation as a service), `no`, `uncertain` (unreadable
  website or ambiguous evidence — NEVER guessed from the company name).
  `yes` → `automation_provider`, `uncertain` → `automation_uncertain`;
  both stay stored, get no credits, no call-list entry and no campaign.
  Industrial automation (PLC/Steuerungs-/Gebäudeautomation) and
  software products that merely contain automation features count as
  `no` — different market, not a competitor. The whole pool carries a
  stored verdict (`daten/automation-klassifikation.json`, CLI
  `automation-check`); campaign runs reuse it instead of paying for a
  second AI call.
- **Eligibility is strict** (per the spec): automation check must have
  run and said `no`, a decision-maker must be known, and a personal
  email must be verified. Anything else carries an honest reason:
  `automation_not_checked`, `no_decision_maker`, `no_personal_email`.
- **Provenance survives.** `company_sources` keeps one row per company
  and source with the raw record and collection time; the master
  database is a regenerable compilation of the run files (delete
  `daten/master.db` any time — the next build recreates it; the files
  stay the source of truth).
- **Cost order.** Free discovery and the AI checks run first; Dropcontact
  credits are spent only on companies that survived qualification.
  A failed source is recorded and the run continues with the others.
- **Nobody is paid for twice** (10 Sep 2026). Before any Dropcontact
  request, every path — the zone tool, the campaign run and the fast
  runner — asks the Dropcontact register. An address found before and not
  older than 90 days is reused and marked with the run and the day it was
  checked; a person asked before without a result is not asked again.
  Older answers are asked again, so every address is checked within 90
  days before sending. Replayed over the zones 32–39, the register would
  have saved 31 payments: 22 people paid for in two zones, and 9 already
  paid for in the PLR 30–31 run or a campaign.
- **Only companies proven in the zone are enriched** (10 Sep 2026). A
  company without a postal code from the zone's list is not sent to
  Dropcontact — it could never enter the zone's list.
- **Cost is measured per run.** AI cost per zone run is written to its
  `kosten.json`. Every Dropcontact balance the provider reports is kept in
  `dropcontact-guthaben-verlauf.jsonl` with its request number, so the cost
  of one batch is the balance at its hand-over minus the balance at the
  next one. Runs before 10 Sep 2026 have no such record and are shown as
  "not recorded" — no number is guessed.
- **The final order of the sources is not decided here.** It is the job
  of the source benchmark (Jira AP-213).

## Commands

```text
python -m pipeline sammeln --deutschland --ziel 100 --dienst "Computer Services"
python -m pipeline anbieter
python -m pipeline master-db
python -m pipeline master-export        # firmen-master.xlsx, one row per
                                        # company, decision-makers A-E
.venv/bin/python werkzeuge/zone-source-report.py            # per zone: sources,
                                        # enrichment funnel, AI cost, credits
.venv/bin/python werkzeuge/zona32-dropcontact.py --zone=36 --nur-zeigen
                                        # whom the zone step would reuse,
                                        # skip or ask - nothing is sent
```

# Company Master Database & Waterfall Enrichment — Overview

Status: 19 August 2026 (evening build). Plain-English companion to
`docs/bauplan-waterfall-master-db-2026-08-19.md` (build plan, Albanian).

## The workflow

```text
Search criteria (step 1+3 of the campaign form: count, region, services)
        ↓
Internal database first (existing company pool - free, nothing is lost)
        ↓
Google Maps  →  Overpass/OSM  →  Gelbe Seiten     (discovery, region by
        ↓                                          region until the
Merge & de-duplicate (domain, else name+postcode;  requested count is
        provenance kept per source)                reached)
        ↓
Automation-service check (website + AI) — BEFORE any paid step
        ↓                    offers_automation_services: yes → stored,
        ↓                    marked, excluded from campaigns, no credits
Decision-maker discovery (website imprint + AI: names, roles;
        priority: Owner/Inhaber → CEO → Managing Director/GF → Founder)
        ↓
Personal email building & verification (Dropcontact; Hunter for info@)
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
| Gelbe Seiten (Apify) | discovery, address, phone, website, general email | ready |
| Imprint AI (own) | decision-makers (names + roles only) | ready |
| Hunter | email discovery + verification | ready (free tier: 50 searches + 100 verifications/month) |
| Dropcontact | builds + verifies personal emails | ready (paid credits) |
| LinkedIn | decision-makers | **not implemented** — needs access AND a terms-of-service decision |
| Apollo | discovery, decision-makers, emails | **not implemented** — tried in July, abandoned (broken endpoint) |
| Clay | contact enrichment | **not implemented** — no account |
| North Data | discovery, decision-makers, company details | **not implemented** — dropped 29.07.2026 ("no emails, only names"); reconsider for names/roles |
| Prospeo | decision-makers, emails | account died during provider's API rework |
| MailCom import | unknown | **optional** — no MailCom data exists on our side (checked 20.08.2026); the "existing data first" role is fully covered by our own master database. If a MailCom export ever shows up, it gets imported as one more source. |

## Key rules built in

- **Nothing is deleted.** New searches only add companies and fill empty
  fields; excluded companies stay stored with the reason.
- **Known vs. new is measured.** Every collection reports how many found
  companies were already in the pool and how many are new, plus what
  every source contributed per area.
- **Automation providers are competitors.** Checked before any paid
  step; `yes`/`uncertain` → stored, `campaign_eligible = false`
  (`automation_provider`), no credits spent, not on the call list.
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

## Commands

```text
python -m pipeline sammeln --deutschland --ziel 100 --dienst "Computer Services"
python -m pipeline anbieter
python -m pipeline master-db
python -m pipeline master-export        # firmen-master.xlsx, one row per
                                        # company, decision-makers A-E
```

# Implementation Audit against Oliver's Requirements

Date: 20 August 2026 · read-only audit, no code changed · source of
truth: the repository at this date (branch `feature/email-compaigns`,
uncommitted work tree included). Test suite at audit time: **1,069
passed**.

---

## A. Executive Summary

A large share of Oliver's workflow already exists — much of it was
built on 19–20 August: target-count Germany-wide discovery with
per-source coverage measurement, decision-maker identification with
Oliver's priority order (Owner → CEO → Managing Director), the
automation-provider exclusion before paid enrichment, a regenerable
master database with provenance and an A–E Excel export.

* **Already implemented:** multi-source discovery (Maps, Gelbe Seiten,
  Overpass) with internal-pool-first reuse, append-only storage,
  dedupe, per-source exclusive-contribution measurement; decision-maker
  discovery via imprint AI with role priority and multi-person storage;
  personal-email building + verification (Dropcontact/Hunter);
  automation exclusion (new campaigns); paused Instantly handover with
  human approval; CRM for responders.
* **Partially implemented:** master database (regenerable read model —
  the campaign wizard does not consult it yet); provenance (per-record,
  not per-field); Oliver's field list (description, employee count,
  county, decision-maker phone/area have no source today); waterfall
  logic (true waterfall in enrichment, breadth-parallel in discovery —
  deliberate, sources barely overlap); automation check (only campaigns
  created by the form; old customer files and the existing pool are
  unchecked).
* **Missing:** **the campaign-eligibility gate.** The live campaign
  path still allows verified `info@` addresses as campaign recipients
  (fallback decided 11.08; 65 of the 277 contacts in the sleeping real
  campaign are info@). Oliver's new rule 3 forbids exactly this.
  The strict rule (named decision-maker + verified personal email +
  automation check = no) exists **only** in the master database's
  `campaign_eligible` flag — nothing in the wizard/approval/handover
  enforces it. Also missing: LinkedIn/Apollo/Clay/North Data (declared
  in the provider registry as not implemented — no fabricated
  integrations), MailCom (no such data exists in the project).
* **Biggest architectural gap:** eligibility enforcement point. The
  wizard consumes run leads directly (`laeufe/<kunde>/<ts>/leads.json`)
  and never asks the master DB whether a company/contact is
  campaign-eligible.

**Documentation discrepancy flag (code wins):**
`docs/waterfall-uebersicht.md` ("Eligibility is strict") and the
workflow image sent to Oliver ("companies that offer automation
services are excluded from the campaign") describe the master-DB flag
and NEW form campaigns. The running campaign path neither blocks
info@ recipients nor re-checks old campaigns. Until the eligibility
gate is built, the documents overstate current behaviour.

---

## B. Requirement Matrix

| Requirement | Status | Current Implementation | Files / Modules | Gap |
|---|---|---|---|---|
| 1a Discovery sources exist | ✅ | Google Maps (area grid), Gelbe Seiten, Overpass/OSM; family search terms | `pipeline/sources/apify_maps.py`, `gelbe_seiten.py`, `overpass.py`, `pipeline/service_categories.py` | — |
| 1b Reuse existing data first | ✅ | Wizard step 3 defaults to pool; collection counts known-vs-new | `web/routen/assistent.py:_firmen_bestand`, `firmen_sammeln._bestand_schluessel` | — |
| 1c Add without deleting | ✅ | Collections append-only; read-time merge fills empty fields only | `_firmen_bestand`/`_firma_ergaenzen`; `master_db._firma_uebernehmen` | — |
| 1d Deduplication | ✅ | Within collection: domain, else name-core+PLZ; across collections: domain/name key; per-campaign email dedupe | `listen_fusion._schluessel`, `grosslauf._namenskern`, `pipeline/dedupe.py` | see §11 weaknesses |
| 1e Coverage per provider measurable | ✅ | raw, knows, EXCLUSIVE contribution per source; per-area log; known-vs-new; end reason | `listen_fusion.fusionieren` (je_quelle, je_quelle_einzigartig, je_quelle_kennt), `firmen_sammeln.sammeln_bis_ziel` | per-run cost not consolidated |
| 2 Decision-maker identification | ✅ | Imprint AI extracts names+roles; priority Owner→CEO→MD/GF→Founder→other; multiple persons stored incl. "ohne_mail"; primary marked | `pipeline/sources/impressum.py`, `pipeline/decision_maker.py`, `sourcing.py`, `schnelllauf.py` | coverage 67/100 with current sources |
| 3 Personal-email-only campaigns | ❌ **critical** | Personal preferred, but verified info@ STILL becomes a lead, passes approval, is handed to Instantly; salutation "zusammen"; with no verifier available info@ is even accepted unverified (backward-compat) | `sourcing.source_leads` info branch (`INFO_OK_STATUS`, `ausgang="info_fallback"`), `kontakte_excel` ("Sammeladresse"), `web/routen/freigabe.py` (no eligibility filter) | eligibility gate missing; strict rule lives only in `master_db._eligibility` |
| 4 Automation exclusion | 🟡 | Website+AI check BEFORE paid steps; yes/uncertain excluded, stored with reason/time, no credits, not on call list; form campaigns enable it | `sourcing._wettbewerber_urteile`, `branchen_filter.ist_wettbewerber`, `config.Kunde.wettbewerber_pruefung`, `assistent._kunde_schreiben` | old customer files default off; existing 4,969-company pool unchecked → master DB shows `automation_not_checked` everywhere |
| 5 Required company fields | 🟡 | see §5 field map below | collections + `master_db.py` | description, employees, county empty (no source); county derivable from PLZ |
| 6 Decision-maker model | 🟡 | multiple per company ✓, role ✓, provenance ✓, status (`mail_geprueft`/`ohne_mail`) ✓, personal vs general email split ✓, LinkedIn field ✓ (rarely filled) | `decision_maker.build_entscheider`, `master_db` table `decision_makers` | phone ❌, area/product ❌ (no source) |
| 7 Provider inventory | ✅ | honest registry with capabilities + configured status; CLI `anbieter` | `pipeline/providers.py`, `pipeline/__main__.py` | LinkedIn/Apollo/Clay/NorthData declared only |
| 8 True waterfall logic | 🟡 | Enrichment: yes (stage 2 only for missed firms; Dropcontact rounds only for open firms; info checks only w/o personal; excluded firms skipped). Discovery: breadth-parallel per area by design (sources barely overlap — 71/20/7% exclusive) | `sourcing.source_leads`, `_impressum_gebuendelt`, `sammeln_bis_ziel` | no per-FIELD "ask next source only for missing field" targeting |
| 9 Master database | 🟡 | regenerable SQLite read model compiled from files: companies / company_sources / decision_makers, completeness %, strict `campaign_eligible` | `pipeline/master_db.py` → `daten/master.db` | not the write path; wizard doesn't consult it |
| 10 CRM | ✅ | separate SQLite `kontakte.db`, ONE table (email PK, name, firma, kampagne, stufe, 2 timestamps), 6 Wholix stages, responders only, duplicates rejected | `web/crm_speicher.py`, `web/crm_zufluss.py` | cannot host master data (by design); no location fields |
| 12 Coverage measurement | ✅ | requested vs unique, per-area, per-source exclusive, known/new, end reason | `sammeln_bis_ziel` bericht | — |
| 13 Campaign eligibility gate | ❌ **critical** | none in the campaign path; handover requires only "all texts approved" | `freigabe.py` (`uebergabe_bereit`) | build gate: personal verified + automation no + DM known |
| 15 Instantly integration | ✅ | campaigns created PAUSED; leads imported with {{anrede}} guard; explicit activate/pause endpoints; no Outlook engine — sender mailboxes live in Instantly (some happen to be Outlook-hosted) | `pipeline/senders/instantly.py` (`create_campaign`, `import_leads_mit_anrede`, `aktiviere_kampagne`), `web/routen/freigabe.py` | — |
| 16 Replies / CRM inflow | ✅ | replies read from Instantly; only conversations with a RECEIVED message create a contact; email PK prevents duplicates | `web/instantly_leser.py`, `web/crm_zufluss.py` | fine for new requirements |
| 17 Provenance | 🟡 | per company+source rows with raw record JSON + collected_at (file mtime); lead source per contact | `master_db` `company_sources` | per-field evidence ❌, source URL ❌, collection timestamps approximated |
| 18 Export | 🟡 | run workbook (Kontakte/Anruf&Brief/Kontrolle, split PLZ/Ort, Rolle) + master export (Oliver's columns + A–E + system fields, 45 cols) | `pipeline/kontakte_excel.py`, `master_db.export_excel` | empty where no source: description, employees, county, DM tel/area |
| 19 Tests | ✅ | 1,069 green; see §19 list | `tests/` (109 files) | gaps: eligibility gate (once built), pool classification |

---

## C. Current End-to-End Workflow (as actually implemented)

```text
Step 1  name, language, TARGET COUNT, sender, seller URL
Step 2  AI drafts USP/ICP from seller site (editable)
Step 3  city/PLZ+radius, services (family chips), pool OR fresh collection
        └─ fresh: background `pipeline sammeln --ziel N [--deutschland]`
           internal-known counted → Maps+GS+OSM per area → fusion/dedupe
           → repeat until target or exhausted (report per source/area)
Step 4  filtered pool table (PLZ|Ort split), cost preview, credits left
        └─ on submit: customer YAML + firm list → background run:
           [wettbewerber_pruefung? → website+AI check → excluded firms
            stored, skipped, no credits]
           → imprint AI (names+roles, Owner→CEO→MD first)
           → Dropcontact batch build+verify (personal)
           → NO personal? → info@ verified (Hunter/Dropcontact)
             → **info@ BECOMES A LEAD** (salutation "zusammen")
           → per-campaign dedupe/blocklist → AI texts + quality check
Step 5  mailbox, daily limit, schedule, signature, PREVIEW/LIVE switch
Step 6  progress + link to approval + Excel download
Approval  read/edit/approve EVERY mail (incl. info@ ones); preview-send
Handover  all approved → Instantly campaign created PAUSED
Activation ONLY on Dafina's explicit word → sending → replies → inbox → CRM
```

## D. Current Data Storage Architecture

| What | Where | Notes |
|---|---|---|
| Campaign drafts | `entwuerfe/<kennung>.json` (+`-firmen.json`) | every wizard step persists |
| Company collections | `laeufe/leadquellen/<sammlung>/firmen.json` + `sammelbericht.json` | append-only, never overwritten; merged at read time |
| Pipeline runs | `laeufe/<kunde-slug>/<ts>/` → `firmen.json` (incl. entscheider, automation fields), `leads.json`, `dedupe.json`, `personalisierung.json`, `status.json`, `zwischenstand.json`, `versand_komplett.json` | crash-safe resume |
| Master DB | `daten/master.db` (SQLite, gitignored) | REGENERABLE compilation of the above |
| CRM | `<daten_dir>/kontakte.db` (SQLite, 1 table) | responders only |
| Credits | `dropcontact-guthaben.json` | last reported balance |
| Instantly (remote) | campaigns, leads, sending stats, warm-up, conversations | read via `web/instantly_leser.py` |

## E. Provider Inventory

| Provider | Current Purpose | Implemented | Used Today | Notes |
|---|---|---|---|---|
| Internal pool | discovery step 1, free | ✅ | ✅ | 4,969 companies; always first |
| Google Maps (Apify) | discovery: name, address, PLZ/Ort, phone, website, categories | ✅ `sources/apify_maps.py` | ✅ | paid per result; async area runs, polling; 71% exclusive contribution |
| Gelbe Seiten (Apify) | discovery + phone + general email | ✅ `sources/gelbe_seiten.py` | ✅ | paid, cheap; nationwide query capable; 20% exclusive |
| Overpass/OSM | discovery (office=it) | ✅ `sources/overpass.py` | ✅ | free, throttled, mirror fallback + retries; 7% exclusive |
| Imprint AI (own) | decision-maker names+roles (+deviating mail domain, LinkedIn if printed) | ✅ `sources/impressum.py` | ✅ | AI cents; Chrome render fallback; NOT a foundation for addresses (project rule) |
| Dropcontact | build + verify personal emails; info@ bulk check | ✅ `sources/dropcontact.py` | ✅ | paid credits; batch with 15-min window + request_id crash recovery |
| Hunter | decision-maker search, email verify | ✅ `sources/hunter.py` | ✅ (free tier) | 50 searches + 100 verifications/month |
| Prospeo | DM + email discovery | ✅ `sources/prospeo.py` | ❌ | account dead since vendor API rework (29.07); measured no better |
| Old hand lists | discovery import | ✅ `listen_import.py` | occasionally | 1% exclusive |
| LinkedIn | DM/contacts | ❌ declared only | ❌ | needs access + ToS decision |
| Apollo | discovery/DM/emails | ❌ declared only | ❌ | tried July, abandoned (broken endpoint) |
| Clay | enrichment | ❌ declared only | ❌ | no account |
| North Data | DM/company details/employees | ❌ declared only | ❌ | dropped 29.07 (no emails); would fill employee-count gap |
| MailCom | unknown | ❌ nothing exists | ❌ | no data on our side (verified 20.08) |

Retry/fallback: Overpass mirrors+retries; Dropcontact batch resume;
imprint dead-host early-exit + browser render; collection continues
when one source fails (errors recorded per area).

## F. Personal Email Logic (critical section)

1. Imprint AI reads owner/CEO names (priority-sorted). Dropcontact
   builds `first.last@domain` and verifies it live → **personal,
   verified** (`source: dropcontact/impressum`). Hunter path may supply
   a person whose email Hunter itself verified.
2. If NO personal address verifies: `info@<domain>` is checked
   (Dropcontact bulk or Hunter); statuses accepted: `valid`,
   `accept_all`, `gueltig`. Failing statuses → company goes to the
   call/letter list (`info_ungueltig`). **Backward-compat hole:** with
   no verifier object available, info@ is accepted UNVERIFIED
   (`pruefstatus is None` branch in `sourcing.source_leads`).
3. The verified info@ **becomes a normal lead** (empty name, salutation
   "zusammen"), gets a personalised text, passes human approval and is
   imported into Instantly. In the real sleeping campaign, 65 of 277
   contacts are info@.
4. Master DB stores general email separately (`email_allgemein`) and
   its `campaign_eligible` requires a personal verified address — but
   no campaign code reads that flag.

**Verdict:** personal emails are preferred and verified-only is
enforced for personal addresses; however generic addresses are still
campaign recipients today. Oliver's rule 3 requires an eligibility
gate; the data to enforce it already exists on every lead
(`source: "info@"` marks generic).

## G. Database Gap Analysis

The file model (collections + run folders) is crash-safe and
append-only but cannot: update a company in place across runs, hold
per-field provenance, hold stable IDs, or answer cross-run questions
directly — that is why `master.db` exists as a compiled read model.
What the current model cannot support without further work: per-field
evidence with source URL and precise collection timestamps (mtime
approximation today), decision-maker phone/area fields (no source),
employee counts (no source), and enforcement — eligibility lives in
the read model that nothing consumes. CRM's single-table design is
deliberately narrow (responders only) and should stay separate from
master data.

## H. UI / Campaign Wizard Gap Analysis

| Step | Exists | Needs (for Oliver's rules) |
|---|---|---|
| 1 | name/language/count/sender/URL/references | unchanged |
| 2 | AI USP/ICP, editable, sender/recipient separated | unchanged |
| 3 | family chips, live pool counter, pool-vs-collect, Germany-wide | source-status panel (which providers will run / not configured) |
| 4 | result table (PLZ/Ort), cost preview, credits | columns: existing/new, DM status, personal-email status, automation status, eligibility + reason; consult master DB |
| 5 | mailbox/limits/schedule/PREVIEW-LIVE | unchanged |
| 6 + approval | per-mail approval, preview-send, Excel | **eligibility gate**: exclude info@ recipients and non-eligible companies from handover (report them instead) |

## I. Priority Gap List

**Critical**
1. Campaign-eligibility gate: personal verified email required —
   info@ leads must stop being campaign recipients (kept as company
   data + call list). Enforce in run (don't build info@ leads for
   campaigns) and/or at handover.
2. Automation classification of the EXISTING pool + old customer
   files (today only new form campaigns check; master DB says
   `automation_not_checked` for all 4,969 companies).
3. Wizard consumes master-DB eligibility (step 4 columns + handover).

**Important**
4. Per-field provenance (field, value, provider, URL, collected_at,
   selected_as_primary) + real collection timestamps.
5. County/Bundesland from PLZ (offline, free); brief description via
   AI (cents) — fills two of Oliver's empty columns.
6. Dedupe hardening: phone/address as secondary keys; legal-form
   variants beyond `_namenskern`; provider record IDs.
7. Consolidated per-run cost/credits tracking.

**Optional**
8. DM phone / area-product via new providers (Apollo/Clay class) —
   only after the source benchmark.
9. UI waterfall progress panel; MailCom import if data ever appears;
   LinkedIn/North Data behind the existing registry.

## J. Recommended Next Implementation Phases (proposal only)

1. **Eligibility rule** — personal-only campaign recipients (run +
   handover gate + tests; info@ stays stored/reported).
2. **Pool classification run** — automation check over existing
   companies (AI cents, no credits), master DB flags become real.
3. **Wizard ↔ master DB** — step-4 columns (existing/new, statuses,
   eligibility) and handover consuming `campaign_eligible`.
4. **Provenance deepening + county/description backfill.**
5. **Source benchmark** — step B (€/contact sample, needs credit okay)
   then step C (trial accounts for the idea sources).
6. **UI waterfall panel.**
7. **Dedupe hardening.**
8. **New providers** via the registry — only those the benchmark
   justifies.

---
*Audit stops here. No code, data, or configuration was changed; no
paid API was called. Awaiting approval before any implementation.*

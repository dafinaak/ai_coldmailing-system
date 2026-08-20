# Bauplan: Waterfall Enrichment + Baza Master e Firmave (Oliver, 19.08.2026)

Urdhri: email-i i Oliverit + specifikimi i zgjeruar (19.08.2026 mbrëma).
Qëllimi afarist: nga "kërkim për një fushatë" → **bazë master e
ripërdorshme firmash** me waterfall zbulimi/pasurimi, ruajtje të
provenancës, përjashtim të ofruesve të automatizimit, dhe eksport me
vendimmarrës A–E.

## Faza 1 — Analiza (gjendja reale, verifikuar 19.08.2026)

- **Ruajtja e firmave**: skedarë JSON pas çdo mbledhjeje
  (`laeufe/leadquellen/<mbledhje>/firmen.json`), të pandryshueshëm;
  bashkimi bëhet në LEXIM (`web/routen/assistent._firmen_bestand`):
  plotëso-fushat-bosh, kurrë mbishkrim — pra "7 ekzistuese + 3 të reja"
  funksionon QË SOT në nivel firme. Mungon: ID e qëndrueshme, vula
  kohore, provenanca për fushë, gjendje pasurimi.
- **Zbulimi**: Maps (Apify), Gelbe Seiten (Apify), OpenStreetMap —
  paralelisht (jo waterfall i vërtetë, po fusioni i bashkon); nga sot
  edhe deri-në-cak + mbarë-Gjermania. "Internal first" ekziston si
  parazgjedhje e formularit (bestand para mbledhjes së re).
- **Dublikatat**: `listen_fusion` (domain, ndryshe emër-bërthamë+PLZ) +
  bestand-merge në lexim + `dedupe.py` për email/fushata. Variantet
  "GmbH" vs "GmbH & Co. KG": `_namenskern` i grosslauf i heq format
  ligjore — mbulohet pjesërisht.
- **Vendimmarrësit**: Impressum-AI me rol + prioritet + `entscheider`/
  `entscheider_primaer` në firmen.json (ndërtuar sot paradite);
  shumë persona për firmë ruhen; tel/fusha-produkti mungojnë.
- **Email**: waterfall real ekziston (Impressum→Dropcontact të ndërtuar
  e të verifikuar live; Hunter zbulim+verifikim; info@ i verifikuar si
  rezervë; personal > info@ me dizajn; pa verifikim s'del asgjë).
  Gjendjet janë de-fakto (source/status fusha), jo makinë e emërtuar.
- **Përjashtimi i automatizimit**: `branchen_filter.ist_wettbewerber`
  EKZISTON (vendimi i Oliverit 30.07) po s'është i lidhur në rrjedhën e
  formularit — përdoret vetëm në flukset paket/grosslauf me dorë.
- **Ofruesit**: të implementuar Maps/GS/OSM/Impressum/Dropcontact/
  Hunter(+Prospeo i vdekur). LinkedIn/Apollo/Clay/North Data: JO;
  North Data u hoq me vendim 29.07 ("s'ka email, vetëm emra") —
  rivendoset nga Oliveri nëse duhet për emra/rolet.
- **"MailCom"**: NUK ekziston askund në projekt — pyetje e hapur për
  Oliverin/Dafinën (çfarë është, ku janë të dhënat, si importohen).
- **CRM**: SQLite më vete (vetëm ata që përgjigjen); pa vendndodhje.
- **Instantly**: i paprekur; dorëzimi PAUSED + aktivizim vetëm me fjalë
  të Dafinës — mbetet ashtu.

## Faza 2 — Plani

Parim: skedarët e mbledhjeve/lëshimeve MBETEN burimi i së vërtetës
(të provuar, crash-safe, 1.052 teste); sipër tyre ndërtohet një **bazë
master SQLite E RIGJENERUESHME** (`daten/master.db`) si model leximi
për pyetje/raporte/eksport. Kështu asgjë ekzistuese s'prishet dhe
migrimi është pa rrezik (fshije → rindërtohet).

### Inkrementi 1 (ZBATOHET TASH, 19.08.2026)

1. **Prioriteti i ri i roleve** (spec §6): Inhaber/Owner → CEO →
   Geschäftsführer/Managing Director → Gründer → drejtues tjetër.
   (Ndryshim nga mëngjesi, ku CEO/GF ishin të parët — fiton urdhri i ri.)
2. **Përjashtimi i automatizimit në rrjedhën e fushatës**: para çdo
   pasurimi me pagesë, `ist_wettbewerber` (webseite+KI) mbi firmat e
   lëshimit; fushat: offers_automation_services (yes/no/uncertain/
   not_checked), automation_check_reason/source/checked_at,
   campaign_eligible + campaign_ineligibility_reason
   ("automation_provider"). Firma e përjashtuar: MBETET e ruajtur,
   S'shpenzon asnjë kredit, s'del në Kontakte as në Anruf&Brief.
   Ndizet me `wettbewerber_pruefung: true` në kunden-file — formulari e
   vendos vetë për fushatat e reja; dosjet e vjetra të paprekura.
3. **Regjistri i ofruesve** (`pipeline/providers.py`): çdo ofrues me
   aftësi + statusin konfiguruar/pa-kredenciale/i-hequr; urdhri
   `python -m pipeline anbieter` e tregon waterfall-in real — pa
   integrime të shpikura.
4. **Llogaritja e-njohur/e-re** te mbledhja: bericht merr
   `vorher_bekannt` / `neu` kundrejt bestand-it (shembulli 7+3 i
   specifikimit, i matshëm).
5. **Baza master + eksporti A–E** (`pipeline/master_db.py`): tabelat
   companies / company_sources / decision_makers, ndërtuar nga bestand
   + lëshimet (entscheider, leads, ausgang); plotësia për firmë;
   eksporti Excel me kolonat e Oliverit (burimi, sektori, firma,
   përshkrimi, fjalët kyçe, punonjësit, CEO/Owner, rruga, qyteti, PLZ,
   landi, shteti, tel, email i përgj., webseite + blloqet A–E + fushat
   e sistemit). Fushat pa burim real (punonjësit, landi, tel i
   personit) mbeten bosh — pa shpikje. CLI: `master-db`, `master-export`.
6. Teste për të gjitha (lista §24 e specifikimit ku prek inkrementi) +
   suita e plotë.

### Inkrementet e ardhshme (presin vendim/kredenciale)

- **I2 — MailCom**: import i të dhënave ekzistuese si burim i parë —
  BLLOKUAR nga pyetja "çka është MailCom, ku janë të dhënat".
- **I3 — LinkedIn/Apollo/Clay/North Data**: adapterët realë — presin
  kredenciale + vendim (North Data u hoq me vendim; Apollo dështoi më
  parë; LinkedIn ka çështje ToS që duhen peshuar).
- **I4 — UI**: paneli i waterfall-it në formular (statuset për burim,
  ekzistues/i ri, plotësia, eligibility) — pas I1, mbi master.db.
- **I5 — Makina e gjendjeve të email-it** e emërtuar (unknown…rejected)
  mbi fushat ekzistuese; dhe field_evidence e plotë për fushë nëse
  provenanca e company_sources s'mjafton.
- **I6 — Migrim i thellë** (nëse vendoset): master.db bëhet burim i së
  vërtetës me shkrim direkt; sot ndalohemi te modeli i leximit me
  vetëdije — më i sigurt.

## Rreziqet / pyetje të hapura

- MailCom i panjohur (bllokon I2). LinkedIn ToS. North Data kundër
  vendimit të vjetër — e vendos Oliveri. Kostoja e kontrollit të
  automatizimit: 1 thirrje KI/firmë (cent) — kursen kredite Dropcontact.

## Ecuria

- [x] I1.1 prioriteti i ri i roleve (Inhaber→CEO→GF/MD→Gründer→tjetër)
- [x] I1.2 përjashtimi i automatizimit në rrjedhë (para çdo shpenzimi;
      formulari e ndez vetë; firmat mbeten të ruajtura)
- [x] I1.3 regjistri i ofruesve + CLI `anbieter` (statuse të sinqerta)
- [x] I1.4 e-njohur/e-re në bericht (+log "Davon schon im Bestand …")
- [x] I1.5 master.db + eksporti A–E (mbi të dhënat reale: 4.969 firma,
      5.713 dëshmi burimesh, 99 vendimmarrës; eksporti 4.970×45)
- [x] I1.6 suita e plotë e gjelbër — 1.068 teste (19.08.2026 mbrëma);
      dokumentimi: docs/waterfall-uebersicht.md

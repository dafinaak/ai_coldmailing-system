# Plan: AP-216 — waterfall pa pagesa të dyfishta

Data: 10.09.2026. Vendimi i Dafinës: opsioni A. Ky plan pret miratimin
e saj para se të ndërtohet diçka.

## Pse

Waterfall-i punon, po kontrolli "a e kemi tashmë?" e sheh vetëm zonën ose
vrapimin e tanishëm. Mbi zonat 32–39, **19 persona u paguan në më shumë se
një zonë — 22 pagesa të tepërta** (numëruar më 10.09.2026 nga
`ergebnisse.json` e zonave). Rruga e fushatës nuk i sheh fare vrapimet e
mëparshme. Kreditet e Dropcontact-it për vrapim nuk ruhen askund, dhe te
zonat nuk ka raport për kontributin e hapave të pasurimit.

## Hapat — secili me provën e vet

1. **Regjistri i përgjigjeve të Dropcontact-it** (`pipeline/dropcontact_register.py`,
   modul i ri). Lexon çdo përgjigje që e kemi marrë tashmë, nga dosjet që
   i shkruajmë sot — nuk krijon bazë të re:
   - zonat: `laeufe/leadquellen/*-dropcontact-*/ergebnisse.json` (email-et e
     gjetura) dhe `request-id.json` (kush u pyet, edhe pa rezultat),
   - vrapimi i madh: `zwischenstand.json` (adresat e paguara),
   - fushatat: `laeufe/<klienti>/<vrapimi>/leads.json`, vetëm burimet që
     kalojnë nga Dropcontact-i (`impressum`, `hunter_dropcontact`).

   Çelësi: emri + mbiemri + domain-i, si sot te zonat.
   **Prova:** teste me dosje prove; mbi të dhënat e vërteta — sa nga 22
   pagesat e dyfishta do t'i kishte kapur regjistri (pritja: të 22-at).

2. **Vegla e zonave e pyet regjistrin para Dropcontact-it**
   (`werkzeuge/zona32-dropcontact.py`):
   - email i gjetur më parë, jo më i vjetër se afati (shih pyetjen 1) →
     merret pa pagesë dhe shkruhet te rezultati i zonës me shënimin
     "ripërdorur nga <vrapimi>, <data>", që lista përfundimtare ta gjejë;
   - i pyetur më parë pa rezultat → nuk pyetet prapë (si sot, po tash nga
     të gjitha zonat);
   - të tjerët → pyeten.

   Mënyrë e re `--nur-zeigen`: tregon kë do ta ripërdorte, kë do ta
   kapërcente dhe kë do ta pyeste — pa dorëzuar asgjë.
   **Prova:** `--nur-zeigen` mbi një zonë të vërtetë, 0 kredite.

3. **Rruga e fushatës e pyet të njëjtin regjistër**, në të tri vendet ku
   paguhet Dropcontact-i: pyetja në grup (`_batch_mit_wiederaufnahme` te
   `pipeline/sourcing.py`), pyetja një nga një (`email_bauen` te
   `sourcing.py`) dhe motori i shpejtë (`pipeline/schnelllauf.py`).
   **Prova:** teste me Dropcontact të rremë — personi i njohur nuk shkon në
   kërkesë, dhe email-i i tij del prapë në rezultat.

4. **Kreditet për çdo vrapim.** Dropcontact-i e kthen gjendjen e krediteve
   (`credits_left`) falas me çdo dorëzim. Burimi e mban, vegla e zonave e
   shkruan te `request-id.json`, fushata te dosja e vrapimit, dhe çdo
   gjendje shtohet te një histori që vetëm rritet
   (`daten/dropcontact-guthaben-verlauf.jsonl`). Kostoja e një vrapimi =
   gjendja te dorëzimi i tij minus gjendja te dorëzimi i radhës.
   **Prova:** teste; vrapimet e vjetra dalin "e paregjistruar" — numrat nuk
   shpiken.

5. **Raporti i pasurimit për çdo zonë**, në të njëjtën veglë si raporti i
   burimeve (`werkzeuge/zone-source-report.py`): firma në zonë → të
   pranueshme (profili IT + automatizimi "no") → me emër nga impressum-i
   → të pyetura te Dropcontact-i → me email → të ripërdorura falas; kostoja
   e AI-së (nga `kosten.json`), kreditet (kur janë regjistruar) dhe kostoja
   për kontakt.
   **Prova:** teste + lëshim mbi zonat 32–39.

6. **Dokumenti `docs/waterfall-uebersicht.md` ndreqet:** pa Gelbe Seiten, me
   MailCom-in, me regjistrin dhe matjen e kostove.
   **Prova:** lexim nga Dafina.

7. **Kontrolli i plotë dhe Jira.** Të gjitha testet; AP-216 merr
   përshkrimin e ri me provën dhe kalon në "Done". Rendi përfundimtar i
   burimeve mbetet te AP-213.
   **Prova:** dalja e testeve dhe detyra e lexuar prapë nga Jira.

## Çka nuk bëhet

- Rendi i burimeve nuk ndryshon — këtë e vendos benchmark-u (AP-213).
- Dropcontact-i nuk pyetet në asnjë hap të ndërtimit apo të provës:
  **0 kredite**.
- Kostoja e Apify-së (mbledhja e firmave) nuk hyn këtu; kjo detyrë është
  për pasurimin.
- Rezultatet e vjetra nuk ndryshohen — regjistri vetëm i lexon.

## Rreziqe dhe pyetje të hapura

1. **Sa i vjetër guxon të jetë një email që e ripërdorim?** Propozimi: 90
   ditë. Më i vjetër → pyetet prapë (kushton një kredit, po kontrollohet
   sërish). Rregulli i projektit: çdo email kontrollohet para dërgimit.
2. **Personat e pyetur më parë pa rezultat:** propozimi — as ata nuk pyeten
   prapë brenda 90 ditëve. Dropcontact-i nuk e paguan pyetjen pa rezultat,
   pra kjo kursen kohë, jo para.
3. **Emrat:** Dropcontact-i ndonjëherë e ndërron emrin me mbiemrin. Çelësi
   merr emrin që e dërguam ne; te vrapimet e vjetra pa listën e dërgimit
   kemi vetëm emrin që u kthye — disa raste mund të mos njihen dhe
   paguhen edhe një herë, si sot. Nuk bëhet më keq se sot.
4. **Kreditet:** më 03.09 Dropcontact-i mori 20 kredite për 7 email. Pra
   numri i email-eve nuk është kosto e saktë — prandaj matet me gjendjen
   para dhe pas.
5. **Rruga e fushatës** është ajo që e përdor formulari. Ndryshimi aty
   mbrohet me testet ekzistuese (`test_sourcing*.py`, `test_schnelllauf*.py`,
   `test_dropcontact*.py`) dhe me teste të reja.

## Gjendja

- [x] 1 Regjistri — 8 teste; mbi historinë e vërtetë do të kishte kursyer
  31 pagesa (22 mes zonave + 9 të paguara tashmë te PLR 30-31/fushatat)
- [x] 2 Vegla e zonave — `--nur-zeigen` mbi 32–39, pa çelës dhe pa shkruar
  asgjë: 7 persona falas nga vrapime të tjera, 15 të pyetur pa rezultat
  nuk pyeten prapë. Shtuar edhe porta e zonës (pa kod postar nga lista →
  nuk paguhet). 176 "për t'u pyetur" janë kryesisht të pyetur para
  03.09 pa listë emrash — pyetja pa rezultat nuk kushton kredit.
- [x] 3 Rruga e fushatës — grupi, një nga një dhe motori i shpejtë; 5 teste
  të reja + 2 për datën (email-i i ripërdorur e mban datën e kontrollit të
  vërtetë, nuk "rinohet"); 324 teste të komandave/fushatës jeshile
- [x] 4 Kreditet për vrapim — historia `dropcontact-guthaben-verlauf.jsonl`
  me `request_id`; kostoja = gjendja te kërkesa minus gjendja te kërkesa e
  radhës (e hapur kur s'ka të radhës, e hapur kur u blenë kredite në mes);
  6 teste; vegla e zonave e shkruan gjendjen te `request-id.json`
- [x] 5 Raporti i pasurimit — 3 teste; mbi 32–39: 5.121 firma → 678 të
  pranueshme → 502 me emër → 913 pyetje → 404 email të paguara (382 persona
  unikë + 22 të dyfishta), AI $5.02; kreditet "not recorded" për 18 vrapimet
  e vjetra — nuk shpiken
- [x] 6 Dokumenti — `docs/waterfall-uebersicht.md` i përditësuar
- [x] 7 Testet — 1.482 jeshile, 90 të kaluara (Postgres); pa skedarë të
  mbetur, skedari i vërtetë i krediteve i paprekur. Shtuar edhe
  `grosslauf` (rruga e katërt, e harruar te plani). Jira AP-216: përshkrimi
  i ri me provën, "Done" (10.09.2026, i lexuar prapë nga Jira).

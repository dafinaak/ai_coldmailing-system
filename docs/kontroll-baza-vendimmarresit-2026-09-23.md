# Kontrolli i bazës për vendimmarrësit (Jira AP-210)

Data: 23.09.2026. Vetëm lexim — asnjë strukturë nuk u ndryshua, asnjë
rresht nuk u prek. Numrat janë nga `daten/master.db` si rri sot
(e ndërtuar më 07.09.2026: 10.183 firma, 933 vendimmarrës).

Pse ky kontroll: para se të ndryshohet struktura e të dhënave, duhet të
dihet çka ka tashmë baza, që të mos prishet diçka që punon dhe të mos
ndërtohet dy herë e njëjta gjë. Mbi këtë mbështeten AP-211 (të dhënat e
plota të vendimmarrësit), AP-212 (burimi për çdo fushë) dhe pjesa e
mbetur e AP-221.

## 1. Cilat fusha të vendimmarrësit ekzistojnë

Te `master.db`, tabela `decision_makers` — 14 kolona:

| Fusha | Çka mban | E mbushur |
|---|---|---|
| name, vorname, nachname | emri i personit | 933 (100%) |
| rolle | pozita, si shkruan te impressum-i | 781 (84%) |
| bereich | fusha (drejtim, IT, shitje ...), nxjerrë nga pozita | 757 (81%) |
| email | email-i personal | 331 (35%) |
| email_art | lloji i adresës — sot vetëm "persoenlich" | 331 |
| telefon | një numër i vetëm | 699 (75%) |
| linkedin | profili i personit | 2 (0%) |
| quelle | burimi i personit — 931 "impressum" | 933 (100%) |
| status | "mail_geprueft" kur email-i është kontrolluar | 331 (35%) |
| created_at | koha e ndërtimit të bazës, jo e kontrollit | 933 |

Te Postgres-i (`kern.entscheider`) janë pikërisht të njëjtat fusha, plus
`firma_uid` dhe `synced_at`.

Te lista e Oliverit (pamja `datawarehouse` dhe eksporti Excel) çdo person
del me pesë fusha: Bereich, Name, Position, Tel, E-Mail.

## 2. Email personal, numër direkt, celular

- **Email personal:** fusha ekziston dhe punon. E kanë 331 nga 933
  persona (35%), të gjithë me shenjën "i kontrolluar".
  **Po 154 email të paguara nuk janë fare në bazë:** të zonave 35–39
  (137) dhe disa të tjera. Dropcontact-i i gjeti dhe u paguan, po hapi
  që i shkruan prapa te dosjet e vrapimit u bë vetëm për zonat 32–34.
- **Numër direkt:** nuk ka fushë të vet. Ka një kolonë të vetme
  `telefon`, që zakonisht mban numrin e impressum-it, pra centralën e
  firmës. Të paktën 43 persona e kanë saktësisht numrin e firmës si
  "numrin e tyre". Dropcontact-i ka kthyer një numër personi te 285
  rreshta të rezultateve të zonave — as ata nuk janë në bazë.
- **Celular:** nuk ka as fushë, as burim. Dropcontact-i nuk na ka kthyer
  celularë; Apollo dhe LinkedIn nuk janë të lidhur. Pa një burim të ri,
  kjo fushë do të mbetej bosh.

## 3. Si ruhet sot burimi dhe prejardhja

- **Për firmën:** tabela `company_sources`, 11.782 rreshta. Çdo rresht
  mban burimin (`provider`), vrapimin nga erdhi (`herkunft`), kohën
  (`collected_at`) dhe rreshtin e papërpunuar ashtu si erdhi. Kjo është
  e fortë dhe nuk ka nevojë të ndërtohet nga e para.
- **Për personin:** vetëm një `quelle` për tërë personin (931 nga 933
  thonë "impressum") dhe një `status`. **Nuk ka burim për çdo fushë dhe
  nuk ka datë kontrolli.** Pra sot nuk mund të thuhet "email-i erdhi nga
  Dropcontact-i më 28.08, kurse pozita nga impressum-i më 25.08".
- Kjo informatë **ekziston** te listat Excel të zonave, që kanë kolonat
  "Quelle - Firma / Person / Position / E-Mail / Telefon". Pra puna e
  AP-212 është ta çojë atë që tashmë e shkruajmë në Excel edhe brenda
  bazës — jo ta shpikë nga e para.

## 4. A lejohen disa vendimmarrës për një firmë

Po, dhe përdoret: 933 persona për 726 firma.

| Persona për firmë | Firma |
|---|---|
| 1 | 589 |
| 2 | 99 |
| 3 | 23 |
| 4 | 8 |
| 5 | 3 |
| 6 | 1 |
| 8 | 3 |

Eksporti dhe pamja e Oliverit tregojnë pesë (A–E). Katër firma kanë më
shumë se pesë; te eksporti ata shkojnë te kolona "Weitere Entscheider",
kurse te pamja e Oliverit nuk shfaqen fare — mbeten vetëm te tabela.

## 5. Si janë ndërtuar ndërfaqja dhe eksporti

**Ndërfaqja** tregon shumë pak për vendimmarrësit:

- faqja `/kontakte` — listë vetëm për lexim e të gjithë kontakteve të
  gjetur ndonjëherë, me emër, firmë, email, klient, fushatë dhe herën e
  fundit të kontaktit. Ndërtohet nga dosjet e vrapimeve, jo nga
  `master.db`; pa pozitë, pa telefon, pa burim;
- pamja e miratimit tregon marrësin për çdo email;
- hapi 4 i formularit tregon vetëm firma (emër, PLZ, qytet, largësi,
  faqe, telefon) — asnjë kolonë për personin;
- gjatë një vrapimi shfaqet vetëm numëruesi "sa firma me vendimmarrës
  personal".

**Eksporti** `firmen-master.xlsx`: një rresht për firmë — blloku i
firmës, pastaj A–E me nga pesë fusha, pastaj "Weitere Entscheider",
blloku i historikut të kontaktimit dhe kolonat e sistemit
(automatizimi, kampanjefähig). Listat e zonave
(`IT-Liste-Emails-Zona…`) janë format tjetër: një rresht për kontakt,
me burimin për çdo fushë.

## Çka duhet ditur para se të ndryshohet struktura

1. **154 email të paguara nuk janë në bazë** (zonat 35–39 e disa të
   tjera). Kjo nuk është punë strukture, është një hap që mungon: baza
   duhet t'i lexojë vetë rezultatet e Dropcontact-it të zonave.
   **U rregullua po më 23.09.2026:** ndërtimi i bazës i lexon vetë
   (`_zonen_dropcontact_leads`). Pas rindërtimit: email 331 → 485,
   telefona 699 → 737, LinkedIn 2 → 146; asnjë email i humbur dhe asnjë
   i mbishkruar.
2. **Lista e vendimmarrësve zëvendësohet nga vrapimi i ri.** Kur një
   firmë del në dy vrapime, lista e re e zëvendëson të vjetrën të tërë
   ([master_db.py:143](../pipeline/master_db.py#L143)). Një email ose
   telefon i gjetur më herët mund të humbasë pa u vënë re. Rregulli
   "vlerat ekzistuese nuk mbishkruhen" sot vlen për firmat, jo për
   personat.
3. **Telefoni i firmës dhe i personit nuk janë vërtet të ndarë** në
   përmbajtje: 43 persona mbajnë centralën e firmës.
4. **Celulari nuk ka burim sot.** Nëse fusha shtohet, do të mbetet bosh
   derisa benchmark-u (AP-213) të gjejë një ofrues.
5. **Prejardhja për çdo fushë nuk duhet shpikur** — merret nga ajo që
   tashmë shkruhet te listat e zonave.

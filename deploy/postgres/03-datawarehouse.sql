-- Die Ansicht, die Oliver liest (Phase 4, 08.09.2026).
--
--     SELECT * FROM datawarehouse;
--
-- Sie liegt in public, damit genau dieser Satz genuegt - ohne Schema
-- davor. 46 Spalten in seiner Reihenfolge, keine Zutaten von uns: kein
-- synced_at, kein completeness, kein "Weitere Entscheider".
--
-- Die 46 ist BESTAETIGT: Olivers eigene Feldliste (Mail "AW:
-- DataWarehouse - Datenbank-Felder") hat genau 46 Eintraege, und jeder
-- davon hat hier seine Spalte - 16 Firmenfelder + 25 fuer A-E +
-- Rausgegeben + drei Kontakte + Opt-Out.
--
-- Bei den NAMEN wurden Olivers Bezeichnungen ueberall dort uebernommen,
-- wo der Unterschied ein echter ist (Dafina, 08./09.09.2026):
--     Datenquelle (woher, wann) -> Daten-Ursprung (woher/von wem, wann)
--     Sektor              -> Branche
--     Auswahl-Stichworte  -> Selektions-Keywords
--     Webseite            -> www
--     A-E) Bereich        -> A-E) Entscheider-Bereich (fuer welches Produkt)
--     A-E) Rolle          -> A-E) Entscheider-Position
--
-- Reine Schreibweisen bleiben, wie sie in der Excel-Datei seit August
-- stehen: Straße (nicht Strasse), Kurzbeschreibung, Mitarbeiterzahl,
-- E-Mail (allgemein). Ebenso die kurzen Ueberschriften fuer die drei
-- Kontakt-Spalten - Olivers lange Klammern dort beschreiben den INHALT
-- des Feldes, sie sind keine Spaltennamen.
--
-- Dass im A-E-Block "Entscheider-Bereich" und "Entscheider-Position"
-- das Praefix tragen, "Name", "Tel" und "E-Mail" aber nicht, ist eine
-- bewusste Entscheidung von Dafina - kein Versehen. Nicht "der Symmetrie
-- wegen" angleichen.
--
-- Offen ist nur noch, ob Oliver mit den beibehaltenen Namen einverstanden
-- ist. Kommt eine Korrektur, wird hier und in
-- tests/postgres/test_datawarehouse.py geaendert - nie stillschweigend.
--
-- Grundregel: nichts erfinden. Fehlt die Quelle, steht NULL da. Kein
-- COALESCE auf '', kein '?', kein 'unbekannt' - eine leere Zelle ist
-- eine ehrliche Auskunft, eine erfundene ist es nicht.
--
-- Nur lesend. Die Ansicht fasst nichts an, am wenigsten die Historie.

BEGIN;

CREATE VIEW public.datawarehouse AS

-- Herkunft je Firma, wie in der Excel-Liste: bis zu vier Belege, danach
-- ein Auslassungszeichen, damit niemand die Aufzaehlung fuer vollstaendig
-- haelt.
WITH quellen_nummeriert AS (
    SELECT firma_uid,
           ROW_NUMBER() OVER (PARTITION BY firma_uid ORDER BY id) AS nr,
           COUNT(*)     OVER (PARTITION BY firma_uid)             AS gesamt,
           NULLIF(concat_ws(' ',
               NULLIF(provider, ''),
               NULLIF('(' || concat_ws(', ', NULLIF(herkunft, ''),
                                             NULLIF(collected_at, '')) || ')',
                      '()')), '') AS beleg
    FROM kern.firma_quelle
),
quellen AS (
    SELECT firma_uid,
           NULLIF(string_agg(beleg, '; ' ORDER BY nr)
                  || CASE WHEN MAX(gesamt) > 4 THEN ' …' ELSE '' END,
                  '') AS text
    FROM quellen_nummeriert
    WHERE nr <= 4
    GROUP BY firma_uid
),

-- A-E: die ersten fuenf Personen je Firma. Die sechste und alle weiteren
-- bleiben in kern.entscheider stehen - sie werden hier nur nicht gezeigt.
-- Die Reihenfolge ist die, in der der Sync sie schreibt (nach Rang
-- sortiert), deshalb ORDER BY id.
entscheider_nummeriert AS (
    SELECT firma_uid, bereich, name, rolle, telefon, email,
           ROW_NUMBER() OVER (PARTITION BY firma_uid ORDER BY id) AS nr
    FROM kern.entscheider
),
ae AS (
    SELECT firma_uid,
        MAX(bereich) FILTER (WHERE nr = 1) AS a_bereich,
        MAX(name)    FILTER (WHERE nr = 1) AS a_name,
        MAX(rolle)   FILTER (WHERE nr = 1) AS a_rolle,
        MAX(telefon) FILTER (WHERE nr = 1) AS a_tel,
        MAX(email)   FILTER (WHERE nr = 1) AS a_mail,
        MAX(bereich) FILTER (WHERE nr = 2) AS b_bereich,
        MAX(name)    FILTER (WHERE nr = 2) AS b_name,
        MAX(rolle)   FILTER (WHERE nr = 2) AS b_rolle,
        MAX(telefon) FILTER (WHERE nr = 2) AS b_tel,
        MAX(email)   FILTER (WHERE nr = 2) AS b_mail,
        MAX(bereich) FILTER (WHERE nr = 3) AS c_bereich,
        MAX(name)    FILTER (WHERE nr = 3) AS c_name,
        MAX(rolle)   FILTER (WHERE nr = 3) AS c_rolle,
        MAX(telefon) FILTER (WHERE nr = 3) AS c_tel,
        MAX(email)   FILTER (WHERE nr = 3) AS c_mail,
        MAX(bereich) FILTER (WHERE nr = 4) AS d_bereich,
        MAX(name)    FILTER (WHERE nr = 4) AS d_name,
        MAX(rolle)   FILTER (WHERE nr = 4) AS d_rolle,
        MAX(telefon) FILTER (WHERE nr = 4) AS d_tel,
        MAX(email)   FILTER (WHERE nr = 4) AS d_mail,
        MAX(bereich) FILTER (WHERE nr = 5) AS e_bereich,
        MAX(name)    FILTER (WHERE nr = 5) AS e_name,
        MAX(rolle)   FILTER (WHERE nr = 5) AS e_rolle,
        MAX(telefon) FILTER (WHERE nr = 5) AS e_tel,
        MAX(email)   FILTER (WHERE nr = 5) AS e_mail
    FROM entscheider_nummeriert
    WHERE nr <= 5
    GROUP BY firma_uid
),

uebergaben AS (
    SELECT firma_uid,
           NULLIF(string_agg(
               concat_ws(', ', NULLIF(name, ''), NULLIF(art_der_person, ''),
                         to_char(datum, 'YYYY-MM-DD')),
               '; ' ORDER BY datum, id), '') AS text
    FROM historie.uebergabe
    WHERE firma_uid IS NOT NULL
    GROUP BY firma_uid
),

-- Die Ablage kennt keine Grenze 1-3 (Phase 3), die Ansicht holt drei
-- heraus. Mehrere Personen koennen dieselbe Nummer haben; dann stehen
-- sie mit "; " nebeneinander, statt dass eine davon still verschwindet.
kontakte_text AS (
    SELECT firma_uid, nummer, id,
           concat_ws(', ', NULLIF(produkt, ''), NULLIF(durch_wen, ''),
                     NULLIF(weg, ''), NULLIF(resultat, ''),
                     to_char(datum, 'YYYY-MM-DD'),
                     NULLIF(absender_email, '')) AS text
    FROM historie.kontakt
    WHERE firma_uid IS NOT NULL AND nummer IN (1, 2, 3)
),
kontakte AS (
    SELECT firma_uid,
        NULLIF(string_agg(text, '; ' ORDER BY id)
               FILTER (WHERE nummer = 1), '') AS k1,
        NULLIF(string_agg(text, '; ' ORDER BY id)
               FILTER (WHERE nummer = 2), '') AS k2,
        NULLIF(string_agg(text, '; ' ORDER BY id)
               FILTER (WHERE nummer = 3), '') AS k3
    FROM kontakte_text
    GROUP BY firma_uid
),

-- Widersprueche. Zwei Wege hierhin, und der zweite ist der wichtige:
--
--   1. o.firma_uid = f.firma_uid          - der normale Fall
--   2. Domain der E-Mail = kennung        - fuer die Zeilen, die mit
--      Absicht firma_uid = NULL haben (Phase 3, "nur E-Mail"). Ohne
--      diesen Weg saehe Oliver eine Firma als anschreibbar, obwohl dort
--      jemand nein gesagt hat.
--
-- btrim beim Vergleich: eine kennung wie 'eq24pay.de ' gibt es wirklich.
-- Das ist KEIN Aufweichen der Identitaetsregel - hier wird nichts
-- zusammengelegt und keine uid vergeben, hier wird nur angezeigt. Und
-- beim Anzeigen ist die vorsichtige Richtung, einen Widerspruch eher zu
-- finden als zu uebersehen.
opt_outs AS (
    SELECT f.firma_uid,
           NULLIF(string_agg(DISTINCT
               concat_ws(', ', to_char(o.datum, 'YYYY-MM-DD'),
                         NULLIF(o.weg, '')), '; '), '') AS text
    FROM kern.firma f
    JOIN historie.opt_out o
      ON o.firma_uid = f.firma_uid
         OR (o.firma_uid IS NULL
             AND NULLIF(split_part(lower(o.email), '@', 2), '')
                 = NULLIF(btrim(lower(f.kennung)), ''))
    GROUP BY f.firma_uid
)

SELECT
    f.firma_uid                     AS "ID",
    q.text                          AS "Daten-Ursprung (woher/von wem, wann)",
    f.sektor                        AS "Branche",
    f.name                          AS "Firma",
    f.beschreibung                  AS "Kurzbeschreibung",
    f.keywords                      AS "Selektions-Keywords",
    f.mitarbeiter                   AS "Mitarbeiterzahl",
    f.ceo_owner                     AS "CEO/Inhaber",
    f.strasse                       AS "Straße",
    f.ort                           AS "Ort",
    f.plz                           AS "PLZ",
    f.bundesland                    AS "Bundesland",
    f.land                          AS "Land",
    f.telefon                       AS "Tel",
    f.email_allgemein               AS "E-Mail (allgemein)",
    f.website                       AS "www",

    -- Olivers eigene Feldnamen (Dafina 08.09.2026). NUR die
    -- Ueberschriften. "(fuer welches Produkt)" gehoert zu SEINEM
    -- Feldnamen; geliefert wird unveraendert ae.*_bereich, also der
    -- Bereich der Person aus ihrer Rolle. Ein Produkt wird nicht
    -- erfunden - dazu gaebe es in unseren Daten auch nichts.
    ae.a_bereich AS "A) Entscheider-Bereich (für welches Produkt)",
    ae.a_name    AS "A) Name",
    ae.a_rolle   AS "A) Entscheider-Position",
    ae.a_tel     AS "A) Tel",
    ae.a_mail    AS "A) E-Mail",
    ae.b_bereich AS "B) Entscheider-Bereich (für welches Produkt)",
    ae.b_name    AS "B) Name",
    ae.b_rolle   AS "B) Entscheider-Position",
    ae.b_tel     AS "B) Tel",
    ae.b_mail    AS "B) E-Mail",
    ae.c_bereich AS "C) Entscheider-Bereich (für welches Produkt)",
    ae.c_name    AS "C) Name",
    ae.c_rolle   AS "C) Entscheider-Position",
    ae.c_tel     AS "C) Tel",
    ae.c_mail    AS "C) E-Mail",
    ae.d_bereich AS "D) Entscheider-Bereich (für welches Produkt)",
    ae.d_name    AS "D) Name",
    ae.d_rolle   AS "D) Entscheider-Position",
    ae.d_tel     AS "D) Tel",
    ae.d_mail    AS "D) E-Mail",
    ae.e_bereich AS "E) Entscheider-Bereich (für welches Produkt)",
    ae.e_name    AS "E) Name",
    ae.e_rolle   AS "E) Entscheider-Position",
    ae.e_tel     AS "E) Tel",
    ae.e_mail    AS "E) E-Mail",

    u.text  AS "Rausgegeben an (Name, Art, Datum)",
    k.k1    AS "1. Kontakt",
    k.k2    AS "2. Kontakt",
    k.k3    AS "3. Kontakt",
    o.text  AS "Opt-Out (Datum, Weg)"

FROM kern.firma f
-- Alle LEFT: eine Firma ohne Personen und ohne Historie steht trotzdem
-- in Olivers Tabelle, nur mit leeren Feldern.
LEFT JOIN quellen    q  ON q.firma_uid  = f.firma_uid
LEFT JOIN ae            ON ae.firma_uid = f.firma_uid
LEFT JOIN uebergaben u  ON u.firma_uid  = f.firma_uid
LEFT JOIN kontakte   k  ON k.firma_uid  = f.firma_uid
LEFT JOIN opt_outs   o  ON o.firma_uid  = f.firma_uid

-- Zusammengelegte Firmen fallen raus. Sonst saehe Oliver die alte Zeile
-- UND die ueberlebende - genau die Dopplung, gegen die firma_uid gebaut
-- wurde. Die Zeile bleibt in kern.firma stehen, damit ihre Historie
-- lesbar bleibt; gezeigt wird sie nicht.
WHERE f.zusammengelegt_in IS NULL;


COMMENT ON VIEW public.datawarehouse IS
    'Olivers Tabelle: 46 Spalten, A-E flach, zusammengelegte Firmen '
    'ausgeblendet. Spaltenzahl entspricht Olivers Feldliste (46).';

-- Nur der Lesezugriff. coldmail_sync braucht die Ansicht nicht: er
-- schreibt in die Tabellen darunter und liest hier nichts.
GRANT SELECT ON public.datawarehouse TO coldmail_read;

INSERT INTO public.schema_version (version, notiz) VALUES
    (2, 'Phase 4: Ansicht public.datawarehouse (46 Spalten) fuer coldmail_read');

COMMIT;

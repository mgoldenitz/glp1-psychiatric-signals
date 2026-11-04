-- Keep one report per case: the latest version (highest caseversion, then the
-- latest FDA date, then the highest primaryid). Cases the FDA has deleted are
-- dropped. Everything downstream counts reports from this table only.
-- period uses the date FDA first received the case (init_fda_dt), so a case
-- first reported in 2022 and updated in 2024 stays in the earlier period.
DROP TABLE IF EXISTS report;
CREATE TABLE report AS
SELECT primaryid, caseid, caseversion, init_fda_dt, fda_dt, quarter, sex, age_years,
       occr_country, rept_cod, occp_cod,
       CASE WHEN COALESCE(init_fda_dt, fda_dt) < :cutoff THEN 'Before July 2023'
            ELSE 'July 2023 onward' END AS period
FROM (
    SELECT d.*,
           ROW_NUMBER() OVER (PARTITION BY caseid
                              ORDER BY caseversion DESC, fda_dt DESC, primaryid DESC) AS rn
    FROM demo d
    WHERE caseid IS NOT NULL
)
WHERE rn = 1
  AND caseid NOT IN (SELECT caseid FROM deleted);
CREATE UNIQUE INDEX ix_report ON report (primaryid);

-- One row per report and exposure. Each drug is an exposure. Indication
-- subgroups, compounded products and the GLP-1 class are added by
-- 03_deduplicate.py.
DROP TABLE IF EXISTS exposure_report;
CREATE TABLE exposure_report (primaryid INTEGER, exposure TEXT, PRIMARY KEY (primaryid, exposure)) WITHOUT ROWID;

INSERT OR IGNORE INTO exposure_report
SELECT DISTINCT e.primaryid, e.drug
FROM exposure e JOIN report r USING (primaryid);

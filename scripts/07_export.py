"""Export tidy tables for Tableau to outputs/ and print the psychiatric results.

Run after 05_validate.py (and 06_canada_vigilance.py if you have the extract).

    signals.csv            (written by 04) FAERS drug-reaction pairs and statistics
    cv_signals.csv         (written by 06) the same for Canada Vigilance
    validation.csv         (written by 05) positive, negative and comparator controls
    psych_signals.csv      the main Tableau source: psychiatric terms and term
                           groups from both databases, all periods and backgrounds
    drugs.csv              exposure lookup: drug, group, subgroup type
    term_groups.csv        the terms in each psychiatric group and whether FAERS has them
    reports_by_quarter.csv reports per exposure and quarter first received, with
                           reports in each psychiatric group
    reporters.csv          reports per exposure, period and reporter type
    demographics.csv       reports per exposure, sex and age band
    outcomes.csv           reports per exposure and outcome code
    data_summary.csv       quarters loaded, report totals, lines skipped
"""

import argparse

import pandas as pd

from common import (CLASS_EXPOSURE, DRUGS, GROUP_PREFIX, OUTPUTS, SGLT2_CLASS_EXPOSURE, base_drug,
                    connect, target_terms)

OUTCOMES = {"DE": "Death", "LT": "Life-threatening", "HO": "Hospitalization",
            "DS": "Disability", "CA": "Congenital anomaly", "RI": "Required intervention",
            "OT": "Other serious"}
REPORTERS = {"MD": "Physician", "PH": "Pharmacist", "OT": "Other health professional",
             "HP": "Other health professional", "LW": "Lawyer", "CN": "Consumer"}
AGE_BANDS = [0, 18, 30, 45, 65, 200]
AGE_LABELS = ["Under 18", "18 to 29", "30 to 44", "45 to 64", "65 and over"]


def drug_table(exposures):
    d = pd.DataFrame({"exposure": sorted(exposures)})
    d["drug"] = d["exposure"].map(lambda e: e if e in (CLASS_EXPOSURE, SGLT2_CLASS_EXPOSURE) else base_drug(e))
    d["group"] = d["drug"].map(lambda x: DRUGS[x][0] if x in DRUGS else
                               ("GLP-1 RA" if x == CLASS_EXPOSURE else "SGLT2 inhibitor"))
    d["subgroup"] = d["exposure"].map(lambda e: e.split(": ", 1)[1] if ": " in e else
                                      ("drug class" if "(any)" in e else "all uses"))
    return d


def psych_rows(path_faers, path_cv):
    keys = target_terms()
    parts = []
    for p in [path_faers, path_cv]:
        if p.exists():
            s = pd.read_csv(p)
            parts.append(s[s["pt"].str.upper().isin(keys)])
    out = pd.concat(parts, ignore_index=True)
    out["is_group"] = out["pt"].str.startswith(GROUP_PREFIX)
    out["term"] = out["pt"].str.replace(GROUP_PREFIX, "", regex=False)
    return out


def summary(psy):
    g = psy[psy["is_group"] & psy["exposure"].isin([CLASS_EXPOSURE, "semaglutide", "liraglutide", "tirzepatide",
                                                     "semaglutide: weight management",
                                                     "semaglutide: type 2 diabetes"])]
    print("\nPsychiatric term groups: ROR (95% CI), reports")
    for _, r in g.sort_values(["database", "term", "exposure", "background", "period"]).iterrows():
        print(f"  {r.database:<17} {r.term:<38} {r.exposure:<31} {r.background:<40} {r.period:<17} "
              f"{r.ror:6.2f} ({r.ror_lo:.2f} to {r.ror_hi:.2f})  n={r.a}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    con = connect(args.db)
    OUTPUTS.mkdir(exist_ok=True)

    exps = pd.read_sql("SELECT DISTINCT exposure FROM exposure_report", con)["exposure"]
    drug_table(exps).to_csv(OUTPUTS / "drugs.csv", index=False)
    pd.read_sql("SELECT term_group, pt, found FROM term_group", con).to_csv(OUTPUTS / "term_groups.csv", index=False)

    rep = pd.read_sql(
        """SELECT e.exposure, r.primaryid, r.init_fda_dt, r.period, r.sex, r.age_years, r.occp_cod,
                  EXISTS (SELECT 1 FROM outc o WHERE o.primaryid = r.primaryid) AS serious
           FROM exposure_report e JOIN report r USING (primaryid)""", con)
    d = pd.to_datetime(rep["init_fda_dt"], format="%Y%m%d", errors="coerce")
    rep["quarter"] = d.dt.year.astype("Int64").astype(str) + "Q" + d.dt.quarter.astype("Int64").astype(str)

    grp = pd.read_sql(
        """SELECT e.exposure, g.primaryid, REPLACE(p.pt, ?, '') AS measure
           FROM reac_group g JOIN pt p USING (pt_id) JOIN exposure_report e USING (primaryid)""",
        con, params=(GROUP_PREFIX,))
    allq = rep.groupby(["exposure", "quarter"]).agg(reports=("primaryid", "size"),
                                                    serious=("serious", "sum")).reset_index()
    allq["measure"] = "All reports"
    gq = (grp.merge(rep[["exposure", "primaryid", "quarter"]], on=["exposure", "primaryid"])
             .groupby(["exposure", "quarter", "measure"]).size().rename("reports").reset_index())
    by_q = pd.concat([allq, gq], ignore_index=True)
    by_q = by_q[by_q["quarter"] != "<NA>Q<NA>"]
    by_q["year"] = by_q["quarter"].str[:4].astype(int)
    by_q.to_csv(OUTPUTS / "reports_by_quarter.csv", index=False)

    rep["reporter"] = rep["occp_cod"].map(REPORTERS).fillna("Not reported")
    (rep.groupby(["exposure", "period", "reporter"]).size().rename("reports").reset_index()
        .to_csv(OUTPUTS / "reporters.csv", index=False))

    rep["sex"] = rep["sex"].map({"F": "Female", "M": "Male"}).fillna("Not reported")
    rep["age_band"] = pd.cut(rep["age_years"], AGE_BANDS, right=False, labels=AGE_LABELS)
    rep["age_band"] = rep["age_band"].astype(object).fillna("Not reported")
    (rep.groupby(["exposure", "sex", "age_band"]).size().rename("reports").reset_index()
        .to_csv(OUTPUTS / "demographics.csv", index=False))

    outc = pd.read_sql(
        """SELECT e.exposure, o.outc_cod, COUNT(*) AS reports
           FROM exposure_report e JOIN outc o USING (primaryid)
           GROUP BY e.exposure, o.outc_cod""", con)
    outc["outcome"] = outc["outc_cod"].map(OUTCOMES).fillna(outc["outc_cod"])
    outc.to_csv(OUTPUTS / "outcomes.csv", index=False)

    loaded = pd.read_sql("SELECT quarter, reports AS report_versions, skipped_lines FROM loaded ORDER BY quarter", con)
    kept = pd.read_sql("SELECT quarter, COUNT(*) AS cases_kept FROM report GROUP BY quarter", con)
    loaded.merge(kept, on="quarter", how="left").to_csv(OUTPUTS / "data_summary.csv", index=False)
    con.close()

    psy = psych_rows(OUTPUTS / "signals.csv", OUTPUTS / "cv_signals.csv")
    psy.to_csv(OUTPUTS / "psych_signals.csv", index=False)
    print(f"Exported tables to {OUTPUTS}")
    summary(psy)


if __name__ == "__main__":
    main()

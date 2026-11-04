"""Canada Vigilance: load the Health Canada extract and compute the same signals.

Uses the extract Safety Signal Explorer already unzipped (default
~/ssx_data/raw/canada_vigilance; set GLP_CV_RAW to change it). The extract is
a set of $-delimited text files with values in double quotes (layout from
Health Canada's "Canada Vigilance Adverse Reaction Online Database - Data
Structure" page). This script uses:

    Reports.txt                    one row per report
    Report_Drug.txt                drugs on each report and their role
    Drug_Product_Ingredients.txt   active ingredients of each drug product
    Reactions.txt                  MedDRA reaction terms and organ classes
    Report_Drug_Indication.txt     indications (used to split by indication)
    report_links.txt               links between reports, including duplicates

Reports initially received from 2019 onward are kept, to match the FAERS
period. When two reports are linked as duplicates, the earlier one (lower
REPORT_ID) is kept. Drugs count only when their role is "Suspect". The
period split uses the date Health Canada first received the report.

Writes these files to outputs/:
    cv_signals.csv              same columns as signals.csv
    cv_reports_by_year.csv      reports per exposure and year
    pt_soc.csv                  each reaction term's MedDRA organ class
"""

import argparse
import csv
import io
from pathlib import Path

import pandas as pd

from common import (CLASS_EXPOSURE, COMPARATORS, GLP1, GROUP_PREFIX, OUTPUTS, PERIOD_CUTOFF, PERIODS,
                    RAW_CV, SGLT2_CLASS_EXPOSURE, TERM_GROUPS, base_drug, connect, indication_group,
                    match_drugs, stats, target_terms, term_category)

START_DATE = "2019-01-01"
ALL = "All Canada Vigilance"
SGLT2 = "SGLT2 inhibitors"
SGLT2_DM = "SGLT2 inhibitors (diabetes indication)"

COLUMNS = {
    "reports": ["REPORT_ID", "REPORT_NO", "VERSION_NO", "DATRECEIVED", "DATINTRECEIVED", "MAH_NO",
                "REPORT_TYPE_CODE", "REPORT_TYPE_ENG", "REPORT_TYPE_FR", "GENDER_CODE", "GENDER_ENG",
                "GENDER_FR", "AGE", "AGE_Y", "AGE_UNIT_ENG", "AGE_UNIT_FR", "OUTCOME_CODE",
                "OUTCOME_ENG", "OUTCOME_FR", "WEIGHT", "WEIGHT_UNIT_ENG", "WEIGHT_UNIT_FR", "HEIGHT",
                "HEIGHT_UNIT_ENG", "HEIGHT_UNIT_FR", "SERIOUSNESS_CODE", "SERIOUSNESS_ENG",
                "SERIOUSNESS_FR", "DEATH", "DISABILITY", "CONGENITAL_ANOMALY", "LIFE_THREATENING",
                "HOSP_REQUIRED", "OTHER_MEDICALLY_IMP_COND", "REPORTER_TYPE_ENG", "REPORTER_TYPE_FR",
                "SOURCE_CODE", "SOURCE_ENG", "SOURCE_FR", "E2B_IMP_SAFETYREPORT_ID",
                "AUTHORITY_NUMB", "COMPANY_NUMB"],
    "report_drug": ["REPORT_DRUG_ID", "REPORT_ID", "DRUG_PRODUCT_ID", "DRUGNAME", "DRUGINVOLV_ENG",
                    "DRUGINVOLV_FR", "ROUTEADMIN_ENG", "ROUTEADMIN_FR", "UNIT_DOSE_QTY",
                    "DOSE_UNIT_ENG", "DOSE_UNIT_FR", "FREQUENCY", "FREQ_TIME", "FREQUENCY_TIME_ENG",
                    "FREQUENCY_TIME_FR", "FREQ_TIME_UNIT_ENG", "FREQ_TIME_UNIT_FR",
                    "THERAPY_DURATION", "THERAPY_DURATION_UNIT_ENG", "THERAPY_DURATION_UNIT_FR",
                    "DOSAGEFORM_ENG", "DOSAGEFORM_FR"],
    "drug_product_ingredients": ["DRUG_PRODUCT_INGREDIENT_ID", "DRUG_PRODUCT_ID", "DRUGNAME",
                                 "ACTIVE_INGREDIENT_ID", "ACTIVE_INGREDIENT_NAME"],
    "reactions": ["REACTION_ID", "REPORT_ID", "DURATION", "DURATION_UNIT_ENG", "DURATION_UNIT_FR",
                  "PT_NAME_ENG", "PT_NAME_FR", "SOC_NAME_ENG", "SOC_NAME_FR", "MEDDRA_VERSION"],
    "report_drug_indication": ["REPORT_DRUG_ID", "REPORT_ID", "DRUG_PRODUCT_ID", "DRUGNAME",
                               "INDICATION_NAME_ENG", "INDICATION_NAME_FR"],
    "report_links_lx": ["REPORT_LINK_ID", "REPORT_ID", "RECORD_TYPE_ENG", "RECORD_TYPE_FR",
                        "REPORT_LINK_NO"],
}


# File names in the extract differ slightly from the Data Structure page
# (the 2026-06-30 extract has report_links.txt and drug_products.txt).
ALIASES = {"report_links_lx": ["report_links_lx", "report_links"]}


def find_file(raw, name):
    names = ALIASES.get(name, [name])
    hits = [p for p in Path(raw).rglob("*") if p.is_file() and p.stem.lower() in names]
    if not hits:
        raise FileNotFoundError(f"{name}.txt not found under {raw}")
    return hits[0]


def read_cv(raw, name, usecols):
    """Read one extract file. Works with or without a header row."""
    path = find_file(raw, name)
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    cols = COLUMNS[name]
    first = text.split("\n", 1)[0].split("$")[0].strip().strip('"').upper()
    header = 0 if first == cols[0] else None
    df = pd.read_csv(io.StringIO(text), sep="$", quotechar='"', dtype=str, header=header,
                     names=None if header == 0 else cols, index_col=False,
                     on_bad_lines="skip", quoting=csv.QUOTE_MINIMAL)
    df.columns = [str(c).strip().upper() for c in df.columns]
    for c in usecols:
        if c not in df.columns:
            df[c] = None
    return df[usecols].apply(lambda s: s.str.strip())


def parse_date(s):
    """Dates look like 05-JUN-73. Two-digit years above the current year are 1900s."""
    d = pd.to_datetime(s, format="%d-%b-%y", errors="coerce")
    other = d.isna() & s.notna()
    d[other] = pd.to_datetime(s[other], errors="coerce", format="mixed")
    future = d.dt.year > pd.Timestamp.today().year
    d[future] = d[future] - pd.DateOffset(years=100)
    return d


def load(raw):
    rep = read_cv(raw, "reports", ["REPORT_ID", "REPORT_NO", "VERSION_NO", "DATRECEIVED", "DATINTRECEIVED",
                                   "GENDER_ENG", "AGE_Y", "SERIOUSNESS_ENG", "DEATH"])
    rep["received"] = parse_date(rep["DATINTRECEIVED"].fillna(rep["DATRECEIVED"]))
    parsed = rep["received"].notna().mean()
    print(f"Reports: {len(rep):,} rows, received date parsed for {parsed:.1%}")
    rep = rep[rep["received"] >= START_DATE].copy()
    # Keep the latest version if a report number appears more than once.
    rep = (rep.assign(v=pd.to_numeric(rep["VERSION_NO"], errors="coerce"))
              .sort_values("v").drop_duplicates("REPORT_NO", keep="last").drop(columns="v"))

    links = read_cv(raw, "report_links_lx", ["REPORT_ID", "RECORD_TYPE_ENG", "REPORT_LINK_NO"])
    dup = links[links["RECORD_TYPE_ENG"].str.upper().str.startswith("DUPLICATE", na=False)]
    by_no = dict(zip(rep["REPORT_NO"], rep["REPORT_ID"]))
    present = set(rep["REPORT_ID"])
    # For each duplicate pair with both reports in the extract, keep the
    # earlier report (lower REPORT_ID) and drop the other.
    dup_ids = set()
    for rid, link_no in zip(dup["REPORT_ID"], dup["REPORT_LINK_NO"]):
        other = by_no.get(link_no)
        if rid in present and other is not None and other != rid:
            dup_ids.add(max(rid, other, key=int))
    rep = rep[~rep["REPORT_ID"].isin(dup_ids)]
    print(f"Reports received from {START_DATE[:4]}: {len(rep):,} after dropping {len(dup_ids):,} duplicates")
    ids = set(rep["REPORT_ID"])

    rd = read_cv(raw, "report_drug", ["REPORT_DRUG_ID", "REPORT_ID", "DRUG_PRODUCT_ID",
                                      "DRUGNAME", "DRUGINVOLV_ENG"])
    rd = rd[rd["REPORT_ID"].isin(ids) & rd["DRUGINVOLV_ENG"].str.upper().str.startswith("SUSPECT", na=False)]
    ing = read_cv(raw, "drug_product_ingredients", ["DRUG_PRODUCT_ID", "ACTIVE_INGREDIENT_NAME"])
    ing = (ing.dropna().groupby("DRUG_PRODUCT_ID")["ACTIVE_INGREDIENT_NAME"]
              .agg(" | ".join).rename("INGREDIENTS").reset_index())
    rd = rd.merge(ing, on="DRUG_PRODUCT_ID", how="left")
    rd["drug"] = (rd["INGREDIENTS"].fillna("") + " | " + rd["DRUGNAME"].fillna("")).map(match_drugs)
    rd = rd[rd["drug"].map(len) > 0].explode("drug")

    expo = rd[["REPORT_ID", "drug"]].rename(columns={"drug": "exposure"}).drop_duplicates()

    ind = read_cv(raw, "report_drug_indication", ["REPORT_DRUG_ID", "INDICATION_NAME_ENG"])
    rows = rd[["REPORT_ID", "REPORT_DRUG_ID", "DRUGNAME", "drug"]].merge(ind, on="REPORT_DRUG_ID", how="left")
    rows["group"] = [indication_group(i, n) for i, n in zip(rows["INDICATION_NAME_ENG"], rows["DRUGNAME"])]
    known = (rows["group"] != "unknown").groupby([rows["REPORT_ID"], rows["drug"]]).transform("max")
    rows = rows[(rows["group"] != "unknown") | ~known]
    extra = [rows[["REPORT_ID"]].assign(exposure=rows["drug"] + ": " + rows["group"])]
    extra.append(rd.loc[rd["drug"].isin(GLP1), ["REPORT_ID"]].assign(exposure=CLASS_EXPOSURE))
    extra.append(rd.loc[rd["drug"].isin(COMPARATORS), ["REPORT_ID"]].assign(exposure=SGLT2_CLASS_EXPOSURE))
    expo = pd.concat([expo] + extra).drop_duplicates()

    reac = read_cv(raw, "reactions", ["REPORT_ID", "PT_NAME_ENG", "SOC_NAME_ENG"])
    reac = reac[reac["REPORT_ID"].isin(ids)].dropna(subset=["PT_NAME_ENG"])
    rep["period"] = (rep["received"] < PERIOD_CUTOFF).map({True: PERIODS[1], False: PERIODS[2]})
    return rep, expo, reac


def with_groups(reac):
    """Add one row per report and psychiatric term group, named "Group: <name>"."""
    keys = reac["PT_NAME_ENG"].str.upper()
    rows = [reac]
    for name, terms in TERM_GROUPS.items():
        ids = reac.loc[keys.isin([t.upper() for t in terms]), "REPORT_ID"].unique()
        rows.append(pd.DataFrame({"REPORT_ID": ids, "PT_NAME_ENG": GROUP_PREFIX + name, "SOC_NAME_ENG": None}))
    return pd.concat(rows, ignore_index=True)


def signals_one(rep, expo, r, names, period):
    """2 x 2 tables for one period. r has REPORT_ID and pt_key, already limited to the period."""
    total = rep["REPORT_ID"].nunique()
    expo = expo[expo["REPORT_ID"].isin(set(rep["REPORT_ID"]))]
    n_pt = r.groupby("pt_key").size().rename("n_pt")
    n_x = expo.groupby("exposure").size().rename("n_x")
    a = expo.merge(r, on="REPORT_ID").groupby(["exposure", "pt_key"]).size().rename("a").reset_index()
    base = a.join(n_x, on="exposure")

    full = base.join(n_pt, on="pt_key")
    full["b"] = full["n_x"] - full["a"]
    full["c"] = full["n_pt"] - full["a"]
    full["d"] = total - full["n_x"] - full["c"]
    full["background"] = ALL
    frames = [full]

    exps = set(expo["exposure"])
    pools = {SGLT2: [e for e in exps if e in COMPARATORS],
             SGLT2_DM: [f"{d}: type 2 diabetes" for d in COMPARATORS if f"{d}: type 2 diabetes" in exps]}
    study = sorted(e for e in exps if base_drug(e) not in COMPARATORS)
    for bg, pool_exps in pools.items():
        if not pool_exps:
            continue
        pool = set(expo.loc[expo["exposure"].isin(pool_exps), "REPORT_ID"])
        rp = r[r["REPORT_ID"].isin(pool)]
        n_pt_pool = rp.groupby("pt_key").size().rename("n_pt_pool")
        for exp in study:
            xs = set(expo.loc[expo["exposure"] == exp, "REPORT_ID"])
            ov = xs & pool
            ov_pt = rp[rp["REPORT_ID"].isin(ov)].groupby("pt_key").size().rename("ov_pt")
            s = base[base["exposure"] == exp].join(n_pt_pool, on="pt_key").join(ov_pt, on="pt_key")
            s = s.fillna({"n_pt_pool": 0, "ov_pt": 0})
            s["b"] = s["n_x"] - s["a"]
            s["c"] = s["n_pt_pool"] - s["ov_pt"]
            s["d"] = (len(pool) - len(ov)) - s["c"]
            s["background"] = bg
            frames.append(s)

    out = pd.concat(frames, ignore_index=True)
    out["pt"] = out["pt_key"].map(names)
    out["period"] = period
    return out[["period", "exposure", "background", "pt", "a", "b", "c", "d"]]


def signals(rep, expo, reac):
    """Same 2 x 2 tables as 04_signals.py, computed in pandas, for each period."""
    r = with_groups(reac)[["REPORT_ID", "PT_NAME_ENG"]].rename(columns={"PT_NAME_ENG": "pt"})
    r["pt_key"] = r["pt"].str.upper()
    names = r.drop_duplicates("pt_key").set_index("pt_key")["pt"]
    r = r[["REPORT_ID", "pt_key"]].drop_duplicates()
    targets = target_terms()
    parts = [signals_one(rep, expo, r, names, PERIODS[0])]
    for period in PERIODS[1:]:
        ids = set(rep.loc[rep["period"] == period, "REPORT_ID"])
        rp = r[r["REPORT_ID"].isin(ids) & r["pt_key"].isin(targets)]
        parts.append(signals_one(rep[rep["REPORT_ID"].isin(ids)], expo, rp, names, period))
    out = pd.concat(parts, ignore_index=True)
    out = stats(out.astype({k: int for k in "abcd"}))
    out.insert(4, "term_category", out["pt"].map(term_category))
    out.insert(0, "database", "Canada Vigilance")
    return out.sort_values(["period", "exposure", "background", "a"], ascending=[True, True, True, False])


def pt_soc(reac):
    """Most common organ class for each reaction term (MedDRA primary SOC in practice)."""
    s = reac.dropna(subset=["SOC_NAME_ENG"]).assign(pt_key=reac["PT_NAME_ENG"].str.upper())
    s = s.groupby(["pt_key", "SOC_NAME_ENG"]).size().rename("n").reset_index()
    s = s.sort_values(["pt_key", "n"], ascending=[True, False]).drop_duplicates("pt_key")
    return s.rename(columns={"SOC_NAME_ENG": "soc"})[["pt_key", "soc"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(RAW_CV))
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=str(OUTPUTS))
    args = ap.parse_args()
    out = Path(args.out)

    rep, expo, reac = load(args.raw)
    sig = signals(rep, expo, reac)
    by_year = (expo.merge(rep[["REPORT_ID", "received"]], on="REPORT_ID")
                   .assign(year=lambda d: d["received"].dt.year)
                   .groupby(["exposure", "year"]).size().rename("reports").reset_index())
    soc = pt_soc(reac)

    con = connect(args.db)
    rep.drop(columns=["received"]).to_sql("cv_report", con, if_exists="replace", index=False)
    expo.to_sql("cv_exposure_report", con, if_exists="replace", index=False)
    sig.to_sql("cv_signals", con, if_exists="replace", index=False)
    con.close()

    keep = (sig["a"] >= 3) | sig["pt"].str.upper().isin(target_terms())
    sig[keep].to_csv(out / "cv_signals.csv", index=False)
    by_year.to_csv(out / "cv_reports_by_year.csv", index=False)
    soc.to_csv(out / "pt_soc.csv", index=False)

    print("\nReports per exposure:")
    print(expo.groupby("exposure").size().to_string())
    print("Psychiatric results are summarised by 07_export.py.")


if __name__ == "__main__":
    main()

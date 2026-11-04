"""End-to-end test on two small hand-made FAERS quarters and a tiny Canada Vigilance extract.

Every count below can be checked by hand from the fixture:
  - case 10 has two versions; only version 2 (primaryid 102) is kept, and it
    stays in the earlier period because FDA first received it in April 2023
  - case 99 is on the FDA deleted list and is dropped
  - a concomitant (role C) Ozempic row does not count as exposure
  - report 301 has two suicidality terms but counts once in the group
"""

import importlib.util
import math
import sqlite3
import sys
import zipfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402


class Con(sqlite3.Connection):
    """A connection that also remembers the fixture folder."""
    tmp = None

SI = "Group: Suicidal and self-injurious behaviour"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("0", "m0"), ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def table(header, rows):
    lines = ["$".join(header) + "$"] + ["$".join(str(v) for v in r) + "$" for r in rows]
    return "\n".join(lines) + "\n"


def make_zip(path, yq, demo, drug, reac, outc, indi, deleted=None):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"ASCII/DEMO{yq}.txt", table(
            ["primaryid", "caseid", "caseversion", "init_fda_dt", "fda_dt", "age", "age_cod", "sex",
             "occr_country", "rept_cod", "occp_cod"], demo))
        z.writestr(f"ASCII/DRUG{yq}.txt", table(
            ["primaryid", "caseid", "drug_seq", "role_cod", "drugname", "prod_ai", "route"], drug))
        z.writestr(f"ASCII/REAC{yq}.txt", table(["primaryid", "caseid", "pt", "drug_rec_act"], reac))
        z.writestr(f"ASCII/OUTC{yq}.txt", table(["primaryid", "caseid", "outc_cod"], outc))
        z.writestr(f"ASCII/INDI{yq}.txt", table(["primaryid", "caseid", "indi_drug_seq", "indi_pt"], indi))
        if deleted:
            z.writestr(f"Deleted/DELETED_CASES_{yq}.txt", "\n".join(str(d) for d in deleted) + "\n")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("glp1")
    raw = tmp / "raw"
    raw.mkdir()
    make_zip(raw / "faers_ascii_2023q2.zip", "23Q2",
        demo=[
            (101, 10, 1, "20230410", "20230410", 55, "YR", "F", "US", "EXP", "MD"),
            (201, 20, 1, "20230411", "20230411", 40, "YR", "F", "US", "EXP", "CN"),
            (211, 21, 1, "20230412", "20230412", 60, "YR", "M", "US", "EXP", "MD"),
            (221, 22, 1, "20230413", "20230413", 70, "YR", "M", "CA", "EXP", "PH"),
            (231, 23, 1, "20230414", "20230414", 30, "YR", "F", "US", "EXP", "CN"),
            (241, 24, 1, "20230415", "20230415", 50, "YR", "F", "US", "EXP", "CN"),
            (251, 25, 1, "20230416", "20230416", 45, "YR", "M", "US", "EXP", "MD"),
        ],
        drug=[
            (101, 10, 1, "PS", "OZEMPIC", "SEMAGLUTIDE", "SUBCUTANEOUS"),
            (201, 20, 1, "PS", "WEGOVY", "SEMAGLUTIDE", "SUBCUTANEOUS"),
            (211, 21, 1, "PS", "JARDIANCE", "EMPAGLIFLOZIN", "ORAL"),
            (221, 22, 1, "PS", "FARXIGA", "DAPAGLIFLOZIN", "ORAL"),
            (231, 23, 1, "PS", "ASPIRIN", "ASPIRIN", "ORAL"),
            (241, 24, 1, "PS", "MOUNJARO", "TIRZEPATIDE", "SUBCUTANEOUS"),
            (241, 24, 2, "SS", "FARXIGA", "DAPAGLIFLOZIN", "ORAL"),
            (251, 25, 1, "PS", "ASPIRIN", "ASPIRIN", "ORAL"),
            (251, 25, 2, "C", "OZEMPIC", "SEMAGLUTIDE", "SUBCUTANEOUS"),   # concomitant: not exposure
        ],
        reac=[
            (101, 10, "Nausea", ""),
            (201, 20, "Suicidal ideation", ""), (201, 20, "Depression", ""),
            (211, 21, "Diabetic ketoacidosis", ""),
            (221, 22, "Anxiety", ""),
            (231, 23, "Nausea", ""),
            (241, 24, "Nausea", ""), (241, 24, "Anxiety", ""),
            (251, 25, "Suicidal ideation", ""),
        ],
        outc=[(201, 20, "HO")],
        indi=[(101, 10, 1, "Type 2 diabetes mellitus"), (211, 21, 1, "Type 2 diabetes mellitus"),
              (221, 22, 1, "Cardiac failure"), (241, 24, 1, "Product used for unknown indication")],
    )
    make_zip(raw / "faers_ascii_2023q3.zip", "23Q3",
        demo=[
            (102, 10, 2, "20230410", "20230805", 55, "YR", "F", "US", "EXP", "MD"),
            (301, 30, 1, "20230801", "20230801", 35, "YR", "F", "US", "EXP", "CN"),
            (311, 31, 1, "20230802", "20230802", 65, "YR", "M", "US", "EXP", "MD"),
            (991, 99, 1, "20230803", "20230803", 45, "YR", "M", "US", "EXP", "CN"),
        ],
        drug=[
            (102, 10, 1, "PS", "OZEMPIC", "SEMAGLUTIDE", "SUBCUTANEOUS"),
            (301, 30, 1, "PS", "SEMAGLUTIDE (COMPOUNDED)", "SEMAGLUTIDE", "SUBCUTANEOUS"),
            (311, 31, 1, "PS", "JARDIANCE", "EMPAGLIFLOZIN", "ORAL"),
            (991, 99, 1, "PS", "OZEMPIC", "SEMAGLUTIDE", "SUBCUTANEOUS"),
        ],
        reac=[
            (102, 10, "Nausea", ""), (102, 10, "Vomiting", ""),
            (301, 30, "Suicide attempt", ""), (301, 30, "Suicidal ideation", ""),
            (311, 31, "Nausea", ""),
            (991, 99, "Suicidal ideation", ""),
        ],
        outc=[], indi=[(102, 10, 1, "Type 2 diabetes mellitus"), (301, 30, 1, "Weight loss"),
                       (311, 31, 1, "Type 2 diabetes mellitus")],
        deleted=[99],
    )
    dbp = tmp / "test.sqlite"
    old = sys.argv
    for name, extra in [("02_load_faers", ["--raw", str(raw)]), ("03_deduplicate", []),
                        ("04_signals", ["--out", str(tmp / "signals.csv")])]:
        sys.argv = [name, "--db", str(dbp)] + extra
        load(name).main()
    sys.argv = old
    con = sqlite3.connect(dbp, factory=Con)
    con.tmp = tmp
    yield con
    con.close()


def test_match_drugs():
    assert common.match_drugs("SEMAGLUTIDE | OZEMPIC") == {"semaglutide"}
    assert common.match_drugs("INSULIN DEGLUDEC\\LIRAGLUTIDE") == {"liraglutide"}
    assert common.match_drugs("SYNJARDY") == {"empagliflozin"}
    assert common.match_drugs("DAPAGLIFLOZIN PROPANEDIOL") == {"dapagliflozin"}
    assert common.match_drugs("ZEPBOUND") == {"tirzepatide"}
    assert common.match_drugs("METFORMIN") == set()
    assert common.match_drugs(None) == set()


def test_indication_group():
    g = common.indication_group
    assert g("Type 2 diabetes mellitus") == "type 2 diabetes"
    assert g("Obesity") == "weight management"
    assert g("Weight loss") == "weight management"
    assert g("Cardiac failure") == "heart failure or kidney disease"
    assert g("Polycystic ovaries") == "other"
    assert g("Product used for unknown indication", "WEGOVY") == "weight management"
    assert g(None, "OZEMPIC") == "type 2 diabetes"
    assert g(None, "SEMAGLUTIDE") == "unknown"


def test_term_category():
    assert common.term_category(SI) == "Term group"
    assert common.term_category("Suicidal ideation") == "Clinical"
    assert common.term_category("Off label use") == "Product, device or use"


def test_deduplication_and_periods(db):
    rep = dict(db.execute("SELECT primaryid, period FROM report"))
    assert 102 in rep and 101 not in rep
    assert 991 not in rep
    assert len(rep) == 9
    assert rep[102] == "Before July 2023"
    assert rep[301] == "July 2023 onward"


def test_exposures(db):
    n = dict(db.execute("SELECT exposure, COUNT(*) FROM exposure_report GROUP BY exposure"))
    assert n["semaglutide"] == 3                       # 102, 201, 301 (not 251)
    assert n["GLP-1 RA (any)"] == 4                    # plus 241
    assert n["SGLT2 inhibitor (any)"] == 4             # 211, 221, 241, 311
    assert n["semaglutide: type 2 diabetes"] == 1      # 102
    assert n["semaglutide: weight management"] == 2    # 201 by brand, 301 by indication
    assert n["semaglutide: compounded"] == 1
    assert n["tirzepatide: type 2 diabetes"] == 1      # unknown indication, Mounjaro brand
    assert n["dapagliflozin: heart failure or kidney disease"] == 1
    assert n["dapagliflozin: unknown"] == 1
    assert n["empagliflozin: type 2 diabetes"] == 2


def test_term_groups(db):
    n = dict(db.execute("""SELECT p.pt, COUNT(*) FROM reac_group g JOIN pt p USING (pt_id)
                           JOIN report r USING (primaryid) GROUP BY p.pt"""))
    assert n[SI] == 3                                  # 201, 251, 301 (301 once)
    assert n["Group: Depression"] == 1
    assert n["Group: Anxiety"] == 2


def row(db, exposure, background, pt, period="All years"):
    df = pd.read_sql("SELECT * FROM signals WHERE exposure=? AND background=? AND pt=? AND period=?",
                     db, params=(exposure, background, pt, period))
    assert len(df) == 1
    return df.iloc[0]


def test_two_by_two_all_faers(db):
    r = row(db, "GLP-1 RA (any)", "All FAERS", SI)
    assert (r.a, r.b, r.c, r.d) == (2, 2, 1, 4)
    r = row(db, "semaglutide", "All FAERS", "Nausea")
    assert (r.a, r.b, r.c, r.d) == (1, 2, 3, 3)
    assert math.isclose(r.ror, (1 * 3) / (2 * 3))


def test_two_by_two_sglt2(db):
    # Pool 211, 221, 241, 311; report 241 also names tirzepatide and leaves the pool.
    r = row(db, "GLP-1 RA (any)", "SGLT2 inhibitors", "Nausea")
    assert (r.a, r.b, r.c, r.d) == (2, 2, 1, 2)
    r = row(db, "GLP-1 RA (any)", "SGLT2 inhibitors (diabetes indication)", "Nausea")
    assert (r.a, r.b, r.c, r.d) == (2, 2, 1, 1)
    none = pd.read_sql("SELECT * FROM signals WHERE exposure='empagliflozin' AND background LIKE 'SGLT2%'", db)
    assert none.empty


def test_periods(db):
    r = row(db, "semaglutide", "All FAERS", SI, "July 2023 onward")
    assert (r.a, r.b, r.c, r.d) == (1, 0, 0, 1)
    r = row(db, "GLP-1 RA (any)", "All FAERS", SI, "Before July 2023")
    assert (r.a, r.b, r.c, r.d) == (1, 2, 1, 3)
    # Periods hold psychiatric terms only.
    other = pd.read_sql("SELECT DISTINCT pt FROM signals WHERE period != 'All years'", db)["pt"]
    assert set(other.str.upper()) <= common.target_terms()


def test_reporter_subsets(db):
    # Health professionals filed 102, 211, 251, 311 (MD) and 221 (PH); consumers 201, 231, 241, 301.
    r = row(db, "GLP-1 RA (any)", "All FAERS", SI, "Consumer reports")
    assert (r.a, r.b, r.c, r.d) == (2, 1, 0, 1)
    r = row(db, "semaglutide", "All FAERS", "Group: Depression", "Consumer reports")
    assert (r.a, r.b, r.c, r.d) == (1, 1, 0, 2)
    hp = pd.read_sql("SELECT * FROM signals WHERE period='Health professional reports' AND pt=?", db, params=(SI,))
    assert set(hp["exposure"]) == set()          # the only HP suicidality report (251) has no study drug


def test_stats_known_values():
    df = pd.DataFrame({"a": [20], "b": [80], "c": [100], "d": [9800]})
    out = common.stats(df).iloc[0]
    assert math.isclose(out.prr, 0.2 / (100 / 9900))
    assert math.isclose(out.ror, (20 * 9800) / (80 * 100))
    assert out.ror_lo < out.ror < out.ror_hi
    assert out.signal_evans and out.signal_ror and out.signal_ic


def test_validate_runs(db):
    v = load("05_validate")
    sig = pd.read_sql("SELECT * FROM signals", db)
    res = v.run(sig)
    assert {"Positive", "Comparator check"} <= set(res["kind"])
    nausea = res[(res["exposure"] == "GLP-1 RA (any)") & (res["background"] == "All FAERS")
                 & (res["reaction"] == "Nausea")].iloc[0]
    assert nausea["reports"] == 2


def test_export_runs(db, monkeypatch):
    ex = load("07_export")
    out = db.tmp / "outputs"
    out.mkdir(exist_ok=True)
    pd.read_sql("SELECT * FROM signals", db).to_csv(out / "signals.csv", index=False)
    monkeypatch.setattr(ex, "OUTPUTS", out)
    old = sys.argv
    sys.argv = ["07_export", "--db", str(db.tmp / "test.sqlite")]
    ex.main()
    sys.argv = old
    psy = pd.read_csv(out / "psych_signals.csv")
    assert set(psy["database"]) == {"FAERS"}
    assert psy["is_group"].any()
    q = pd.read_csv(out / "reports_by_quarter.csv")
    si = q[(q.exposure == "semaglutide") & (q.measure == "Suicidal and self-injurious behaviour")]
    assert dict(zip(si.quarter, si.reports)) == {"2023Q2": 1, "2023Q3": 1}


def cv_file(path, cols, rows, header=True):
    q = lambda v: f'"{v}"'
    lines = (["$".join(q(c) for c in cols)] if header else []) + ["$".join(q(v) for v in r) for r in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_canada_vigilance(tmp_path):
    cv = load("06_canada_vigilance")
    C = cv.COLUMNS
    raw = tmp_path / "cv"
    raw.mkdir()

    def pad(name, d):
        return [d.get(c, "") for c in C[name]]

    reports = [
        {"REPORT_ID": "1", "REPORT_NO": "000000001", "DATINTRECEIVED": "01-MAY-20"},
        {"REPORT_ID": "2", "REPORT_NO": "000000002", "DATINTRECEIVED": "2024-01-01"},
        {"REPORT_ID": "3", "REPORT_NO": "000000003", "DATINTRECEIVED": "2024-02-01"},  # duplicate of 2
        {"REPORT_ID": "4", "REPORT_NO": "000000004", "DATINTRECEIVED": "2022-01-01"},
        {"REPORT_ID": "5", "REPORT_NO": "000000005", "DATINTRECEIVED": "05-JUN-73"},  # before 2019
        {"REPORT_ID": "6", "REPORT_NO": "000000006", "DATINTRECEIVED": "2023-08-01"},
    ]
    cv_file(raw / "reports.txt", C["reports"], [pad("reports", r) for r in reports], header=False)
    cv_file(raw / "report_links.txt", C["report_links_lx"],
            [pad("report_links_lx", {"REPORT_LINK_ID": "1", "REPORT_ID": "2", "RECORD_TYPE_ENG": "Duplicate",
                                     "REPORT_LINK_NO": "000000003"})], header=False)
    drugs = [("10", "1", "100", "OZEMPIC", "Suspect"), ("11", "2", "101", "WEGOVY", "Suspect"),
             ("12", "3", "101", "WEGOVY", "Suspect"), ("13", "4", "200", "FORXIGA", "Suspect"),
             ("14", "4", "100", "OZEMPIC", "Concomitant"), ("15", "5", "100", "OZEMPIC", "Suspect"),
             ("16", "6", "300", "ASPIRIN", "Suspect")]
    cv_file(raw / "Report_Drug.txt", C["report_drug"],
            [pad("report_drug", dict(zip(["REPORT_DRUG_ID", "REPORT_ID", "DRUG_PRODUCT_ID", "DRUGNAME",
                                          "DRUGINVOLV_ENG"], d))) for d in drugs])
    ingr = [("1", "100", "SEMAGLUTIDE"), ("2", "101", "SEMAGLUTIDE"), ("3", "200", "DAPAGLIFLOZIN")]
    cv_file(raw / "Drug_Product_Ingredients.txt", C["drug_product_ingredients"],
            [pad("drug_product_ingredients", {"DRUG_PRODUCT_INGREDIENT_ID": i, "DRUG_PRODUCT_ID": p,
                                              "ACTIVE_INGREDIENT_NAME": n}) for i, p, n in ingr])
    reac = [("1", "Suicidal ideation", "Psychiatric disorders"), ("2", "Depression", "Psychiatric disorders"),
            ("3", "Depression", "Psychiatric disorders"), ("4", "Anxiety", "Psychiatric disorders"),
            ("6", "Suicidal ideation", "Psychiatric disorders")]
    cv_file(raw / "Reactions.txt", C["reactions"],
            [pad("reactions", {"REACTION_ID": str(i), "REPORT_ID": r, "PT_NAME_ENG": p, "SOC_NAME_ENG": s})
             for i, (r, p, s) in enumerate(reac)])
    cv_file(raw / "Report_Drug_Indication.txt", C["report_drug_indication"],
            [pad("report_drug_indication", {"REPORT_DRUG_ID": "10", "REPORT_ID": "1",
                                            "INDICATION_NAME_ENG": "Type 2 diabetes mellitus"})])

    rep, expo, rx = cv.load(raw)
    assert set(rep["REPORT_ID"]) == {"1", "2", "4", "6"}
    e = expo.groupby("exposure")["REPORT_ID"].apply(set)
    assert e["GLP-1 RA (any)"] == {"1", "2"}
    assert e["semaglutide: type 2 diabetes"] == {"1"}
    assert e["semaglutide: weight management"] == {"2"}
    sig = cv.signals(rep, expo, rx)
    pick = lambda x, b, p, per="All years": sig[(sig.exposure == x) & (sig.background == b)
                                               & (sig.pt == p) & (sig.period == per)].iloc[0]
    r = pick("GLP-1 RA (any)", "All Canada Vigilance", SI)
    assert (r.a, r.b, r.c, r.d) == (1, 1, 1, 1)
    r = pick("GLP-1 RA (any)", "SGLT2 inhibitors", SI)
    assert (r.a, r.b, r.c, r.d) == (1, 1, 0, 1)
    r = pick("GLP-1 RA (any)", "All Canada Vigilance", "Group: Depression", "July 2023 onward")
    assert (r.a, r.b, r.c, r.d) == (1, 0, 0, 1)
    assert set(sig["database"]) == {"Canada Vigilance"}


def test_cv_dates():
    cv = load("06_canada_vigilance")
    d = cv.parse_date(pd.Series(["05-JUN-73", "01-MAY-20", None]))
    assert d.iloc[0].year == 1973 and d.iloc[1].year == 2020 and pd.isna(d.iloc[2])

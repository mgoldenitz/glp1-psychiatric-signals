"""De-duplicate reports, build one row per report and exposure, and add term groups.

Runs sql/03_deduplicate.sql, then adds these exposures:
    "<drug>: <indication>"   indication group of the drug row (common.indication_group)
    "<drug>: compounded"     semaglutide or tirzepatide rows whose name says compounded
    "GLP-1 RA (any)"         any of the six GLP-1 receptor agonists
    "SGLT2 inhibitor (any)"  any of the five SGLT2 inhibitors

Then writes each psychiatric term group (common.TERM_GROUPS) as an extra
reaction term named "Group: <name>", so every later step treats a group like
a single term. The view reac_all holds real terms plus groups.
"""

import argparse

import pandas as pd

from common import (CLASS_EXPOSURE, COMPARATORS, GLP1, SGLT2_CLASS_EXPOSURE, GROUP_PREFIX, PERIOD_CUTOFF, REPO, TERM_GROUPS,
                    connect, indication_group, is_compounded)


def indication_rows(df, id_col="primaryid"):
    """df has id, drug, drugname, indi_pt (one row per drug row and indication)."""
    df = df.copy()
    df["group"] = [indication_group(i, n) for i, n in zip(df["indi_pt"], df["drugname"])]
    # A report with any known indication for a drug is not also "unknown" for it.
    known = (df["group"] != "unknown").groupby([df[id_col], df["drug"]]).transform("max")
    df = df[(df["group"] != "unknown") | ~known]
    return df[[id_col]].assign(exposure=df["drug"] + ": " + df["group"]).drop_duplicates()


def add_term_groups(con):
    con.execute("DROP VIEW IF EXISTS reac_all")
    con.execute("DROP TABLE IF EXISTS reac_group")
    con.execute("CREATE TABLE reac_group (primaryid INTEGER, pt_id INTEGER, PRIMARY KEY (primaryid, pt_id)) WITHOUT ROWID")
    con.execute("DROP TABLE IF EXISTS term_group")
    con.execute("CREATE TABLE term_group (term_group TEXT, pt TEXT, pt_key TEXT, found INTEGER)")
    for name, terms in TERM_GROUPS.items():
        label = GROUP_PREFIX + name
        con.execute("INSERT OR IGNORE INTO pt (pt_key, pt) VALUES (?, ?)", (label.upper(), label))
        gid = con.execute("SELECT pt_id FROM pt WHERE pt_key = ?", (label.upper(),)).fetchone()[0]
        keys = [t.upper() for t in terms]
        marks = ",".join("?" * len(keys))
        con.execute(f"""INSERT OR IGNORE INTO reac_group
                        SELECT DISTINCT x.primaryid, ? FROM reac x JOIN pt p USING (pt_id)
                        WHERE p.pt_key IN ({marks})""", [gid] + keys)
        found = {k for (k,) in con.execute(f"SELECT pt_key FROM pt WHERE pt_key IN ({marks})", keys)}
        con.executemany("INSERT INTO term_group VALUES (?, ?, ?, ?)",
                        [(name, t, t.upper(), int(t.upper() in found)) for t in terms])
    con.execute("CREATE VIEW reac_all AS SELECT primaryid, pt_id FROM reac "
                "UNION ALL SELECT primaryid, pt_id FROM reac_group")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    args = ap.parse_args()
    con = connect(args.db)

    cutoff = PERIOD_CUTOFF.replace("-", "")
    con.executescript((REPO / "sql" / "03_deduplicate.sql").read_text().replace(":cutoff", f"'{cutoff}'"))

    rowsdf = pd.read_sql(
        """SELECT DISTINCT e.primaryid, e.drug, e.drug_seq, e.drugname, i.indi_pt
           FROM exposure e
           JOIN report r USING (primaryid)
           LEFT JOIN indi i ON i.primaryid = e.primaryid AND i.drug_seq = e.drug_seq""",
        con,
    )
    extra = [indication_rows(rowsdf)]
    comp = rowsdf[rowsdf["drugname"].map(is_compounded) & rowsdf["drug"].isin(["semaglutide", "tirzepatide"])]
    extra.append(comp[["primaryid"]].assign(exposure=comp["drug"] + ": compounded"))
    glp = rowsdf[rowsdf["drug"].isin(GLP1)]
    extra.append(glp[["primaryid"]].assign(exposure=CLASS_EXPOSURE))
    sg = rowsdf[rowsdf["drug"].isin(COMPARATORS)]
    extra.append(sg[["primaryid"]].assign(exposure=SGLT2_CLASS_EXPOSURE))
    allrows = pd.concat(extra).drop_duplicates()
    con.executemany("INSERT OR IGNORE INTO exposure_report VALUES (?, ?)",
                    allrows[["primaryid", "exposure"]].itertuples(index=False))
    add_term_groups(con)
    con.commit()

    n_demo = con.execute("SELECT COUNT(*) FROM demo").fetchone()[0]
    n_rep = con.execute("SELECT COUNT(*) FROM report").fetchone()[0]
    print(f"{n_demo:,} report versions loaded, {n_rep:,} cases kept after de-duplication")
    for exp, n in con.execute(
        "SELECT exposure, COUNT(*) FROM exposure_report GROUP BY exposure ORDER BY exposure"
    ):
        print(f"  {exp:<45} {n:>9,}")
    missing = con.execute("SELECT term_group, pt FROM term_group WHERE found = 0").fetchall()
    if missing:
        print("Group terms not found in FAERS (they add nothing):", "; ".join(f"{g}: {p}" for g, p in missing))
    con.close()


if __name__ == "__main__":
    main()

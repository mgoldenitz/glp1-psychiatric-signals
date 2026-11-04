"""Disproportionality statistics for every exposure and reaction term.

For each exposure X and reaction R, with report counts:
    a = X with R          b = X without R
    c = others with R     d = others without R

"Others" is one of three backgrounds:
    All FAERS                               every other de-duplicated report
    SGLT2 inhibitors                        reports naming one of the five SGLT2
                                            inhibitors, minus reports that also name X
    SGLT2 inhibitors (diabetes indication)  the same, limited to SGLT2 drug rows
                                            given for type 2 diabetes

SGLT2 inhibitors are the active comparator: they treat the same disease
(type 2 diabetes) and have no known psychiatric effect. FDA's 2026 Sentinel study used the same comparison.
The comparator backgrounds are only computed for exposures that are not
SGLT2 inhibitors themselves.

Periods: "All years" covers every reaction term. "Before July 2023" and
"July 2023 onward" cover the psychiatric terms and term groups only, with the
background limited to the same period, to show how much of any signal comes
after EMA's review and the media coverage that followed.

Measures (same as Safety Signal Explorer):
    PRR with 95% CI, chi-squared with Yates correction
    Evans signal: a >= 3, PRR >= 2, chi-squared >= 4
    ROR with 95% CI; ROR signal: a >= 3 and lower bound > 1
    IC with the IC025 approximation; IC signal: IC025 > 0

Writes the full table to the database (signals) and, to keep the file small
enough for GitHub and Tableau, outputs/signals.csv with the rows that have at
least 3 reports or are psychiatric target terms.
"""

import argparse

import pandas as pd

from common import (COMPARATORS, OUTPUTS, PERIODS, base_drug, connect, stats, target_terms,
                    term_category)

ALL = "All FAERS"
SGLT2 = "SGLT2 inhibitors"
SGLT2_DM = "SGLT2 inhibitors (diabetes indication)"


def backgrounds(exposures):
    exps = list(exposures)
    return {
        SGLT2: [e for e in exps if e in COMPARATORS],
        SGLT2_DM: [f"{d}: type 2 diabetes" for d in COMPARATORS if f"{d}: type 2 diabetes" in exps],
    }


def sql_list(items):
    return ", ".join("'" + str(i).replace("'", "''") + "'" for i in items) or "''"


def counts(con, period, only_targets):
    """2 x 2 tables for one period. Returns a frame with exposure, background, pt_id, a, b, c, d."""
    q = lambda s: pd.read_sql(s, con)
    # Real terms (reac) and term groups (reac_group) have different pt_ids, so
    # their counts are computed separately and stacked. This keeps SQLite on
    # the primary-key index instead of joining through a UNION ALL view.
    qr = lambda s: pd.concat([q(s.format(R=src)) for src in sources], ignore_index=True)
    con.execute("DROP TABLE IF EXISTS temp.scope")
    if period == "All years":
        con.execute("CREATE TEMP TABLE scope AS SELECT primaryid FROM report")
    else:
        con.execute("CREATE TEMP TABLE scope AS SELECT primaryid FROM report WHERE period = ?", (period,))
    con.execute("CREATE UNIQUE INDEX temp.ix_scope ON scope (primaryid)")

    con.execute("DROP TABLE IF EXISTS temp.rx")
    if only_targets:
        keys = sql_list(sorted(target_terms()))
        ids = f"(SELECT pt_id FROM pt WHERE pt_key IN ({keys}))"
        con.execute(f"""CREATE TEMP TABLE rx AS
                        SELECT x.primaryid, x.pt_id FROM reac x JOIN scope USING (primaryid) WHERE x.pt_id IN {ids}
                        UNION ALL
                        SELECT x.primaryid, x.pt_id FROM reac_group x JOIN scope USING (primaryid)""")
        con.execute("CREATE INDEX temp.ix_rx ON rx (primaryid)")
        sources = ["rx"]
    else:
        sources = ["reac", "reac_group"]

    total = con.execute("SELECT COUNT(*) FROM scope").fetchone()[0]
    n_pt = qr("SELECT x.pt_id, COUNT(*) AS n_pt FROM {R} x JOIN scope USING (primaryid) GROUP BY x.pt_id")
    n_x = q("SELECT e.exposure, COUNT(*) AS n_x FROM exposure_report e JOIN scope USING (primaryid) GROUP BY e.exposure")
    a = qr("""SELECT e.exposure, x.pt_id, COUNT(*) AS a
              FROM exposure_report e JOIN scope USING (primaryid) JOIN {R} x USING (primaryid)
              GROUP BY e.exposure, x.pt_id""")
    base = a.merge(n_x, on="exposure")

    full = base.merge(n_pt, on="pt_id")
    full["b"] = full["n_x"] - full["a"]
    full["c"] = full["n_pt"] - full["a"]
    full["d"] = total - full["n_x"] - full["c"]
    full["background"] = ALL
    frames = [full]

    study = sorted(e for e in n_x["exposure"] if base_drug(e) not in COMPARATORS)
    for name, pool_exps in backgrounds(n_x["exposure"]).items():
        if not pool_exps:
            continue
        con.execute("DROP TABLE IF EXISTS temp.pool")
        con.execute(f"""CREATE TEMP TABLE pool AS SELECT DISTINCT e.primaryid
                        FROM exposure_report e JOIN scope USING (primaryid)
                        WHERE e.exposure IN ({sql_list(pool_exps)})""")
        con.execute("CREATE UNIQUE INDEX temp.ix_pool ON pool (primaryid)")
        n_pool = con.execute("SELECT COUNT(*) FROM pool").fetchone()[0]
        n_pt_pool = qr("SELECT x.pt_id, COUNT(*) AS n_pt_pool FROM {R} x JOIN pool USING (primaryid) GROUP BY x.pt_id")
        ov = q(f"""SELECT e.exposure, COUNT(*) AS ov FROM exposure_report e JOIN pool USING (primaryid)
                   WHERE e.exposure IN ({sql_list(study)}) GROUP BY e.exposure""")
        ov_pt = qr("""SELECT e.exposure, x.pt_id, COUNT(*) AS ov_pt
                      FROM exposure_report e JOIN pool USING (primaryid) JOIN {R} x USING (primaryid)
                      WHERE e.exposure IN (""" + sql_list(study).replace("{", "{{").replace("}", "}}")
                   + ") GROUP BY e.exposure, x.pt_id")
        s = (base[base["exposure"].isin(study)]
             .merge(n_pt_pool, on="pt_id", how="left")
             .merge(ov_pt, on=["exposure", "pt_id"], how="left")
             .merge(ov, on="exposure", how="left")
             .fillna({"n_pt_pool": 0, "ov_pt": 0, "ov": 0}))
        s["b"] = s["n_x"] - s["a"]
        s["c"] = s["n_pt_pool"] - s["ov_pt"]
        s["d"] = (n_pool - s["ov"]) - s["c"]
        s["background"] = name
        frames.append(s)

    out = pd.concat(frames, ignore_index=True)[["exposure", "background", "pt_id", "a", "b", "c", "d"]]
    out["period"] = period
    return out


def build(con):
    parts = [counts(con, p, only_targets=(p != "All years")) for p in PERIODS]
    sig = stats(pd.concat(parts, ignore_index=True))
    sig = sig.merge(pd.read_sql("SELECT pt_id, pt FROM pt", con), on="pt_id")
    sig["term_category"] = sig["pt"].map(term_category)
    for k in "abcd":
        sig[k] = sig[k].astype(int)
    sig.insert(0, "database", "FAERS")
    order = ["database", "period", "exposure", "background", "pt", "term_category", "a", "b", "c", "d",
             "expected", "prr", "prr_lo", "prr_hi", "chi2", "ror", "ror_lo", "ror_hi", "ic", "ic025",
             "signal_evans", "signal_ror", "signal_ic"]
    return sig[order].sort_values(["period", "exposure", "background", "a"],
                                  ascending=[True, True, True, False])


def csv_rows(sig):
    targets = target_terms()
    return sig[(sig["a"] >= 3) | sig["pt"].str.upper().isin(targets)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=str(OUTPUTS / "signals.csv"))
    args = ap.parse_args()
    con = connect(args.db)
    sig = build(con)
    sig.to_sql("signals", con, if_exists="replace", index=False)
    con.close()
    csv_rows(sig).to_csv(args.out, index=False)
    print(f"{len(sig):,} drug-reaction pairs in the database; {len(csv_rows(sig)):,} written to {args.out}")
    print("Run 05_validate.py next. Psychiatric results are summarised by 06_export.py, after the controls pass.")

if __name__ == "__main__":
    main()

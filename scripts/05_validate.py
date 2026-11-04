"""Check the signals against reactions whose answer is already known.

Run this before reading any psychiatric result.

Positive controls are reactions on the GLP-1 and SGLT2 labels. Each should be
flagged (ROR lower bound above 1, at least 3 reports) against all of FAERS.
If one is not, the pipeline is more likely wrong than the label.

Comparator checks test the SGLT2 background: nausea should still be flagged
for GLP-1 drugs against SGLT2 inhibitors, and diabetic ketoacidosis (an SGLT2
effect) should not be.

Negative controls are reactions with no known link to GLP-1 drugs, SGLT2
inhibitors, diabetes or obesity. The candidate list and the selection rule
were fixed before any data were loaded: the first four candidates, in list
order, with at least 10 reports for "GLP-1 RA (any)" are used. The rule looks
at report counts only, never at the ROR. A flagged negative control is a
warning to look at, not a failure.

Writes outputs/validation.csv and exits with code 1 if a positive control or
comparator check fails.
"""

import argparse
import sys

import pandas as pd

from common import CLASS_EXPOSURE, OUTPUTS, SGLT2_CLASS_EXPOSURE, connect

ALL = "All FAERS"
SGLT2 = "SGLT2 inhibitors"
GI_PANCREAS = ["Pancreatitis", "Pancreatitis acute"]
GALLBLADDER = ["Cholelithiasis", "Cholecystitis", "Cholecystitis acute", "Cholecystitis chronic"]
INJECTION = ["Injection site pain", "Injection site erythema", "Injection site reaction",
             "Injection site pruritus", "Injection site swelling"]
DKA = ["Diabetic ketoacidosis", "Euglycaemic diabetic ketoacidosis", "Ketoacidosis"]
GENITAL = ["Genital infection fungal", "Vulvovaginal mycotic infection", "Genital candidiasis",
           "Vulvovaginal candidiasis", "Balanoposthitis", "Genital infection"]

# (exposure, background, terms, expected, kind, source). For a list of terms the
# control passes if any one of them is flagged.
CONTROLS = [
    (CLASS_EXPOSURE, ALL, ["Nausea"], True, "Positive", "GLP-1 RA labels: most common adverse reaction"),
    (CLASS_EXPOSURE, ALL, ["Vomiting"], True, "Positive", "GLP-1 RA labels: common adverse reaction"),
    (CLASS_EXPOSURE, ALL, ["Decreased appetite"], True, "Positive", "GLP-1 RA labels: common adverse reaction"),
    (CLASS_EXPOSURE, ALL, GI_PANCREAS, True, "Positive", "GLP-1 RA labels: warnings (acute pancreatitis)"),
    (CLASS_EXPOSURE, ALL, GALLBLADDER, True, "Positive", "GLP-1 RA labels: warnings (gallbladder disease)"),
    (CLASS_EXPOSURE, ALL, INJECTION, True, "Positive", "Injectable GLP-1 RA labels: injection site reactions"),
    ("semaglutide", ALL, ["Nausea"], True, "Positive", "Ozempic and Wegovy labels"),
    ("liraglutide", ALL, ["Nausea"], True, "Positive", "Victoza and Saxenda labels"),
    ("tirzepatide", ALL, ["Nausea"], True, "Positive", "Mounjaro and Zepbound labels"),
    (SGLT2_CLASS_EXPOSURE, ALL, DKA, True, "Positive", "SGLT2 inhibitor labels: warnings (ketoacidosis)"),
    (SGLT2_CLASS_EXPOSURE, ALL, GENITAL, True, "Positive", "SGLT2 inhibitor labels: genital mycotic infections"),
    (SGLT2_CLASS_EXPOSURE, ALL, ["Fournier's gangrene"], True, "Positive",
     "SGLT2 inhibitor labels: warnings (necrotising fasciitis of the perineum)"),
    (CLASS_EXPOSURE, SGLT2, ["Nausea"], True, "Comparator check", "GI effects are GLP-1 specific"),
    (CLASS_EXPOSURE, SGLT2, DKA, False, "Comparator check", "Ketoacidosis is an SGLT2 effect"),
]

# Fixed before data were loaded (3 November 2026). Order matters.
NEGATIVE_CANDIDATES = [
    "Seasonal allergy", "Ingrowing nail", "Ligament sprain", "Epicondylitis", "Sunburn",
    "Rotator cuff syndrome", "Hordeolum", "Tendonitis", "Bursitis", "Plantar fasciitis",
]
N_NEGATIVE = 4
MIN_NEGATIVE_REPORTS = 10


def pick_negatives(sig):
    s = sig[(sig["exposure"] == CLASS_EXPOSURE) & (sig["background"] == ALL)]
    n = dict(zip(s["pt"].str.upper(), s["a"]))
    chosen = [t for t in NEGATIVE_CANDIDATES if n.get(t.upper(), 0) >= MIN_NEGATIVE_REPORTS][:N_NEGATIVE]
    return [(CLASS_EXPOSURE, ALL, [t], False, "Negative", "Negative control (picked by report count rule)")
            for t in chosen]


def check(sig, controls, flag="signal_ror"):
    rows = []
    s = sig[sig["period"] == "All years"].copy()
    s["pt_key"] = s["pt"].str.upper()
    for exposure, background, terms, expected, kind, source in controls:
        keys = [t.upper() for t in terms]
        hit = s[(s["exposure"] == exposure) & (s["background"] == background) & s["pt_key"].isin(keys)]
        best = hit.sort_values("ror_lo", ascending=not expected).head(1)
        flagged = bool(hit[flag].any())
        rows.append({
            "kind": kind, "exposure": exposure, "background": background,
            "reaction": " / ".join(terms), "expected_signal": expected, "flagged": flagged,
            "passed": flagged == expected,
            "reports": int(hit["a"].sum()) if len(hit) else 0,
            "best_term": best["pt"].iloc[0] if len(best) else None,
            "ror": best["ror"].iloc[0] if len(best) else None,
            "ror_lo": best["ror_lo"].iloc[0] if len(best) else None,
            "ror_hi": best["ror_hi"].iloc[0] if len(best) else None,
            "source": source,
        })
    return pd.DataFrame(rows)


def run(sig):
    return check(sig, CONTROLS + pick_negatives(sig))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--out", default=str(OUTPUTS / "validation.csv"))
    args = ap.parse_args()
    con = connect(args.db)
    sig = pd.read_sql("SELECT * FROM signals WHERE period = 'All years' AND background IN (?, ?)",
                      con, params=(ALL, SGLT2))
    con.close()

    res = run(sig)
    res.to_csv(args.out, index=False)
    with pd.option_context("display.width", 200, "display.max_colwidth", 45):
        print(res[["kind", "exposure", "background", "reaction", "expected_signal", "flagged",
                   "reports", "ror", "ror_lo"]].to_string(index=False))

    n_neg = (res["kind"] == "Negative").sum()
    if n_neg < N_NEGATIVE:
        print(f"\nOnly {n_neg} negative candidates had {MIN_NEGATIVE_REPORTS}+ reports.")
    must = res[res["kind"] != "Negative"]
    fail = must[~must["passed"]]
    neg_fail = res[(res["kind"] == "Negative") & ~res["passed"]]
    if len(neg_fail):
        print(f"\nWarning: {len(neg_fail)} negative control(s) flagged; look at them before publishing.")
    if len(fail):
        print(f"\nFAILED: {len(fail)} positive control(s) or comparator check(s) did not behave as expected.")
        sys.exit(1)
    print("\nAll positive controls and comparator checks passed.")


if __name__ == "__main__":
    main()

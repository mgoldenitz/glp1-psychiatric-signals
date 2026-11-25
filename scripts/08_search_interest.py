"""Compare US Google search interest in semaglutide brands with FAERS suicidality reports.

Question: did semaglutide suicidality reports jump in 2023 Q3 because more people
used the drug, or because of the July 2023 news about suicidal thoughts?
Search interest is a rough stand-in for public attention to the drug.

Input
    data/google_trends_us.csv     monthly Google Trends values, US, Jan 2019 to Nov 2026
                                  (fetched once on 2026-11-25 through SerpApi; values are
                                  relative, 0 to 100, where 100 is the busiest month for
                                  any term in the same request)
    outputs/reports_by_quarter.csv  written by 07_export.py

Output
    outputs/search_vs_reports.csv  one row per quarter
    images/search_vs_reports.png   the chart for the README

Run from the repo root:  python scripts/08_search_interest.py
"""

from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
SUICIDALITY = "Suicidal and self-injurious behaviour"


def quarterly_search(trends):
    """Average the monthly values per quarter. Ozempic and Wegovy are both semaglutide."""
    trends = trends.copy()
    trends["quarter"] = pd.PeriodIndex(trends["month"], freq="Q").astype(str)
    trends["semaglutide_search"] = trends["Ozempic"] + trends["Wegovy"]
    return trends.groupby("quarter", as_index=False)["semaglutide_search"].mean().round(1)


def semaglutide_reports(reports):
    """Semaglutide suicidality reports per quarter. A missing quarter means zero reports."""
    rows = reports[(reports["exposure"] == "semaglutide") & (reports["measure"] == SUICIDALITY)]
    return rows[["quarter", "reports"]].rename(columns={"reports": "suicidality_reports"})


def build_table(trends, reports):
    table = quarterly_search(trends).merge(semaglutide_reports(reports), on="quarter", how="left")
    table["suicidality_reports"] = table["suicidality_reports"].fillna(0).astype(int)
    # Drop quarters after the last FAERS quarter loaded, so they do not show as zero reports.
    return table[table["quarter"] <= reports["quarter"].max()].reset_index(drop=True)


def plot(table, path):
    import matplotlib
    matplotlib.use("Agg")  # no screen needed
    import matplotlib.pyplot as plt

    fig, left = plt.subplots(figsize=(10, 4.5))
    x = range(len(table))
    left.bar(x, table["suicidality_reports"], color="#c0504d", label="FAERS suicidality reports")
    left.set_ylabel("Semaglutide suicidality reports")
    right = left.twinx()
    right.plot(x, table["semaglutide_search"], color="#1f4e79", linewidth=2,
               label="Search interest: Ozempic + Wegovy")
    right.set_ylabel("Google search interest (relative)")
    right.set_ylim(bottom=0)

    news = list(table["quarter"]).index("2023Q3")
    left.axvline(news, color="grey", linestyle="--")
    left.annotate("July 2023: news reports of\nsuicidal thoughts", (news, left.get_ylim()[1] * 0.9),
                  xytext=(-8, 0), textcoords="offset points", ha="right", fontsize=9)

    ticks = [i for i, q in enumerate(table["quarter"]) if q.endswith("Q1")]
    left.set_xticks(ticks, [table["quarter"][i][:4] for i in ticks])
    lines = left.get_legend_handles_labels()
    more = right.get_legend_handles_labels()
    left.legend(lines[0] + more[0], lines[1] + more[1], loc="upper left", frameon=False)
    left.set_title("Semaglutide: US search interest and FAERS suicidality reports by quarter")
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main():
    trends = pd.read_csv(REPO / "data" / "google_trends_us.csv")
    reports = pd.read_csv(REPO / "outputs" / "reports_by_quarter.csv")
    table = build_table(trends, reports)
    table.to_csv(REPO / "outputs" / "search_vs_reports.csv", index=False)
    plot(table, REPO / "images" / "search_vs_reports.png")
    print(table[table["quarter"].between("2022Q3", "2024Q2")].to_string(index=False))


if __name__ == "__main__":
    main()

"""Check that 08_search_interest.py averages months into quarters and fills missing quarters with zero."""

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("search_interest", ROOT / "scripts" / "08_search_interest.py")
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)


def test_build_table():
    trends = pd.DataFrame({
        "month": ["2023-04", "2023-05", "2023-06", "2023-07", "2023-08", "2023-09", "2023-10"],
        "Ozempic": [10, 20, 30, 40, 50, 60, 70],
        "Wegovy": [0, 0, 0, 5, 5, 5, 5],
    })
    reports = pd.DataFrame({
        "exposure": ["semaglutide", "semaglutide", "tirzepatide"],
        "quarter": ["2023Q3", "2023Q2", "2023Q3"],
        "reports": [93, 999, 7],
        "measure": ["Suicidal and self-injurious behaviour", "All reports",
                    "Suicidal and self-injurious behaviour"],
    })
    table = search.build_table(trends, reports)
    # 2023Q4 is after the last FAERS quarter, so it is dropped
    assert list(table["quarter"]) == ["2023Q2", "2023Q3"]
    assert list(table["semaglutide_search"]) == [20.0, 55.0]
    assert list(table["suicidality_reports"]) == [0, 93]

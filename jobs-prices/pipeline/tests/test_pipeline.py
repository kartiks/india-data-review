"""Unit tests for the readers and rules, plus an end-to-end run of the checks on the saved data."""

from pathlib import Path

import pytest

from jobs_prices_pipeline import build, checks

ROOT = Path(__file__).resolve().parents[2]


def test_month_of_agricultural_year():
    # The Labour Bureau's CPI-AL/RL years run July to June.
    assert build.ym({"year": "2024-2025", "month": "July"}) == "2024-07"
    assert build.ym({"year": "2024-2025", "month": "March"}) == "2025-03"
    assert build.ym({"year": 2025, "month": "December"}) == "2025-12"


def test_numbers_and_missing_markers():
    assert build.number("12.5") == 12.5
    assert build.number("NaN") is None
    assert build.number("l0.8") is None  # transcription error in MoSPI's data
    assert "**" in build.MISSING and "-" in build.MISSING


def test_worker_ratio_identity():
    ok = {"lfpr": 59.3, "wpr": 57.4, "ur": 3.1}
    gap, tol = build.identity_gap(ok)
    assert gap <= tol
    bad = {"lfpr": 46.5, "wpr": 42.4, "ur": 21.6}  # Apr-Jun 2019 urban, as in MoSPI's data service
    gap, _ = build.identity_gap(bad)
    assert gap > build.SMALL_GAP


def test_flag_rates_leaves_out_inconsistent_combinations():
    base = {"frequency": "annual", "year": "2025", "period": "", "state": "X", "sector": "urban", "age": "15 years and above",
            "status": "PS+SS", "religion": "all", "social_group": "all", "education": "all", "left_out": ""}
    rows = [
        {**base, "gender": "person", "lfpr": 50.0, "wpr": 47.5, "ur": 5.0, "lfpr_as_printed": "50", "wpr_as_printed": "47.5", "ur_as_printed": "5"},
        {**base, "gender": "male", "lfpr": 70.0, "wpr": 60.0, "ur": 5.0, "lfpr_as_printed": "70", "wpr_as_printed": "60", "ur_as_printed": "5"},
        {**base, "gender": "female", "lfpr": None, "wpr": 20.0, "ur": 5.0, "lfpr_as_printed": "2O", "wpr_as_printed": "20", "ur_as_printed": "5"},
    ]
    build.flag_rates(rows)
    assert rows[0]["left_out"] == ""
    assert rows[1]["left_out"].startswith("inconsistent")  # 70 x 0.95 = 66.5, published 60
    assert rows[2]["left_out"].startswith("not a number")


def test_fractile_order_skips_all():
    classes = {"0-5": 1, " 5-10": 2, "10-20": 3, "20-30": 4, "30-40": 5, "40-50": 6, "50-60": 7, "60-70": 8, "70-80": 9,
               "80-90": 10, "90-95": 11, "95-100": 12, "All": 99}
    assert checks.order_fractiles(classes) == list(range(1, 13))


def test_compact_table_round_trip():
    t = build.table(["state", "value"], [["Bihar", 1.5], ["Assam", None], ["Bihar", 2.0]])
    rows = [[t["labels"][f][v] if f in t["labels"] and v is not None else v for f, v in zip(t["fields"], r)] for r in t["rows"]]
    assert rows == [["Bihar", 1.5], ["Assam", None], ["Bihar", 2.0]]


@pytest.mark.skipif(not (ROOT / "sources" / "manifest.json").exists(), reason="sources not downloaded")
def test_checks_pass_on_saved_data():
    assert checks.main() == 0

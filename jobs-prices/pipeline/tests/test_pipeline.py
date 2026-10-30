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


def test_release_table_reader():
    from jobs_prices_pipeline import cpi2024

    html = """<h2>PRESS RELEASE OF CONSUMER PRICE INDEX ON BASE 2024=100 FOR MAY, 2026</h2>
    <p>Year-on-year inflation rate based on All India Consumer Price Index (CPI) with base year 2024 for the month of May,
    2026 over May, 2025 is 3.93%(Provisional). Corresponding inflation rates for rural and urban are 4.25% and 3.53%, respectively.</p>
    <table><tr><td></td><td>May, 2026 (Provisional)</td><td>April, 2026 (Final)</td></tr>
    <tr><td>Inflation (%)</td><td>CPI (General)</td><td>4.25</td><td>3.53</td><td>3.93</td><td>3.74</td><td>3.16</td><td>3.48</td></tr>
    <tr><td>CFPI</td><td>4.85</td><td>4.66</td><td>4.78</td><td>4.26</td><td>4.1`0</td><td>4.20</td></tr></table>
    <table><tr><td>S.No.</td><td>State/UT</td><td>CPI</td><td>Inflation</td><td></td></tr>
    <tr><td></td><td>Andhra Pradesh</td><td>106.04</td><td>106.10</td><td>106.06</td><td>5.09</td><td>4.80</td><td>4.97</td><td></td></tr>
    <tr><td></td><td>Uttar Pradesh</td><td>106.24</td><td>105.58</td><td>106.03</td><td>4.30</td><td>4.10</td><td>4.20</td><td></td></tr>
    <tr><td></td><td>Chandigarh*</td><td>-</td><td>104.98</td><td>104.98</td><td>-</td><td>3.10</td><td>3.10</td></tr></table>"""
    r = cpi2024.parse(html, "2026-05")
    assert r["headline"]["combined"] == 3.93 and r["headline"]["rural"] == 4.25
    assert r["summary"]["current"]["general_inflation"] == [4.25, 3.53, 3.93]  # column order read from the header
    assert r["summary"]["previous"]["general_inflation"] == [3.74, 3.16, 3.48]
    assert any("`" in p for p in r["problems"])  # the stray backtick is reported, not read as a number
    assert [s["name"] for s in r["states"]] == ["Andhra Pradesh", "Uttar Pradesh", "Chandigarh"]  # trailing empty cells dropped
    assert r["states"][2]["values"][0] is None

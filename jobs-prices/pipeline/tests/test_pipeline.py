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
def test_checks_pass_on_saved_data(data_dir):
    # data_dir (conftest) is under tmp_path: the committed data/ is never rewritten.
    committed = {p.name: p.stat().st_mtime_ns for p in (ROOT / "data").iterdir()}
    assert checks.main() == 0
    assert (data_dir / "validation_summary.json").exists()
    assert {p.name: p.stat().st_mtime_ns for p in (ROOT / "data").iterdir()} == committed


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
    # ... and only that figure is missing: the rest of the row is read
    assert r["summary"]["current"]["cfpi_inflation"] == [4.85, 4.66, 4.78]
    assert r["summary"]["previous"]["cfpi_inflation"] == [4.26, None, 4.20]
    assert [s["name"] for s in r["states"]] == ["Andhra Pradesh", "Uttar Pradesh", "Chandigarh"]  # trailing empty cells dropped
    assert r["states"][2]["values"][0] is None


def test_rbi_cells():
    from jobs_prices_pipeline import rbi

    assert rbi.cell(61) == (61.0, "61", "")
    assert rbi.cell("81*") == (81.0, "81*", "footnote")
    assert rbi.cell("-")[2] == "not available"
    assert rbi.cell(".")[2] == "not applicable"
    assert rbi.cell("n/a")[2] == "unreadable"


def test_rbi_table_links():
    from jobs_prices_pipeline import rbi

    page = ("<h2>Handbook of Statistics on Indian States 2024-25</h2><tr><td><a class='link2' href=PublicationsView.aspx?id=23470>"
            "Table 21: Gross State Domestic Product (Current Prices)</a></td><td><a href='https://rbidocs.rbi.org.in/rdocs/"
            "Publications/DOCs/21T_1112.XLSX'>x</a></td></tr>")
    edition, links = rbi.table_links(page)
    assert edition == "2024-25"
    assert links[21] == ("Table 21: Gross State Domestic Product (Current Prices)", "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/21T_1112.XLSX")


def test_cfpi_final_figures_replace_provisional_ones_figure_by_figure():
    def release(month, current, previous=None):
        summary = {"current": {"cfpi_index": current}}
        if previous is not None:
            summary["previous"] = {"cfpi_index": previous}
        return {"summary": summary, "source": f"cpi2024/{month}"}

    cfpi = build.cfpi_by_month({
        "2026-05": release("2026-05", [105.0, 105.8, 105.3]),
        "2026-06": release("2026-06", [106.8, 107.7, 107.1], previous=[105.1, 105.8, 105.4]),
        "2026-07": release("2026-07", [109.2, 109.7, None], previous=[106.9, None, 107.2]),  # a figure not printed as a number
        "2026-08": release("2026-08", [110.7, 110.7, 110.7], previous=None),  # no final figures at all
    })
    assert cfpi["2026-05"] == {"index": [105.1, 105.8, 105.4], "inflation": None, "provisional": True, "source": "cpi2024/2026-06"}
    # Final where the next release gives it, provisional otherwise, and still marked provisional
    assert cfpi["2026-06"]["index"] == [106.9, 107.7, 107.2] and cfpi["2026-06"]["provisional"] is True
    assert cfpi["2026-07"] == {"index": [109.2, 109.7, None], "inflation": None, "provisional": True, "source": "cpi2024/2026-07"}
    assert cfpi["2026-08"]["provisional"] is True


def test_cfpi_complete_final_figures_are_final():
    rel = {"2026-01": {"summary": {"current": {"cfpi_index": [1.0, 2.0, 3.0], "cfpi_inflation": [4.0, 5.0, 6.0]}}, "source": "a"},
           "2026-02": {"summary": {"current": {}, "previous": {"cfpi_index": [1.1, 2.1, 3.1], "cfpi_inflation": [4.1, 5.1, 6.1]}},
                       "source": "b"}}
    assert build.cfpi_by_month(rel)["2026-01"] == {"index": [1.1, 2.1, 3.1], "inflation": [4.1, 5.1, 6.1], "provisional": False, "source": "b"}


def test_site_json_shows_annual_job_conditions_and_earnings_only():
    # MoSPI's data service lists quarterly and monthly frequencies for indicators 5-8; once it fills them, their
    # rows must not merge into the site's annual figures (whose keys have no period).
    def row(freq, period, value, **kw):
        return {"frequency": freq, "year": "2024", "year_type": "", "period": period, "state": "All India", "sector": "rural",
                "gender": "male", "age": "", "status": "", "value": value, **kw}

    plfs = {"indicators": {}, "rates": [], "distribution": [],
            "conditions": [row("annual", "", 50.0, condition="no written contract"),
                           row("quarterly", "Q2", 51.0, condition="no written contract")],
            "earnings": [row("annual", "", 20000.0, kind="regular"), row("monthly", "07", 21000.0, kind="regular"),
                         row("quarterly", "Q3", 22000.0, kind="regular")]}
    ds = {"description": "", "generated_at": "", "sources": {}, "plfs": plfs, "cpi": [], "cpialrl": [], "hces": [],
          "cpi2024": {"releases": {}, "latest": None, "series": [], "cfpi": {}, "linking": {}, "weights": []},
          "rbi": [], "rbi_editions": {}, "hces_overall": [], "source_problems": []}
    site = build.site_json(ds)["plfs"]
    for kind, value in (("conditions", 50.0), ("earnings", 20000.0)):
        assert [r[-1] for r in site[kind]["rows"]] == [value]

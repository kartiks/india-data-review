"""Ministry/department spending: parser edge cases and figures confirmed on the page images."""

import csv
from pathlib import Path

import pytest

from budget_pipeline import ministries as M

RAW = Path(__file__).resolve().parents[2] / "sources" / "raw"
DATA = Path(__file__).resolve().parents[2] / "data"


def parse(budget: str, ext: str = "pdf") -> dict:
    p = M.parse_file(RAW / budget / f"ministries.{ext}", int(budget[:4]), ext)
    M.assign_ids(budget, p, M.load_name_map())
    return p


def line(p: dict, item_id: str) -> dict:
    return next(it for it in p["items"] if it["item_id"] == item_id)


def test_glued_numbers_are_split():
    # Budget 2000-01 prints "5200.35" and "1477.00" with no gap between them.
    assert M._split_number("5200.351477.00") == ["5200.35", "1477.00"]
    assert M._split_number("66817.77212547.53") == ["66817.77", "212547.53"]
    assert M._split_number("Revenue") is None


def test_glued_numbers_land_in_the_right_columns():
    agri = line(parse("2000-01"), "agriculture")
    assert agri["periods"][0]["total"] == 5200.35  # Actual 1998-99
    assert agri["periods"][1]["plan"] == 1477.00  # RE 1999-2000
    assert agri["periods"][2]["total"] == 6140.97  # BE 2000-01


def test_blank_cells_stay_blank():
    # Pharmaceuticals is new in Budget 2009-10: Actual and RE cells are blank (seen on the page).
    ph = line(parse("2009-10"), "pharmaceuticals")
    assert [p["total"] for p in ph["periods"]] == [None, None, 190.33]
    assert ph["revenue_line"][2] == {"plan": 125.25, "non_plan": 35.01, "total": 160.26}


def test_department_named_revenue_is_not_a_revenue_line():
    p = parse("2000-01")
    rev = line(p, "revenue")
    assert rev["level"] == "department"
    assert rev["periods"][0]["total"] == 1957.95


def test_demand_era_values_match_page():
    # Budget 2026-27, Demand No. 1 (confirmed on the page image).
    d = line(parse("2026-27"), "agriculture")
    assert d["demand_no"] == 1
    assert [p["total"] for p in d["periods"]] == [129933.47, 127290.16, 123089.30, 130561.38]
    assert d["subs"]["central_sector_schemes"][3]["total"] == 108660.82


def test_excel_spacer_column_does_not_shift_values():
    # The 2026-27 Excel file has an empty column before the last Total.
    pdf, xlsx = line(parse("2026-27"), "agriculture"), line(parse("2026-27", "xlsx"), "agriculture")
    assert pdf["periods"] == xlsx["periods"]


def test_source_errors_are_kept_as_printed():
    # Union Territories subtotal, Capital line, RE 2011-12 Non-Plan: printed 3679.04 (should be -55.46).
    ut = next(it for it in parse("2012-13")["items"] if it["name"].startswith("III. UNION TERRITORIES"))
    assert ut["capital_line"][2]["non_plan"] == 3679.04
    # Budget 2023-24 grand-total block: Central Sector Schemes revenue 2021-22 printed 74188.47.
    g = line(parse("2023-24"), "grand_total")
    assert g["subs"]["central_sector_schemes"][0]["revenue"] == 74188.47


def test_name_map_handles_health_2006_07():
    # Budget 2006-07 prints the merged Health and Family Welfare department as "Health".
    assert line(parse("2006-07"), "health_family_welfare")["label_as_printed"] == "Health"
    assert line(parse("2005-06"), "health")["label_as_printed"] == "Health"


def test_unknown_name_fails_loudly():
    with pytest.raises(KeyError):
        M.lookup("Ministry of Imaginary Affairs", "2020-21", M.load_name_map())


@pytest.fixture(scope="module")
def everything():
    return M.load_all()


def test_every_budget_parses_in_every_format(everything):
    assert len(everything) == 27
    assert all(b["primary"] == "pdf" for b in everything.values())
    assert {k: b["errors"] for k, b in everything.items() if b["errors"]} == {}


def test_all_checks_pass(everything):
    summary = list(csv.DictReader((DATA / "observations.csv").open()))
    results = M.checks(everything, summary)
    failures = {title: fails for title, _, fails, _ in results if fails}
    assert failures == {}
    assert sum(n for _, n, _, _ in results) > 50000

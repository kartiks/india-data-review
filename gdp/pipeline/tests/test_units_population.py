"""population_read.read_rbi: the RBI handbook's macro-economic tables, split by base year. Read from the committed
tables (small xlsx files, the format this reader exists for) and from hand-made workbooks for the failure paths."""

import json
from pathlib import Path

import openpyxl
import pytest

from gdp_pipeline import population_read as read

ROOT = Path(__file__).resolve().parents[2]


def by(records):
    return {(r["prices"], r["base"]): r for r in records}


def test_the_committed_tables_read_as_published():
    manifest = json.loads((ROOT / "sources" / "manifest.json").read_text())
    records, problems = read.read_rbi(manifest)
    assert problems == []
    tables = by(records)
    assert set(tables) == {("cur", "2011-12"), ("cur", "2022-23"), ("con", "2011-12"), ("con", "2022-23")}
    old, new = tables[("cur", "2011-12")], tables[("cur", "2022-23")]
    # 2022-23 is printed under both bases, with different figures for each
    assert old["years"] == ["2020-21", "2021-22", "2022-23"] and new["years"] == ["2022-23", "2023-24", "2024-25",
                                                                                   "2025-26"]
    assert old["figures"]["gdp"]["2022-23"] == 26890473 and new["figures"]["gdp"]["2022-23"] == 26117627
    assert old["figures"]["population_lakh"]["2022-23"] == new["figures"]["population_lakh"]["2022-23"] == 13829
    assert new["figures"]["pc_pfce"]["2025-26"] == 138324
    assert set(new["figures"]) == {"population_lakh", "gdp", "gni", "nni", "pc_gdp", "pc_gni", "pc_nni", "pc_pfce"}
    assert "population_lakh" not in tables[("con", "2022-23")]["figures"]  # table 2 prints no population
    assert new["url"] == read.RBI_TABLES["cur"]["url"] and new["document"] == read.RBI_TABLES["cur"]["title"]


@pytest.fixture
def workbooks(tmp_path, monkeypatch):
    """Saves each table's rows (lists of cells) as an xlsx and returns the manifest pointing to them."""
    monkeypatch.setattr(read, "ROOT", tmp_path)

    def save(cur=None, con=None):
        manifest = {}
        for prices, rows in (("cur", cur), ("con", con)):
            if rows is None:
                continue
            wb = openpyxl.Workbook()
            for r in rows:
                wb.active.append(r)
            wb.save(tmp_path / f"{prices}.xlsx")
            manifest[read.RBI_TABLES[prices]["key"]] = {"file": f"{prices}.xlsx"}
        return manifest
    return save


HEAD = [None, "Item/Year", "2021-22", "2022-23", "2022-23", "2023-24"]
BASES = [None, None, "(Base Year: 2011-12)", None, "(Base Year: 2022-23)", None]


def test_tables_not_downloaded_are_problems(workbooks):
    records, problems = read.read_rbi(workbooks(cur=[HEAD, BASES, [None, "Gross Domestic Product", 1, 2, 3, 4]]))
    assert [r["prices"] for r in records] == ["cur", "cur"]
    assert problems == [f"{read.RBI_TABLES['con']['title']}: not downloaded"]


@pytest.mark.parametrize("rows", [
    [BASES, [None, "Gross Domestic Product", 1, 2, 3, 4]],  # no year row
    [HEAD, [None, "Gross Domestic Product", 1, 2, 3, 4]],  # no base-year row
])
def test_a_table_laid_out_differently_is_a_problem_not_a_guess(workbooks, rows):
    records, problems = read.read_rbi(workbooks(cur=rows, con=rows))
    assert records == []
    assert problems == [f"{read.RBI_TABLES[p]['title']}: layout changed (no year or base-year row)" for p in ("cur", "con")]


def test_a_table_without_any_known_row_is_a_problem(workbooks):
    rows = [HEAD, BASES, [None, "Gross Value of Output", 1, 2, 3, 4]]
    records, problems = read.read_rbi(workbooks(cur=rows, con=rows))
    assert records == [] and problems == [f"{read.RBI_TABLES[p]['title']}: no figures read" for p in ("cur", "con")]


def test_blank_or_dashed_cells_and_columns_that_are_not_years_are_skipped(workbooks):
    head = [*HEAD, "Growth (%)"]
    rows = [[None, "TABLE 1"], head, BASES,
            [None, "  Population (in Lakhs) ", 13686, 13829, 13829, "-", 1.1],
            [None, "Per Capita GDP (₹)", None, 194451, 188862, 207699, 7.0]]
    tables = by(read.read_rbi(workbooks(cur=rows))[0])
    assert tables[("cur", "2011-12")]["figures"] == {"population_lakh": {"2021-22": 13686.0, "2022-23": 13829.0},
                                                     "pc_gdp": {"2022-23": 194451.0}}
    assert tables[("cur", "2022-23")]["figures"] == {"population_lakh": {"2022-23": 13829.0},
                                                     "pc_gdp": {"2022-23": 188862.0, "2023-24": 207699.0}}
    assert tables[("cur", "2022-23")]["years"] == ["2022-23", "2023-24"]


def test_columns_before_the_first_base_year_label_are_not_read(workbooks):
    bases = [None, None, None, "(Base Year: 2011-12)", "(Base Year: 2022-23)", None]
    rows = [HEAD, bases, [None, "Gross Domestic Product", 1, 2, 3, 4]]
    tables = by(read.read_rbi(workbooks(cur=rows))[0])
    assert tables[("cur", "2011-12")]["figures"] == {"gdp": {"2022-23": 2.0}}  # 2021-22 has no base: left out
    assert tables[("cur", "2022-23")]["figures"] == {"gdp": {"2022-23": 3.0, "2023-24": 4.0}}

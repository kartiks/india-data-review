"""The RBI handbook reader's unit and sub-title checks, and the checks on the state GDP and income tables."""

import openpyxl
import pytest

from conftest import failures_of

from jobs_prices_pipeline import checks, rbi


def workbook(path, notes: list[str]) -> None:
    """One sheet laid out like the handbook's: title, notes in brackets, header row, states, a footnote."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "T8"
    ws.append([None, "TABLE 8: STATE-WISE UNEMPLOYMENT RATE"])
    for n in notes:
        ws.append([None, f"({n})"])
    ws.append([None, "State/Union Territory", "2022-23", "2023-24"])
    ws.append([1, "Andhra Pradesh", 41, "45*"])
    ws.append([2, "ALL INDIA", 24, "-"])
    ws.append([None, "Note: * provisional."])
    wb.save(path)


SPEC = rbi.RBI_STATE_TABLES[8]


def test_reader_takes_the_expected_unit_and_sub_title(tmp_path):
    workbook(tmp_path / "t.xlsx", ["Rural Male", "Per Thousands"])
    recs, problems = rbi.read_table(tmp_path / "t.xlsx", 8, SPEC)
    assert problems == []
    assert {(r["unit"], r["variant"]) for r in recs} == {("Per Thousands", "Rural Male")}
    assert [(r["state"], r["year"], r["value"], r["flag"]) for r in recs] == [
        ("Andhra Pradesh", "2022-23", 41.0, ""), ("Andhra Pradesh", "2023-24", 45.0, "footnote"),
        ("All India", "2022-23", 24.0, ""), ("All India", "2023-24", None, "not available")]


def test_reader_accepts_another_spelling_of_the_unit(tmp_path):
    workbook(tmp_path / "t.xlsx", ["Rural Female", "Per Thousand"])
    recs, problems = rbi.read_table(tmp_path / "t.xlsx", 8, SPEC)
    assert problems == [] and recs[0]["unit"] == "Per Thousands"


@pytest.mark.parametrize("notes, problem", [
    (["Rural Male", "Per cent"], "unit (Per Thousands) not found"),  # another unit would shift into the variant
    (["Rural Male"], "unit (Per Thousands) not found"),
    (["Rural Males", "Per Thousands"], "sub-title 'Rural Males' is not one of"),
    (["Per Thousands"], "sub-title '' is not one of"),
])
def test_reader_reports_an_unexpected_unit_or_sub_title(tmp_path, notes, problem):
    workbook(tmp_path / "t.xlsx", notes)
    _, problems = rbi.read_table(tmp_path / "t.xlsx", 8, SPEC)
    assert any(problem in p for p in problems), problems


def rbi_ds(rows, problems=()):
    return {"rbi": rows, "rbi_problems": list(problems), "rbi_editions": {8: "2024-25"}, "cpi": []}


def rec(table, state, year, value, **kw):
    spec = rbi.RBI_STATE_TABLES[table]
    return {"table": table, "table_id": spec.id, "variant": spec.variants[0], "unit": spec.unit, "state": state,
            "year": year, "value": value, **kw}


def test_check_rbi_fails_on_a_unit_or_variant_the_site_does_not_expect():
    states = [f"State {i}" for i in range(30)]
    ok = [rec(n, s, "2023-24", 1.0) for n in rbi.RBI_STATE_TABLES for s in states]
    assert failures_of(checks.check_rbi, rbi_ds(ok)) == []
    bad = ok + [rec(21, "Goa", "2023-24", 1.0, unit="₹ Crore"), rec(8, "Goa", "2023-24", 1.0, variant="Rural Overall Per cent")]
    fails = failures_of(checks.check_rbi, rbi_ds(bad))
    assert any("RBI table 21" in f and "₹ Crore" in f for f in fails)
    assert any("RBI table 8" in f and "Rural Overall Per cent" in f for f in fails)
    # and a reader problem is a failure
    assert failures_of(checks.check_rbi, rbi_ds(ok, ["Table 8 sheet T8: unit (Per Thousands) not found"]))


def income(state="Kerala", year="2022-23", gsdp_cur=1000.0, gsdp_const=600.0, pc_cur=2.0e5, pc_const=1.2e5):
    return [rec(21, state, year, gsdp_cur), rec(22, state, year, gsdp_const), rec(19, state, year, pc_cur),
            rec(20, state, year, pc_const)]


def test_check_rbi_income_passes_consistent_tables():
    rows = income(year="2011-12", gsdp_const=1000.0, pc_const=2.0e5) + income()
    assert failures_of(checks.check_rbi_income, rbi_ds(rows)) == []


@pytest.mark.parametrize("rows, message", [
    (income(year="2011-12", gsdp_const=990.0, pc_const=2.0e5 * 0.99), "(base year): current prices"),
    (income(year="2011-12", gsdp_const=1000.0, pc_const=2.0e5) + income(gsdp_cur=500.0, pc_cur=1.0e5),
     "below constant prices"),
    # GSDP at constant prices read from the current-price table's pair, per capita not: the ratio breaks
    (income(year="2011-12", gsdp_const=1000.0, pc_const=2.0e5) + income(gsdp_const=400.0), "GSDP ÷ per capita NSDP"),
    (income(), "no figures for the base year"),
])
def test_check_rbi_income_fails_on_inconsistent_tables(rows, message):
    fails = failures_of(checks.check_rbi_income, rbi_ds(rows))
    assert any(message in f for f in fails), fails

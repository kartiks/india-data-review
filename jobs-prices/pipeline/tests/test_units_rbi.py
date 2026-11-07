"""rbi.read_table on sheet layouts test_rbi.py leaves out (several sheets, years under the header, sheets it cannot
read), and rbi.read_all."""

import openpyxl
import pytest

from jobs_prices_pipeline import rbi

SPEC = rbi.RBI_STATE_TABLES[8]


def sheet(wb, title, rows):
    ws = wb.create_sheet(title)
    for r in rows:
        ws.append(r)


def save(path, sheets: dict[str, list[list]]):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        sheet(wb, title, rows)
    wb.save(path)
    return path


def head(variant="Rural Male", unit="Per Thousands", title="TABLE 8: STATE-WISE UNEMPLOYMENT RATE"):
    return [[None, title], [None, f"({variant})"], [None, f"({unit})"]]


def test_reads_every_sheet_with_years_on_the_row_under_the_header(tmp_path):
    path = save(tmp_path / "t.xlsx", {
        "T8": head() + [[None, "State/Union Territory", "Year"], [None, None, "2022-23", "2023-24"],
                        [1, "Bihar", 30, 31], [None, None], [None, "Source: PLFS"]],
        "T8 (2)": head(variant="Rural Female", title="TABLE 8: STATE-WISE UNEMPLOYMENT RATE (Contd.)")
                  + [[None, "State/Union Territory", None, "2023-24"], [1, "Bihar*", None, 12], [2, "All India", None, "."]],
    })
    recs, problems = rbi.read_table(path, 8, SPEC)
    assert problems == []
    assert [(r["sheet"], r["variant"], r["state"], r["year"], r["value"], r["flag"]) for r in recs] == [
        ("T8", "Rural Male", "Bihar", "2022-23", 30.0, ""), ("T8", "Rural Male", "Bihar", "2023-24", 31.0, ""),
        ("T8 (2)", "Rural Female", "Bihar", "2023-24", 12.0, ""),  # footnote mark on the name dropped
        ("T8 (2)", "Rural Female", "All India", "2023-24", None, "not applicable")]
    assert {r["title"] for r in recs} == {"TABLE 8: STATE-WISE UNEMPLOYMENT RATE"}  # '(Contd.)' dropped
    assert {(r["table"], r["table_id"], r["unit"]) for r in recs} == {(8, "unemployment_rural", "Per Thousands")}


def test_a_sheet_without_a_header_or_years_is_a_problem_and_the_others_are_read(tmp_path):
    path = save(tmp_path / "t.xlsx", {
        "Chart": [[None, "A chart"]],
        "NoYears": head() + [[None, "State/Union Territory", "Rural"], [None, None, "Male"], [1, "Bihar", 1]],
        "T8": head() + [[None, "State/Union Territory", "2023-24"], [1, "Bihar", 31]],
    })
    recs, problems = rbi.read_table(path, 8, SPEC)
    assert problems == ["Table 8 sheet Chart: no 'State/Union Territory' header",
                        "Table 8 sheet NoYears: no years in the header"]
    assert [(r["sheet"], r["value"]) for r in recs] == [("T8", 31.0)]


def unreadable(tmp_path):
    path = save(tmp_path / "t.xlsx", {"T8": head() + [[None, "State/Union Territory", "2023-24"], [1, "Bihar", "3l.5"]]})
    return rbi.read_table(path, 8, SPEC)


def test_an_unreadable_value_is_a_problem_and_kept_as_printed(tmp_path):
    recs, problems = unreadable(tmp_path)
    assert [(r["value"], r["value_as_printed"], r["flag"]) for r in recs] == [(None, "3l.5", "unreadable")]
    assert len(problems) == 1 and "Bihar 2023-24" in problems[0] and "'3l.5'" in problems[0]


@pytest.mark.xfail(strict=True, reason="rbi.read_table's problem for an unreadable value says 'is not a table_no' "
                                       "(a slip for 'is not a number')")
def test_an_unreadable_value_is_reported_as_not_a_number(tmp_path):
    _, problems = unreadable(tmp_path)
    assert problems[0].endswith("value '3l.5' is not a number")


def test_read_all_reads_each_downloaded_table_and_names_the_missing_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(rbi, "ROOT", tmp_path)
    monkeypatch.setattr(rbi, "RBI_STATE_TABLES", {8: SPEC, 9: rbi.RBI_STATE_TABLES[9], 21: rbi.RBI_STATE_TABLES[21]})
    save(tmp_path / "t8.xlsx", {"T8": head() + [[None, "State/Union Territory", "2023-24"], [1, "Bihar", 31]]})
    manifest = {"rbi/table008": {"file": "t8.xlsx", "edition": "2024-25"},
                "rbi/table021": {"url": "u", "empty": True}}
    recs, problems, editions = rbi.read_all(manifest)
    assert [(r["table"], r["state"], r["source"]) for r in recs] == [(8, "Bihar", "rbi/table008")]
    assert problems == ["RBI table 9 not downloaded", "RBI table 21 not downloaded"]
    assert editions == {8: "2024-25"}

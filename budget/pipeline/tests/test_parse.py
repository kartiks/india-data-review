"""Parser edge cases, each taken from a real document that once broke it."""

from pathlib import Path

import pytest

from budget_pipeline.parse import ParseError, expected_columns, match_field, parse_cell, parse_document
from budget_pipeline.readers import read_any

RAW = Path(__file__).resolve().parents[2] / "sources" / "raw"


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("100162 (4.3)", (True, 100162.0, 4.3)),  # HTML: amount and % of GDP in one cell
        ("140955*", (True, 140955.0, None)),  # footnote symbol
        ("...", (True, None, None)),  # not available
        ("", (True, None, None)),
        ("(-) 8047", (True, -8047.0, None)),  # negative written as (-)
        ("77425 (3.6 )", (True, 77425.0, 3.6)),  # stray space inside the brackets
        ("-(0.9)", (True, None, -0.9)),
        ("Estimates", (False, None, None)),  # text is not a value
    ],
)
def test_parse_cell(cell, expected):
    assert parse_cell(cell) == expected


@pytest.mark.parametrize(
    "label, field",
    [
        ("7. Borrowings and other liabilities$", "borrowings"),
        ("1 1 Revenue Receipts", "revenue_receipts"),  # spreadsheet: item numbers in their own cells
        ("18. Of Which, Grants for creation of Capital Assets", "grants_capital_assets"),
        ("21 (20-18)# 21 Effective Revenue Deficit (20-18)#", "effective_revenue_deficit"),
        ("BEEK 22 Fiscal Deficit", "fiscal_deficit"),  # leftovers of a Hindi label before the English one
        ("10. On Revenue Account", None),  # ambiguous on its own; resolved by position in the table
    ],
)
def test_match_field(label, field):
    assert match_field(label) == field


def test_unexpected_column_years_are_rejected():
    # The 2017-18 Excel header says "2016-2016" for the 2015-16 column: refuse rather than guess.
    with pytest.raises(ParseError):
        expected_columns("2016-2016 Actuals 2016-2017 Budget 2016-2017 Revised 2017-2018 Budget", 2017)


def test_five_columns_when_provisional_actuals_present():
    cols = expected_columns("2022-2023 2023-2024 2023-2024 2023-2024 2024-2025 Actuals Provisional Actuals", 2024)
    assert [(c.fiscal_year, c.kind) for c in cols] == [
        ("2022-23", "Actual"), ("2023-24", "BE"), ("2023-24", "RE"), ("2023-24", "PA"), ("2024-25", "BE"),
    ]


def values(doc_year: str, ext: str) -> dict:
    parsed = parse_document(read_any(RAW / doc_year / f"summary.{ext}"), int(doc_year[:4]), ext != "pdf")
    return {(o.field, o.fiscal_year, o.kind): o for o in parsed["observations"]}


def test_pdf_footnote_marker_is_not_glued_to_number():
    # Budget 2006-07 prints "62043" with a superscript "1"; naive text extraction gives 620431.
    assert values("2006-07", "pdf")[("recoveries_of_loans", "2004-05", "Actual")].value == 62043


def test_pdf_blank_cell_keeps_columns_aligned():
    # Budget 2011-12 leaves the 2009-10 grants cell blank; the other three must not shift left.
    v = values("2011-12", "pdf")
    assert v[("grants_capital_assets", "2009-10", "Actual")].value is None
    assert v[("grants_capital_assets", "2011-12", "BE")].value == 146853


def test_html_header_with_extra_cell_keeps_columns_aligned():
    # Budget 2003-04's header row has one more cell than its data rows.
    assert values("2003-04", "htm")[("total_expenditure", "2003-04", "BE")].value == 438795


def test_spreadsheet_percent_rows_are_attached_to_deficits():
    # Spreadsheets store "(4.8)" as -4.8 in an unlabeled row under the deficit.
    assert values("2014-15", "xls")[("fiscal_deficit", "2013-14", "BE")].pct_gdp == 4.8

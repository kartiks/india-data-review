"""The headline-table parser on small hand-made tables: minus signs printed as "(-)", % of GDP rows, the GDP the
budget states, and the errors it must raise rather than guess. (test_parse.py covers cases from real documents.)"""

import pytest

from budget_pipeline.parse import ParseError, parse_cell, parse_document, read_row_tokens, stated_gdp
from budget_pipeline.readers import PdfLine

HEADER = ["", "", "2008-2009 Actuals", "2009-2010 Budget Estimates", "2009-2010 Revised Estimates",
          "2010-2011 Budget Estimates"]


def table(*body):
    """A Budget 2010-11 headline table as spreadsheet cells: title, header, then body rows."""
    return [["Budget at a Glance"], HEADER, *body]


REVENUE = ["1.", "Revenue Receipts", "540259", "614497", "577294", "682212"]


def values(parsed):
    return {(o.field, o.fiscal_year, o.kind): (o.value, o.pct_gdp) for o in parsed["observations"]}


# ----- "(-)" is a minus sign -----------------------------------------------------------------------------------


@pytest.mark.parametrize("cell, expected", [
    ("(-)8047", (True, -8047.0, None)),
    ("(-) 8047 (0.1)", (True, -8047.0, 0.1)),  # amount and % in one cell: the sign is the amount's
    ("(-) (0.2)", (True, None, -0.2)),  # a negative percentage
    ("- (0.2)", (True, None, -0.2)),
    ("-", (True, None, None)),  # on its own a dash is "nil", not a sign
    ("(-)", (False, None, None)),  # a sign with nothing after it is not a value
])
def test_minus_signs_in_a_cell(cell, expected):
    assert parse_cell(cell) == expected


def test_pdf_minus_token_joins_the_number_after_it():
    # PDF text splits "(-) 1732" into two tokens: one more token than columns, so "(-)" is a sign.
    row = read_row_tokens(["Primary Deficit", "(-)", "1732", "500", "600", "700"], 4, None)
    assert row.amounts == [-1732, 500, 600, 700]
    row = read_row_tokens(["Revenue Deficit", "(-)", "(0.2)", "(0.3)", "(0.1)", "(0.4)"], 4, None)
    assert (row.amounts, row.pcts) == ([], [-0.2, 0.3, 0.1, 0.4])


def test_pdf_lone_dash_with_as_many_tokens_as_columns_is_nil():
    row = read_row_tokens(["Other receipts", "-", "500", "600", "700"], 4, None)
    assert row.amounts == [None, 500, 600, 700]


def test_pdf_numbers_go_to_the_nearest_column():
    line = PdfLine(["Grants for creation of capital assets", "500", "700"])
    line.xs = [300.0, 500.0]
    row = read_row_tokens(line, 4, [300.0, 400.0, 500.0, 600.0])
    assert row.amounts == [500, None, 700, None]
    # A number far from every value column (a year in a note, say) means the line is not a data row.
    line.xs = [300.0, 800.0]
    assert read_row_tokens(line, 4, [300.0, 400.0, 500.0, 600.0]) is None


def test_text_in_a_value_position_is_not_a_data_row():
    assert read_row_tokens(["Notes", "see", "below"], 4, None) is None


# ----- parse_document on a hand-made table ----------------------------------------------------------------------


def test_table_with_negative_deficits_and_percent_rows():
    parsed = parse_document(table(
        REVENUE,
        ["2.", "Tax Revenue (net to centre)", "443319", "474218", "465103", "534094"],
        ["3.", "Non-Plan Expenditure", "1", "2", "3", "4"],  # known, not published
        ["4.", "Mystery line", "1", "2", "3", "4"],  # unknown: listed for a person to look at
        ["5.", "Fiscal Deficit", "336992", "400996", "414041", "381408"],
        ["", "", "(6.0)", "(6.8)", "(6.7)", "(5.5)"],
        ["6.", "Primary Deficit", "(-) 1732", "-", "(-) 500", "600"],
        ["", "", "(0.1)", "...", "(0.2)", "(0.3)"],  # a surplus printed as a positive % of GDP
        ["Note: 1. The figures are rounded."],
        ["", "GDP for BE 2010-2011 has been projected at ₹ 69,34,700 crore"],
    ), 2010, True)
    v = values(parsed)
    assert [(c.fiscal_year, c.kind) for c in parsed["columns"]] == [
        ("2008-09", "Actual"), ("2009-10", "BE"), ("2009-10", "RE"), ("2010-11", "BE")]
    assert v[("fiscal_deficit", "2010-11", "BE")] == (381408, 5.5)
    assert v[("primary_deficit", "2008-09", "Actual")] == (-1732, -0.1)
    assert v[("primary_deficit", "2009-10", "BE")] == (None, None)
    assert v[("primary_deficit", "2009-10", "RE")] == (-500, -0.2)
    assert v[("primary_deficit", "2010-11", "BE")] == (600, 0.3)
    assert {f for f, _, _ in v} == {"revenue_receipts", "tax_revenue_net", "fiscal_deficit", "primary_deficit"}
    assert parsed["unknown_rows"] == ["'4. Mystery line' -> [1.0, 2.0, 3.0, 4.0]"]
    assert parsed["gdp"]["value"] == 6934700
    assert parsed["gdp"]["fiscal_year"] == "2010-2011"


def test_table_without_revenue_receipts_is_refused():
    with pytest.raises(ParseError, match="Revenue Receipts"):
        parse_document(table(["5.", "Fiscal Deficit", "336992", "400996", "414041", "381408"]), 2010, True)


def test_header_for_another_budget_is_refused():
    with pytest.raises(ParseError, match="unexpected column years"):
        parse_document(table(REVENUE), 2011, True)


def test_line_item_printed_twice_is_refused():
    with pytest.raises(ParseError, match="appears twice"):
        parse_document(table(REVENUE, REVENUE), 2010, True)


def test_pdf_line_with_a_missing_value_is_refused():
    rows = [["2008-2009 2009-2010 2009-2010 2010-2011"], ["1. Revenue Receipts", "540259", "614497", "577294", "682212"],
            ["2. Tax Revenue", "443319", "474218", "534094"]]
    with pytest.raises(ParseError, match="has 3 values, expected 4"):
        parse_document(rows, 2010, False)


def test_percent_row_with_a_missing_value_is_refused():
    rows = [["2008-2009 2009-2010 2009-2010 2010-2011"], ["1. Revenue Receipts", "540259", "614497", "577294", "682212"],
            ["5. Fiscal Deficit", "336992", "400996", "414041", "381408"], ["", "(6.8)", "(6.7)", "(5.5)"]]
    with pytest.raises(ParseError, match="% of GDP values under fiscal_deficit"):
        parse_document(rows, 2010, False)


# ----- the GDP the budget states (parse.stated_gdp) -------------------------------------------------------------


@pytest.mark.parametrize("text, year, value", [
    ("GDP for BE 2023-2024 has been projected at ₹3,01,75,065 crore assuming 10.5% growth over the estimated "
     "Nominal GDP of ₹2,73,07,751 crore", "2023-2024", 30175065),
    ("GDP for BE 2016-2017 has been projected at ` 1,50,65,010 crore", "2016-2017", 15065010),  # ₹ printed as `
    # Bilingual page: the Hindi words around the sentence are dropped.
    ("सकल घरेलू उत्पाद GDP for BE 2024-2025 has been projected at ₹ 3,26,36,912 crore अनुमान", "2024-2025",
     32636912),
])
def test_stated_gdp(text, year, value):
    gdp = stated_gdp(text)
    assert (gdp["fiscal_year"], gdp["value"]) == (year, value)
    assert gdp["text"].startswith("GDP for BE") and gdp["text"].endswith("crore")  # the base GDP is not read
    assert gdp["text"].isascii()


@pytest.mark.parametrize("text", ["Fiscal deficit as 5.9 per cent of GDP", "GDP for BE 2010-2011 has been projected",
                                  ""])
def test_no_stated_gdp(text):
    assert stated_gdp(text) is None

"""Tax breakdown (Budget at a Glance "Receipts" table): edge cases and published figures."""

from pathlib import Path

import pytest

from budget_pipeline.parse import ParseError
from budget_pipeline.readers import read_any
from budget_pipeline.taxes import (
    checks,
    load_all,
    load_summary_observations,
    match_item,
    parse_receipts,
    receipts_columns,
)

RAW = Path(__file__).resolve().parents[2] / "sources" / "raw"


@pytest.fixture(scope="module")
def taxes():
    return load_all()


def value(taxes, budget, item, year, kind):
    p = taxes["budgets"][budget]["parsed"]
    it = next(i for i in p["items"] if i["item_id"] == item)
    col = next(c for c, k in enumerate(p["columns"]) if (k.fiscal_year, k.kind) == (year, kind))
    return it["values"][col]


@pytest.mark.parametrize(
    "label, item",
    [
        ("B E B E - V Gross Tax Revenue", "gross_tax_revenue"),  # Hindi leftovers before the English label
        ("b. Taxes on Income", "income_tax"),
        ("Income-Tax", "income_tax"),
        ("Interest-Tax", "interest_tax"),  # not income tax
        ("- -GST Compensation Cess", "gst_compensation_cess"),  # not GST total
        ("g. GST", "gst"),
        ("Less - State s share", "states_share"),
        ("Less-States' share adjustment for prior years in RE", "states_share_adjustment"),
        ("Less surcharge on Union taxes/duties transferred to the National Calamity Contingency Fund",
         "nccd_transferred"),
        ("- Other Non Tax Revenue", "other_non_tax"),  # not the non-tax total
        ("2. Non-Tax Revenue", "non_tax_revenue_total"),
        ("1a Centre s Net Tax", "net_tax_revenue"),  # "Revenue" wraps to the next line
        ("Total- Revenue", "revenue_receipts_total"),  # "Receipts (1a + 2)" wraps to the next line
        ("Receipts of Union", "ut_non_tax_receipts"),
        ("h. Taxes of Union", "ut_taxes"),
    ],
)
def test_match_item(label, item):
    assert match_item(label) == item


def test_three_column_layout_before_2010():
    cols = receipts_columns("1999-2000 Budget Estimates 1999-2000 Revised Estimates 2000-2001 Budget Estimates", 2000)
    assert [(c.fiscal_year, c.kind) for c in cols] == [("1999-00", "BE"), ("1999-00", "RE"), ("2000-01", "BE")]


def test_unexpected_years_are_rejected():
    with pytest.raises(ParseError):
        receipts_columns("2016-2016 Actuals 2016-2017 Budget 2016-2017 Revised 2017-2018 Budget", 2017)


def test_wrong_table_is_rejected():
    # Deficit Statistics (once mistaken for the Receipts table) has no gross tax line.
    with pytest.raises(ParseError):
        parse_receipts([["Deficit Statistics"], ["1. Fiscal Deficit", "532791"]], 2017, True)


def test_states_share_split_is_not_a_gross_tax(taxes):
    # Budget 2000-01 lists "Income-Tax" twice: as a tax, and again as part of the states' share.
    assert value(taxes, "2000-01", "income_tax", "2000-01", "BE") == 31590
    assert value(taxes, "2000-01", "states_share_of:income_tax", "2000-01", "BE") == 19774


def test_blank_cell_stays_in_its_column(taxes):
    # Budget 2024-25: wealth tax has an Actual but '..' elsewhere; the Provisional Actuals cell is blank.
    assert value(taxes, "2024-25", "wealth_tax", "2022-23", "Actual") == -9
    assert value(taxes, "2024-25", "wealth_tax", "2023-24", "PA") is None


def test_four_dot_not_available_marker(taxes):
    # Budget 2020-21 PDF prints "28945 28000 .... ...." for IGST.
    assert value(taxes, "2020-21", "igst", "2018-19", "Actual") == 28945
    assert value(taxes, "2020-21", "igst", "2020-21", "BE") is None


def test_wrapped_states_share_adjustment(taxes):
    # Budget 2025-26: "Less- States' share" / "adjustment for prior years in RE" is its own deduction.
    assert value(taxes, "2025-26", "states_share", "2024-25", "RE") == 1274121
    assert value(taxes, "2025-26", "states_share_adjustment", "2024-25", "RE") == 12764


@pytest.mark.parametrize(
    "budget, item, year, kind, expected",
    [
        # PRS Union Budget Analysis 2026-27, Table 2 (from Receipts Budget 2026-27)
        ("2026-27", "corporation_tax", "2026-27", "BE", 1231000),
        ("2026-27", "income_tax", "2026-27", "BE", 1466000),
        ("2026-27", "states_share", "2026-27", "BE", 1526255),
        ("2026-27", "customs", "2025-26", "RE", 258290),
        ("2026-27", "gross_tax_revenue", "2024-25", "Actual", 3796382),
        ("2026-27", "cgst", "2025-26", "BE", 1010890),
    ],
)
def test_published_figures(taxes, budget, item, year, kind, expected):
    assert value(taxes, budget, item, year, kind) == expected


def test_every_budget_has_a_receipts_table(taxes):
    assert len(taxes["budgets"]) == 27


def test_all_tax_checks_pass(taxes):
    results = checks(taxes, load_summary_observations())
    failures = [f for _, _, fs, _ in results for f in fs]
    assert failures == []


# ----- Receipt Budget Annex 7: tax actuals 2000-01..2007-08 -----

from budget_pipeline.taxes import annex7_columns, observations  # noqa: E402


def rb_value(taxes, budget, item, kind="Actual"):
    p = taxes["receipt_budgets"][budget]["parsed"]
    it = next(i for i in p["items"] if i["item_id"] == item)
    col = next(c for c, k in enumerate(p["columns"]) if k.kind == kind)
    return it["values"][col]


def test_annex7_glued_header_years():
    # Receipt Budget 2008-09 prints "1999-20002000-2001 ..." in its header.
    from budget_pipeline.taxes import annex7_header_text

    text = annex7_header_text(RAW / "2008-09" / "receipt_budget.pdf")
    cols = annex7_columns(text, 2008)
    assert [(c.fiscal_year, c.kind) for c in cols[-3:]] == [("2006-07", "Actual"), ("2007-08", "RE"), ("2008-09", "BE")]


def test_annex7_small_font_header_is_read():
    # Receipt Budget 2009-10 prints its column headings under 7pt (dropped by the shared reader).
    from budget_pipeline.taxes import annex7_header_text

    assert "2007-2008" in annex7_header_text(RAW / "2009-10" / "receipt_budget.pdf")


def test_annex7_income_tax_not_corporation_tax(taxes):
    # "2. Taxes on Income other / than Corporation Tax" wraps; it must not be read as corporation tax.
    assert rb_value(taxes, "2002-03", "income_tax") == 31764
    assert rb_value(taxes, "2002-03", "corporation_tax") == 35696


@pytest.mark.parametrize(
    "budget, item, expected",
    [
        ("2002-03", "net_tax_revenue", 136916),  # = headline Actual 2000-01 in Budget at a Glance 2002-03
        ("2007-08", "gross_tax_revenue", 366152),  # Actual 2005-06
        ("2009-10", "corporation_tax", 192911),  # Actual 2007-08
        ("2009-10", "states_share", 151800),
    ],
)
def test_annex7_actuals(taxes, budget, item, expected):
    assert rb_value(taxes, budget, item) == expected


def test_actuals_cover_2000_to_2008(taxes):
    rows = [r for r in observations(taxes) if r["document"] == "receipt_budget" and r["item_id"] == "net_tax_revenue"]
    assert sorted(r["fiscal_year"] for r in rows) == [f"{y}-{str(y + 1)[-2:]}" for y in range(2000, 2008)]
    assert all("/rec/annex7.pdf" in r["source_url"] for r in rows)

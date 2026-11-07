"""Which document each published figure comes from: build.choose (headline table), datasets.consolidate (taxes,
ministries, schemes) and build.compare_formats (PDF against its Excel/HTML copies). Small hand-made inputs only."""

import pytest

from budget_pipeline import build, datasets
from budget_pipeline.parse import Observation
from budget_pipeline.sources import FIRST_BUDGET, LATEST_BUDGET

# ----- build.choose ---------------------------------------------------------------------------------------------


def row(budget, kind, value, year="2010-11", field="fiscal_deficit", pct=None, label=None):
    """One observation as build.parse_all returns it."""
    return {"fiscal_year": year, "kind": kind, "field": field, "value_crore": value, "pct_gdp": pct,
            "source_budget": budget, "label_as_printed": label or f"fiscal deficit ({budget})"}


def test_choose_takes_each_estimate_from_its_own_budget():
    rows = [
        row("2010-11", "BE", 100, pct=5.5),
        row("2011-12", "BE", 100),  # BE reprinted unchanged: no be_restated
        row("2011-12", "RE", 120),
        row("2012-13", "Actual", 130),
        row("2013-14", "Actual", 999),  # not where Actuals for 2010-11 are taken from
        row("2009-10", "BE", 999),  # a BE printed in an earlier budget is not the announced one
    ]
    item = build.choose(rows)["2010-11"]["fiscal_deficit"]
    assert set(item) == {"be", "re", "actual"}
    assert item["be"] == {"value": 100, "pct_gdp": 5.5, "source_budget": "2010-11",
                          "label_as_printed": "fiscal deficit (2010-11)"}
    assert (item["re"]["value"], item["re"]["source_budget"]) == (120, "2011-12")
    assert (item["actual"]["value"], item["actual"]["source_budget"]) == (130, "2012-13")


def test_choose_keeps_a_restated_be_only_when_it_differs():
    item = build.choose([row("2010-11", "BE", 100), row("2011-12", "BE", 105, pct=5.6)])["2010-11"]["fiscal_deficit"]
    assert item["be"]["value"] == 100
    assert item["be_restated"] == {"value": 105, "pct_gdp": 5.6, "source_budget": "2011-12"}
    blank = build.choose([row("2010-11", "BE", 100), row("2011-12", "BE", None)])["2010-11"]["fiscal_deficit"]
    assert "be_restated" not in blank


def test_choose_leaves_out_missing_figures_rather_than_zero():
    out = build.choose([row("2010-11", "BE", 100), row("2011-12", "RE", None), row("2012-13", "Actual", None)])
    assert set(out["2010-11"]["fiscal_deficit"]) == {"be"}
    assert "revenue_deficit" not in out["2010-11"]  # nothing printed: the field is left out, not zero


def test_choose_covers_every_budget_year_and_no_other():
    # The first budget's Actual and RE columns are for years before the first budget: not published.
    rows = [row("2000-01", "Actual", 1, year="1998-99"), row("2000-01", "RE", 2, year="1999-00")]
    out = build.choose(rows)
    assert list(out) == [f"{y}-{str(y + 1)[-2:]}" for y in range(FIRST_BUDGET, LATEST_BUDGET + 1)]
    assert all(v == {} for v in out.values())


def test_choose_attaches_the_note_of_the_document_it_used(monkeypatch):
    monkeypatch.setattr(build, "SOURCE_NOTES", {
        ("2010-11", "2010-11", "BE", "fiscal_deficit"): "note on the announced BE",
        ("2011-12", "2010-11", "BE", "fiscal_deficit"): "note on the reprinted BE",
        ("2013-14", "2010-11", "Actual", "fiscal_deficit"): "note on a document that is not used",
    })
    rows = [row("2010-11", "BE", 100), row("2011-12", "BE", 105), row("2012-13", "Actual", 130),
            row("2013-14", "Actual", 131)]
    item = build.choose(rows)["2010-11"]["fiscal_deficit"]
    assert item["be"]["note"] == "note on the announced BE"
    assert item["be_restated"]["note"] == "note on the reprinted BE"
    assert "note" not in item["actual"]


def test_every_source_note_names_a_published_field():
    for (budget, year, kind, field) in build.SOURCE_NOTES:
        assert field in build.FIELD_LABELS, field
        assert kind in ("BE", "RE", "Actual"), kind
        assert budget >= year, (budget, year)


# ----- build.compare_formats ------------------------------------------------------------------------------------


def parsed(*observations):
    return {"observations": [Observation(f, "2010-11", k, v, p, f) for f, k, v, p in observations]}


def test_compare_formats_lists_only_real_differences():
    pdf = parsed(("fiscal_deficit", "BE", 1000, 5.5), ("revenue_deficit", "BE", 500, 2.5),
                 ("primary_deficit", "BE", 200, 1.0), ("borrowings", "BE", 900, None),
                 ("interest_payments", "BE", 300, None))
    xls = parsed(("fiscal_deficit", "BE", 1001, 5.5),  # within Rs 1 crore: rounding
                 ("revenue_deficit", "BE", 503, 2.5),  # off by 3: a difference
                 ("primary_deficit", "BE", 200, 1.1),  # % of GDP differs by 0.1 point
                 ("borrowings", "BE", 900, 4.0),  # % printed in one copy only: not a difference
                 ("total_receipts", "BE", 800, None))  # missing from the PDF
    result = build.compare_formats("2010-11", "pdf", {"pdf": pdf, "xls": xls}, {"htm": "no table"})
    assert result["budget"] == "2010-11"
    assert result["primary"] == "pdf"
    assert result["unparseable"] == {"htm": "no table"}
    assert result["others"]["xls"]["compared"] == 6
    assert result["others"]["xls"]["differences"] == [
        {"item": ("interest_payments", "2010-11", "BE"), "pdf": 300, "xls": None},
        {"item": ("primary_deficit", "2010-11", "BE", "% of GDP"), "pdf": 1.0, "xls": 1.1},
        {"item": ("revenue_deficit", "2010-11", "BE"), "pdf": 500, "xls": 503},
        {"item": ("total_receipts", "2010-11", "BE"), "pdf": None, "xls": 800},
    ]


def test_compare_formats_with_one_copy_compares_nothing():
    result = build.compare_formats("2010-11", "pdf", {"pdf": parsed(("fiscal_deficit", "BE", 1, None))}, {})
    assert result["others"] == {}


# ----- datasets.consolidate -------------------------------------------------------------------------------------


def drow(budget, kind, value, year="2010-11", item="income_tax", **extra):
    """One long-format observation of a detailed table (taxes, ministries, schemes)."""
    return {"fiscal_year": year, "item_id": item, "kind": kind, "value": value, "source_budget": budget,
            "label_as_printed": f"{item} as printed", "source_url": f"https://example.org/{budget}.pdf", **extra}


def consolidate(rows, id_fields=("item_id",), value_fields=("value",)):
    return datasets.consolidate(rows, id_fields, value_fields)


def test_consolidate_takes_each_estimate_from_its_own_budget():
    rows = [drow("2010-11", "BE", 100), drow("2011-12", "BE", 100), drow("2011-12", "RE", 120),
            drow("2012-13", "Actual", 130), drow("2013-14", "Actual", 999), drow("2009-10", "BE", 999)]
    item = consolidate(rows)["2010-11"]["income_tax"]
    assert set(item) == {"be", "re", "actual"}
    assert item["be"] == {"value": 100, "source_budget": "2010-11", "label_as_printed": "income_tax as printed",
                          "source_url": "https://example.org/2010-11.pdf"}
    assert (item["re"]["value"], item["actual"]["value"]) == (120, 130)


def test_consolidate_restated_be_beyond_a_rounding_difference():
    small = consolidate([drow("2010-11", "BE", 100.0), drow("2011-12", "BE", 100.005)])["2010-11"]["income_tax"]
    assert "be_restated" not in small
    big = consolidate([drow("2010-11", "BE", 100.0), drow("2011-12", "BE", 100.02)])["2010-11"]["income_tax"]
    assert big["be_restated"]["value"] == 100.02
    assert big["be_restated"]["source_budget"] == "2011-12"


def test_consolidate_keeps_a_reprinted_be_when_its_own_budget_lacks_it():
    # An item first printed a year later (e.g. a new scheme): its BE exists only as the reprint, kept apart.
    item = consolidate([drow("2011-12", "BE", 50), drow("2011-12", "RE", 60)])["2010-11"]["income_tax"]
    assert set(item) == {"re", "be_restated"}
    assert item["be_restated"]["value"] == 50


def test_consolidate_compares_every_value_field():
    fields = ("revenue_crore", "capital_crore")
    rows = [drow("2010-11", "BE", None, revenue_crore=10, capital_crore=5),
            drow("2011-12", "BE", None, revenue_crore=10, capital_crore=7),
            drow("2011-12", "RE", None, revenue_crore=None, capital_crore=None)]  # all blank: left out
    item = consolidate(rows, value_fields=fields)["2010-11"]["income_tax"]
    assert set(item) == {"be", "be_restated"}
    assert (item["be"]["revenue_crore"], item["be"]["capital_crore"]) == (10, 5)
    assert item["be_restated"]["capital_crore"] == 7


def test_consolidate_keys_items_by_every_id_field_and_keeps_notes():
    rows = [drow("2010-11", "BE", 1, item="a", scheme_type="css", note="read from the page image"),
            drow("2010-11", "BE", 2, item="a", scheme_type="central_sector", note=None)]
    out = consolidate(rows, id_fields=("scheme_type", "item_id"))["2010-11"]
    assert set(out) == {"css/a", "central_sector/a"}
    assert out["css/a"]["be"]["note"] == "read from the page image"
    assert "note" not in out["central_sector/a"]["be"]


def test_consolidate_accepts_the_same_figure_twice_but_refuses_two_values():
    assert consolidate([drow("2010-11", "BE", 1), drow("2010-11", "BE", 1)])["2010-11"]["income_tax"]["be"]["value"] == 1
    with pytest.raises(ValueError, match="two different values"):
        consolidate([drow("2010-11", "BE", 1), drow("2010-11", "BE", 2)])


def test_consolidate_leaves_out_years_with_nothing_printed():
    assert consolidate([drow("2011-12", "RE", None, year="2010-11")]) == {}

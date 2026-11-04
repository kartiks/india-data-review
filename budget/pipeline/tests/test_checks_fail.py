"""Each check, given a small dataset with a known fault, must report it (and pass the same data without it).

These build their inputs in memory and run one check each, so they take no time; the end-to-end tests show the
real data passing."""

import json

import pytest
from pipeline_common.report import Exceptions, Report
from pipeline_common.text import fy

from budget_pipeline import checks as C
from budget_pipeline import schemes
from budget_pipeline.build import FIELD_LABELS
from budget_pipeline.sources import FIRST_BUDGET, LATEST_BUDGET


def run(check, *args):
    """Run one headline check; return its section (title, checks, failures, notes, allowed)."""
    report = Report("test")
    check(*args, report)
    (section,) = report.sections
    return section


def obs(field, value, pct=None, budget="2010-11", year="2010-11", kind="BE"):
    """One row of observations.csv, as checks.load_observations() returns it."""
    return {"source_budget": budget, "fiscal_year": year, "kind": kind, "field": field,
            "value_crore": value, "pct_gdp": pct}


# ----- headline figures (checks.py) -----------------------------------------------------------------------------

def test_identity_failure_names_the_rule_and_the_gap():
    rows = [obs("revenue_receipts", 1000), obs("tax_revenue_net", 700), obs("non_tax_revenue", 200)]
    s = run(C.check_identities, rows)
    assert s.checks == 1
    assert s.failures == ["Budget 2010-11, BE 2010-11: revenue receipts = tax + non-tax — printed 1,000, "
                          "components give 900 (off by 100)"]


def test_identity_within_rounding_passes():
    rows = [obs("revenue_receipts", 1000), obs("tax_revenue_net", 797), obs("non_tax_revenue", 200)]
    s = run(C.check_identities, rows)
    assert (s.checks, s.failures) == (1, [])


def test_identity_listed_exception_is_allowed_with_its_reason(monkeypatch):
    key = ("identity", "Budget 2010-11, BE 2010-11: revenue receipts = tax + non-tax —")
    monkeypatch.setitem(C.EXCEPTIONS.known, key, "a reviewed reason")
    rows = [obs("revenue_receipts", 1000), obs("tax_revenue_net", 700), obs("non_tax_revenue", 200)]
    s = run(C.check_identities, rows)
    assert s.failures == []
    assert s.allowed == [{"reason": "a reviewed reason", "cases": 1}]
    assert s.notes[0].startswith("Allowed (1): a reviewed reason Cases:\n  - Budget 2010-11, BE 2010-11: revenue")


def test_pct_gdp_listed_exception_is_counted(monkeypatch):
    monkeypatch.setitem(C.EXCEPTIONS.known, ("pct", "Budget 2010-11, BE 2010-11: fiscal_deficit printed"),
                        "a reviewed reason")
    s = run(C.check_pct_gdp, [obs("fiscal_deficit", 100000, pct=6.0)], {"2010-11": {"value": 2_000_000}})
    assert (s.checks, s.failures, s.allowed) == (1, [], [{"reason": "a reviewed reason", "cases": 1}])


def test_unused_exceptions_are_listed_for_review():
    exceptions = Exceptions({("identity", "Budget 2010-11"): "used", ("identity", "Budget 1999-00"): "stale"},
                            contains={(("2010-11", "a check"), "fragment"): "stale too"})
    assert exceptions.reason("identity", "Budget 2010-11, BE 2010-11: ...") == "used"
    report = Report("test")
    C.check_unused_exceptions(report, {"headline": exceptions})
    (s,) = report.sections
    assert (s.checks, s.failures) == (0, [])
    assert s.notes == ["headline: identity: Budget 1999-00", "headline: 2010-11 / a check: fragment"]


def test_no_unused_exceptions_no_section():
    report = Report("test")
    C.check_unused_exceptions(report, {"headline": Exceptions()})
    assert report.sections == []


def test_cross_document_large_restatement_fails():
    rows = [obs("fiscal_deficit", 100000), obs("fiscal_deficit", 110000, budget="2011-12")]
    s = run(C.check_cross_document, rows)
    assert s.failures == ["BE 2010-11 fiscal_deficit: 100,000 in budget 2010-11 vs 110,000 in budget 2011-12 "
                          "(+10,000, 10.0%)"]


@pytest.mark.parametrize("restated", [101000, 100400])  # 1% (over Rs 500 crore); Rs 400 crore (0.4%)
def test_cross_document_small_restatement_is_a_note(restated):
    rows = [obs("fiscal_deficit", 100000), obs("fiscal_deficit", restated, budget="2011-12")]
    s = run(C.check_cross_document, rows)
    assert s.failures == []
    assert s.notes[0].startswith("Restated: BE 2010-11 fiscal_deficit")


def test_pct_gdp_against_stated_gdp():
    rows = [obs("fiscal_deficit", 100000, pct=6.0)]
    s = run(C.check_pct_gdp, rows, {"2010-11": {"value": 2_000_000}})
    assert s.failures == ["Budget 2010-11, BE 2010-11: fiscal_deficit printed 6.0% of GDP, but 100,000 / "
                          "stated GDP 2,000,000 = 5.00%"]


def test_pct_gdp_against_gdp_implied_by_fiscal_deficit():
    # A later budget's column (no stated GDP for it): the fiscal deficit's own % gives GDP 2,000,000.
    rows = [obs("fiscal_deficit", 100000, pct=5.0, budget="2011-12"),
            obs("revenue_deficit", 60000, pct=2.0, budget="2011-12")]
    s = run(C.check_pct_gdp, rows, {})
    assert s.checks == 2
    assert s.failures == ["Budget 2011-12, BE 2010-11: revenue_deficit printed 2.0% of GDP, but 60,000 / "
                          "GDP implied by fiscal deficit % = 3.00%"]


def test_pct_gdp_within_rounding_passes():
    rows = [obs("fiscal_deficit", 100000, pct=5.0), obs("primary_deficit", 30900, pct=1.5)]
    s = run(C.check_pct_gdp, rows, {"2010-11": {"value": 2_000_000}})
    assert (s.checks, s.failures) == (2, [])


def complete_dataset() -> dict:
    """Every field, every estimate, every year: nothing missing."""
    full = {f: {"be": {"value": 1}, "re": {"value": 1}, "actual": {"value": 1}} for f in FIELD_LABELS}
    return {"years": {fy(y): json.loads(json.dumps(full)) for y in range(FIRST_BUDGET, LATEST_BUDGET + 1)}}


def test_completeness_reports_each_missing_figure():
    dataset = complete_dataset()
    assert run(C.check_completeness, dataset).failures == []
    del dataset["years"]["2010-11"]["fiscal_deficit"]["re"]
    del dataset["years"]["2012-13"]["interest_payments"]
    s = run(C.check_completeness, dataset)
    assert s.failures == ["2010-11: missing RE for fiscal_deficit", "2012-13: missing BE for interest_payments",
                          "2012-13: missing RE for interest_payments", "2012-13: missing ACTUAL for interest_payments"]


def test_completeness_does_not_ask_for_unpublished_figures():
    dataset = complete_dataset()
    latest = dataset["years"][fy(LATEST_BUDGET)]
    for item in latest.values():
        del item["re"], item["actual"]
    assert run(C.check_completeness, dataset).failures == []


def test_rbi_comparison(monkeypatch):
    rbi = {
        ("2010-11", "fiscal_deficit", "actual"): {"value": 400000},  # matches
        ("2011-12", "fiscal_deficit", "actual"): {"value": 500000},  # ours is 2% higher: fails
        ("2012-13", "fiscal_deficit", "actual"): {"value": 490000},  # ours is 0.1% lower: a note
        ("2013-14", "fiscal_deficit", "actual"): {"value": 500000},  # ours is missing: fails
        ("1999-00", "fiscal_deficit", "actual"): {"value": 1},  # before the first budget: not compared
    }
    monkeypatch.setattr(C, "load_rbi", lambda: rbi)
    dataset = {"years": {y: {"fiscal_deficit": {"actual": {"value": v}}}
                         for y, v in (("2010-11", 400003), ("2011-12", 510000), ("2012-13", 489500))}}
    s = run(C.check_reference, dataset)
    assert s.checks == 4
    assert s.failures == ["Actual 2011-12 fiscal_deficit: ours 510,000 vs RBI 500,000 (+10,000, 2.00%)",
                          "Actual 2013-14 fiscal_deficit: missing from our data (RBI: 500,000)"]
    assert s.notes[0] == "1 of 4 figures match the RBI series exactly (within Rs 5 crore)."
    assert s.notes[1].startswith("Actual 2012-13 fiscal_deficit: ours 489,500 vs RBI 490,000 (-500, 0.10%). "
                                 "Small difference:")


def test_rbi_listed_difference_is_allowed(monkeypatch):
    monkeypatch.setattr(C, "load_rbi", lambda: {("2011-12", "fiscal_deficit", "actual"): {"value": 500000}})
    monkeypatch.setitem(C.EXCEPTIONS.known, ("rbi", "Actual 2011-12 fiscal_deficit:"), "a reviewed reason")
    dataset = {"years": {"2011-12": {"fiscal_deficit": {"actual": {"value": 600000}}}}}
    s = run(C.check_reference, dataset)
    assert s.failures == []
    assert s.allowed == [{"reason": "a reviewed reason", "cases": 1}]
    assert "  - Actual 2011-12 fiscal_deficit: ours 600,000 vs RBI 500,000 (+100,000, 20.00%)" in s.notes[0]


def test_year_on_year_jump_is_flagged_for_review():
    # Not a failure by design (a real jump happens, e.g. 2020-21), but it must be listed for a person to look at.
    values = {"2010-11": 100, "2011-12": 110, "2012-13": 200, "2013-14": 210}
    dataset = {"years": {y: {"total_expenditure": {"actual": {"value": v}}} for y, v in values.items()}}
    s = run(C.check_jumps, dataset)
    assert s.failures == []
    assert s.notes == ["total_expenditure: 2011-12 → 2012-13 changed +82% (110 → 200)"]


def test_other_copies_must_agree(monkeypatch, tmp_path):
    (tmp_path / "format_comparison.json").write_text(json.dumps([{
        "budget": "2010-11", "primary": "pdf", "unparseable": {},
        "others": {"xls": {"compared": 50, "differences": [{"item": "fiscal_deficit BE 2010-11", "pdf": 381408,
                                                             "xls": 381480}]}},
    }]))
    monkeypatch.setattr(C, "DATA", tmp_path)
    s = run(C.check_formats)
    assert s.failures == ["Budget 2010-11: XLS differs from PDF in 1 values (fiscal_deficit BE 2010-11: 381408 vs "
                          "381480)"]
    monkeypatch.setitem(C.EXCEPTIONS.known, ("format", "Budget 2010-11: XLS differs"), "a reviewed reason")
    s = run(C.check_formats)
    assert (s.failures, s.allowed) == ([], [{"reason": "a reviewed reason", "cases": 1}])


# ----- schemes (Expenditure Profile Statements 4A/4B) -------------------------------------------------------------

def item(iid, values, level="scheme", label=None, number="1"):
    """A parsed scheme row. values: {(fiscal_year, kind): (revenue, capital, total)}."""
    return {"item_id": iid, "level": level, "number": number, "label_as_printed": label or iid,
            "demand_no": None, "category": None, "parent": None, "department": None,
            "values": {pk: dict(zip(("revenue", "capital", "total"), v)) for pk, v in values.items()}}


def budgets(*rows_by_budget):
    """{budget: [rows]} -> all_parsed for schemes.checks, adding a Grand Total that equals the rows."""
    out = {}
    for budget, rows in rows_by_budget:
        periods = {pk for r in rows for pk in r["values"]}
        grand = {pk: tuple(sum(r["values"][pk][p] for r in rows) for p in ("revenue", "capital", "total"))
                 for pk in periods}
        items = [*rows, item("css:grand_total", grand, level="grand_total", label="Grand Total", number="")]
        out[budget] = {"css": {"parsed": {"items": items}, "errors": {}, "differences": {}}}
    return {"budgets": out}


def scheme_section(all_parsed, start):
    return next(s for s in schemes.checks(all_parsed, []) if s[0].startswith(start))


def cross(restated, kind="BE"):
    """Scheme A's 2010-11 figure: 1,000 in Budget 2010-11 and `restated` in Budget 2011-12, which merges Scheme B
    into it (so the Grand Total is the same in both)."""
    pk = ("2010-11", kind)
    return budgets(("2010-11", [item("css:a", {pk: (1000, 0, 1000)}, label="Scheme A"),
                                item("css:b", {pk: (restated - 1000, 0, restated - 1000)}, label="Scheme B")]),
                   ("2011-12", [item("css:a", {pk: (restated, 0, restated)}, label="Scheme A")]))


def test_scheme_restated_by_more_than_both_limits_fails():
    _, checked, fails, _, _ = scheme_section(cross(2000), "Same scheme figure agrees")
    assert checked == 2  # Scheme A and the Grand Total
    assert fails == ["css 'Scheme A' BE 2010-11: 1,000.00 in budget 2010-11 vs 2,000.00 in budget 2011-12 "
                     "(+1,000.00, 50.0%)"]


@pytest.mark.parametrize("restated", [1400, 1010])  # +400 (40%, but under Rs 500 crore); +10 (1%)
def test_scheme_small_restatement_is_a_note(restated):
    _, _, fails, notes, _ = scheme_section(cross(restated), "Same scheme figure agrees")
    assert fails == []
    assert any(n.startswith("Restated: css 'Scheme A' BE 2010-11") for n in notes)


def test_scheme_listed_restatement_is_allowed(monkeypatch):
    monkeypatch.setitem(schemes.EXCEPTIONS.known, (("cross", "css", "css:a"), "BE 2010-11"), "a reviewed reason")
    _, _, fails, _, allowed = scheme_section(cross(2000), "Same scheme figure agrees")
    assert fails == []
    assert dict(allowed.cases) == {"a reviewed reason": [
        "css 'Scheme A' BE 2010-11: 1,000.00 in budget 2010-11 vs 2,000.00 in budget 2011-12 (+1,000.00, 50.0%)"]}


def test_scheme_actuals_must_match_exactly():
    # Only a BE may be restated; the same Actual printed twice must agree.
    _, _, fails, _, _ = scheme_section(cross(1010, kind="Actual"), "Same scheme figure agrees")
    assert fails == ["css 'Scheme A' Actual 2010-11: 1,000.00 in budget 2010-11 vs 1,010.00 in budget 2011-12 "
                     "(+10.00, 1.0%)"]


def test_scheme_revenue_plus_capital_must_equal_total():
    data = budgets(("2010-11", [item("css:a", {("2010-11", "BE"): (600, 300, 1000)}, label="Scheme A")]))
    _, _, fails, _, _ = scheme_section(data, "Schemes: revenue + capital = total")
    assert "Budget 2010-11 css: 'Scheme A' BE 2010-11: 600.00 + 300.00 != 1000.00" in fails


def test_scheme_rows_must_add_up_to_the_grand_total():
    data = budgets(("2010-11", [item("css:a", {("2010-11", "BE"): (600, 400, 1000)})]))
    data["budgets"]["2010-11"]["css"]["parsed"]["items"][-1]["values"][("2010-11", "BE")]["total"] = 1200
    _, _, fails, _, _ = scheme_section(data, "Schemes add up")
    assert fails == ["Budget 2010-11 css BE 2010-11 total: groups sum to 1,000.00, Grand Total 1,200.00"]


def test_grand_total_restated_by_a_small_share_still_fails():
    # Scheme A grows by 10 (1%) in the second budget and nothing offsets it, so the Grand Total moves by 10 too:
    # a scheme row may be restated a little, the Grand Total may not.
    pk = ("2010-11", "BE")
    data = budgets(("2010-11", [item("css:a", {pk: (1000, 0, 1000)}, label="Scheme A")]),
                   ("2011-12", [item("css:a", {pk: (1010, 0, 1010)}, label="Scheme A")]))
    _, _, fails, notes, _ = scheme_section(data, "Same scheme figure agrees")
    assert fails == ["css 'Grand Total' BE 2010-11: 1,000.00 in budget 2010-11 vs 1,010.00 in budget 2011-12 "
                     "(+10.00, 1.0%)"]
    assert any(n.startswith("Restated: css 'Scheme A'") for n in notes)

"""Unit tests for the readers, plus an end-to-end run of the checks on the saved data."""

import json
from pathlib import Path

import pytest

from gdp_pipeline import budget, build, checks, forecasts

ROOT = Path(__file__).resolve().parents[2]


def test_budget_sentence_with_growth():
    text = ("GDP for BE 2023-2024 has been projected at ` 3,01,75,065 crore assuming 10.5 % growth over the "
            "estimated Nominal GDP of ` 2,73,07,751 crore as per the First Advance Estimates")
    p = budget.parse_sentence(text)
    assert p["gdp_crore"] == 30175065
    assert p["growth_pct"] == 10.5
    assert p["base_gdp_crore"] == 27307751


def test_budget_sentence_without_growth():
    p = budget.parse_sentence("GDP for BE 2015-2016 has been projected at `14108945 crore")
    assert p["gdp_crore"] == 14108945 and "growth_pct" not in p


def test_numbers_in_quotes():
    assert forecasts.numbers_in("negative at (-)9.5 per cent") >= {-9.5}
    assert forecasts.numbers_in("7 to 7¾ per cent") >= {7.0, 7.75}
    assert forecasts.numbers_in("range of 5.4 – 5.9 per cent") >= {5.4, 5.9}


@pytest.mark.parametrize("quote, numbers", [
    ("GVA growth for 2016-17 is projected at 7.6 per cent", {7.6}),  # not 2016, 17 or -17
    ("revised down to 6.7 per cent from the August 2017 projection of 7.3 per cent", {6.7, 7.3}),
    ("7.2 per cent – in the range of 6.8-7.1 per cent in H1:2019-20 and 7.3-7.4 per cent in H2", {7.2, 6.8, 7.1, 7.3, 7.4}),
    ("we expect real GDP growth to be in the 6¾ to 7½ percent range in FY2018.", {6.75, 7.5}),
    ("a baseline GDP growth of 6.5 per cent in real terms in FY24.", {6.5}),
    ("raising real GDP growth from 4.4 per cent in Q1 to 5.0 per cent", {4.4, 5.0}),
    ("growth in 1999-2000 was 8.8 per cent", {8.8}),
    ("growth of -0.5 per cent, or minus 1 per cent, between 6.8 - 7.1", {-0.5, 0.5, -1.0, 1.0, 6.8, 7.1}),
])
def test_numbers_in_leaves_out_years_and_periods(quote, numbers):
    assert forecasts.numbers_in(quote) == numbers


def test_years_in():
    assert forecasts.years_in("from 6.6 per cent in 2017-18 to 7.4 per cent in 2018-19.") == {"2017-18", "2018-19"}
    assert forecasts.years_in("in FY2018 and FY24, H1:2019-20; 1999-2000") == {"2017-18", "2023-24", "2019-20",
                                                                               "1999-00"}
    assert forecasts.years_in("for the year as a whole, 7.5 per cent, April 2017") == set()


def survey(**kw):
    return {"fiscal_year": "2023-24", "low": 6.5, "high": 6.5, "quote": "growth of 6.5 per cent in FY24.", **kw}


def test_a_record_its_sentences_bear_out_has_no_problems():
    assert forecasts.record_problems(survey()) == []
    # a band from a second sentence, or the projection ± the quote's '(+/- x)'
    assert forecasts.record_problems(survey(band_low=6.0, band_high=6.8,
                                            quote_2="in the range of 6.0 per cent to 6.8 per cent")) == []
    assert forecasts.record_problems({"fiscal_year": "2011-12", "low": 9.0, "high": 9.0, "band_low": 8.75,
                                      "band_high": 9.25, "quote": "grow by 9 per cent (+/- 0.25) in 2011-12."}) == []
    assert forecasts.record_problems(survey(nominal_low=10.5, nominal_high=11.0,
                                            nominal_quote="nominal growth of 10.5 to 11 per cent")) == []
    # the year growth is measured from may be named too
    assert forecasts.record_problems({"fiscal_year": "2018-19", "value": 7.4,
                                      "quote": "from 6.6 per cent in 2017-18 to 7.4 per cent in 2018-19"}) == []


@pytest.mark.parametrize("record, problem", [
    ({"fiscal_year": "2016-17", "value": 17.0, "quote": "GVA growth for 2016-17 is projected at 7.6 per cent"},
     "recorded [17.0] not all in the quote"),
    (survey(band_low=6.0, band_high=6.9, quote_2="in the range of 6.0 per cent to 6.8 per cent"),
     "band [6.0, 6.9] not in the quotes"),
    (survey(band_low=6.0), "band [6.0, None] not in the quotes"),
    ({"fiscal_year": "2011-12", "low": 9.0, "high": 9.0, "band_low": 8.5, "band_high": 9.5,
      "quote": "grow by 9 per cent (+/- 0.25) in 2011-12."}, "band [8.5, 9.5] not in the quotes"),
    (survey(nominal_low=10.5, nominal_high=11.5, nominal_quote="nominal growth of 10.5 to 11 per cent"),
     "nominal [10.5, 11.5] not all in"),
    (survey(fiscal_year="2024-25"), "the quotes name ['2023-24'], not 2024-25"),
    (survey(quote_2="and 7 per cent in 2025-26"), "the quotes name ['2023-24', '2025-26'], not 2023-24"),
    (survey(quote="growth of 6.5 per cent for the year as a whole"), "the quotes name no fiscal year"),
])
def test_a_record_its_sentences_do_not_bear_out_is_reported(record, problem):
    problems = forecasts.record_problems(record)
    assert len(problems) == 1 and problems[0].startswith(f"{record['fiscal_year']}: {problem}")


def rbi(date, value=7.0, **flags):
    return {"fiscal_year": "2024-25", "date": date, "value": value, **flags}


def flagged():
    return [rbi("2024-02-08", is_first=True), rbi("2024-04-05", is_first_april_policy=True), rbi("2024-06-07"),
            rbi("2024-12-06", is_last=True)]


def test_flags_that_follow_the_dates_have_no_problems():
    assert forecasts.flag_problems(flagged()) == []
    # records are matched by date, not by their order in the file; a record without a figure is never first or last
    assert forecasts.flag_problems([rbi("2024-01-01", value=None)] + flagged()[::-1]) == []
    # a year still being projected: its latest record is marked as such, and none is last
    running = flagged()[:3] + [rbi("2024-10-09", is_latest_available=True)]
    assert forecasts.flag_problems(running) == []


@pytest.mark.parametrize("change, problem", [
    (lambda rs: rs[0].pop("is_first") and rs[1].update(is_first=True),
     "2024-25: is_first is set on ['2024-04-05'], expected ['2024-02-08']"),
    (lambda rs: rs[3].pop("is_last"), "2024-25: is_last is set on no record, expected ['2024-12-06']"),
    (lambda rs: rs[2].update(is_last=True), "2024-25: is_last is set on ['2024-06-07', '2024-12-06'], expected"),
    (lambda rs: rs[3].update(value=None), "2024-25: is_last is set on ['2024-12-06'], expected ['2024-06-07']"),
    (lambda rs: rs[1].pop("is_first_april_policy"), "2024-25: is_first_april_policy is set on no record"),
    (lambda rs: rs[2].update(is_latest_available=True), "2024-25: is_latest_available is set on ['2024-06-07'], "
                                                         "expected ['2024-12-06']"),
])
def test_flags_that_do_not_follow_the_dates_are_reported(change, problem):
    rs = flagged()
    change(rs)
    problems = forecasts.flag_problems(rs, lambda r: r["date"])
    assert any(p.startswith(problem) for p in problems), problems


def test_in_order_tolerates_interleaved_text():
    quote = "expected to grow in the range of 5.4 – 5.9 per cent"
    text = "expected to grow in the turing, improved balance of range of 5.4 – 5.9 per cent in 2014-15"
    assert forecasts.in_order(quote, text)
    assert not forecasts.in_order(quote, "expected to fall sharply")


@pytest.mark.skipif(not (ROOT / "data" / "gdp.json").exists(), reason="data not built")
def test_checks_pass_on_saved_data(tmp_path):
    # The report goes to tmp_path: gdp/data/validation_report.md and validation_summary.json are the site's build
    # gate and are written only by the pipeline.
    ds = json.loads((ROOT / "data" / "gdp.json").read_text())
    assert checks.main(ds, out=tmp_path) == 0
    assert json.loads((tmp_path / "validation_summary.json").read_text())["result"] == "PASSED"


def row(indicator, industry="", subindustry="", sector="", cur=None, con=None, unit="₹ Crore",
        series="2022-23", year="2023-24", stage="FINAL"):
    return {"series": series, "frequency": "annual", "year": year, "quarter": "", "stage": stage,
            "indicator": indicator, "industry": industry, "subindustry": subindustry, "sector": sector,
            "current_price": cur, "constant_price": con, "unit": unit}


def test_arrange_keeps_industry_growth_when_subindustries_follow():
    # build.main sorts sub-industry rows after their industry; they must not replace the industry's rate.
    rows = [row("gva_growth", "manufacturing", con=10.7, cur=9.0, unit="%"),
            row("gva_growth", "manufacturing", "textiles_apparel_and_leather_products", con=-1.3, cur=-2.0, unit="%")]
    node = build.arrange(rows)["2022-23"]["annual"]["2023-24"]["FINAL"]
    assert node["gva_growth"] == {"manufacturing": {"real": 10.7, "nominal": 9.0}}


@pytest.mark.parametrize("order", [1, -1])
def test_arrange_ignores_gva_by_institutional_sector(order):
    rows = [row("gva", "total", sector="total", cur=100.0, con=90.0),
            row("gva", sector="households", cur=40.0)][::order]
    node = build.arrange(rows)["2022-23"]["annual"]["2023-24"]["FINAL"]
    assert node["gva_by_industry"] == {"total": {"cur": 100.0, "con": 90.0}}


def growth_ds(series, year, stage, published_real, level_now=110.0, level_before=100.0):
    prev_year = f"{int(year[:4]) - 1}-{year[2:4]}"
    return {"data": {series: {"annual": {
        prev_year: {"RE1": {"gva_by_industry": {"mining": {"con": level_before}}}},
        year: {stage: {"gva_by_industry": {"mining": {"con": level_now}},
                       "gva_growth": {"mining": {"real": published_real}}}},
    }}}}


def industry_growth(ds):
    report = checks.Report(checks.INTRO)
    checks.check_industry_growth(ds, report)
    (s,) = report.sections
    return s.checks, s.failures, s.notes


def test_industry_growth_matching_levels_passes():
    assert industry_growth(growth_ds("2022-23", "2024-25", "RE1", 10.0))[:2] == (1, [])


def test_industry_growth_far_from_levels_fails():
    _, failures, _ = industry_growth(growth_ds("2011-12", "2018-19", "RE1", -1.3))
    assert len(failures) == 1 and "mining: published real growth -1.3%, levels give RE1 10.00%" in failures[0]


def test_industry_growth_small_gap_fails_only_where_estimates_are_kept():
    assert len(industry_growth(growth_ds("2022-23", "2024-25", "RE1", 10.4))[1]) == 1
    _, failures, notes = industry_growth(growth_ds("2011-12", "2018-19", "RE1", 10.4))
    assert failures == [] and any("within 1.5 points" in n for n in notes)


def test_industry_growth_known_exception_is_allowed_with_reason():
    _, failures, notes = industry_growth(growth_ds("2011-12", "2014-15", "AE1", 4.0))
    assert failures == [] and any(n.startswith("Allowed (1): ") and "first releases" in n for n in notes)


def test_industry_growth_quarters_compare_with_the_same_quarter_a_year_earlier():
    ds = {"data": {"2022-23": {"annual": {}, "quarterly": {
        "2023-24 Q2": {"LATEST": {"gva_by_industry": {"mining": {"con": 100.0}}}},
        "2024-25 Q2": {"LATEST": {"gva_by_industry": {"mining": {"con": 104.0}},
                                  "gva_growth": {"mining": {"real": 4.0}}}},
        "2024-25 Q1": {"LATEST": {"gva_by_industry": {"mining": {"con": 50.0}},
                                  "gva_growth": {"mining": {"real": 9.0}}}},
    }}}}
    checked, failures, notes = industry_growth(ds)
    assert (checked, failures) == (1, []) and any("1 published rates not checkable" in n for n in notes)


def test_industry_growth_mistyped_2019_20_rate_is_allowed():
    ds = growth_ds("2011-12", "2019-20", "AE2", 3.3, level_now=107.26)
    ds["data"]["2011-12"]["annual"]["2019-20"]["AE2"]["gva_growth"] = {"total": {"nominal": 3.3}}
    ds["data"]["2011-12"]["annual"]["2019-20"]["AE2"]["gva_by_industry"] = {"total": {"cur": 107.26}}
    ds["data"]["2011-12"]["annual"]["2018-19"]["RE1"]["gva_by_industry"] = {"total": {"cur": 100.0}}
    _, failures, notes = industry_growth(ds)
    assert failures == [] and any(n.startswith("Allowed (1): ") and "mistyped" in n for n in notes)


def test_gdp_growth_exact_for_the_new_series():
    def ds(series, published):
        return {"data": {series: {"annual": {
            "2023-24": {"FINAL": {"gdp": {"con": 100.0}}},
            "2024-25": {"RE1": {"gdp": {"con": 106.0}, "growth": {"gdp": {"real": published}}}},
        }}}}
    for series, failures in (("2022-23", 1), ("2011-12", 0)):
        report = checks.Report(checks.INTRO)
        checks.check_growth(ds(series, 6.5), report)
        assert len(report.sections[0].failures) == failures


@pytest.mark.parametrize("text, expected", [
    ("Trade & Repair Services", "trade_repair_services"),
    ("Communication & Services Related to Broadcasting", "communication_services_related_to_broadcasting"),
    ("Food Products, Beverages and Tobacco", "food_products_beverages_and_tobacco"),
    (" -- Odd -- spacing -- ", "odd_spacing"),
])
def test_slug_collapses_every_run_of_separators(text, expected):
    assert build.slug(text) == expected


def identities(node):
    report = checks.Report(checks.INTRO)
    checks.check_identities({"data": {"2022-23": {"annual": {"2023-24": {"FINAL": node}}}}}, report)
    (s,) = report.sections
    return s.failures


def trade_node(**subs):
    return {"gva_by_industry": {"trade_hotels": {"cur": 100.0}}, "gva_sub": {"trade_hotels": subs}}


def test_subindustries_that_add_up_pass():
    assert identities(trade_node(trade_repair_services={"cur": 80.0}, hotels_restaurants={"cur": 20.0})) == []


def test_subindustries_that_do_not_add_up_fail():
    (f,) = identities(trade_node(trade_repair_services={"cur": 80.0}, hotels_restaurants={"cur": 40.0}))
    assert "sub-industries = industry — printed 100, parts give 120 (-20)" in f


def test_missing_subindustry_fails_instead_of_skipping_the_sum():
    (f,) = identities(trade_node(trade_repair_services={"cur": 80.0}))
    assert "sub-industries of trade_hotels: missing hotels_restaurants" in f


def test_unexpected_subindustry_fails():
    (f,) = identities(trade_node(trade__repair_services={"cur": 80.0}, hotels_restaurants={"cur": 20.0}))
    assert "missing trade_repair_services; unexpected trade__repair_services" in f


def test_subindustry_without_the_price_basis_fails():
    (f,) = identities(trade_node(trade_repair_services={"cur": 80.0}, hotels_restaurants={"con": 20.0}))
    assert "current prices: sub-industries of trade_hotels: no figure for hotels_restaurants" in f


def test_subindustries_of_an_unlisted_industry_fail():
    node = {"gva_by_industry": {"mining": {"cur": 10.0}}, "gva_sub": {"mining": {"coal": {"cur": 10.0}}}}
    (f,) = identities(node)
    assert "sub-industries of mining: not expected" in f


def test_subindustries_without_their_industry_fail():
    node = trade_node(trade_repair_services={"cur": 80.0}, hotels_restaurants={"cur": 20.0})
    node["gva_by_industry"] = {}
    (f,) = identities(node)
    assert "2023-24, FINAL: sub-industries of trade_hotels: published, but trade_hotels itself is not" in f


def test_either_set_of_transport_subindustries_is_accepted():
    old = ["railways", "transport_by_other_means", "storage", "communication_services_related_to_broadcasting"]
    node = {"gva_by_industry": {"transport_comm": {"cur": 40.0}},
            "gva_sub": {"transport_comm": {k: {"cur": 10.0} for k in old}}}
    assert identities(node) == []

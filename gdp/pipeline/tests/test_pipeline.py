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


def test_in_order_tolerates_interleaved_text():
    quote = "expected to grow in the range of 5.4 – 5.9 per cent"
    text = "expected to grow in the turing, improved balance of range of 5.4 – 5.9 per cent in 2014-15"
    assert forecasts.in_order(quote, text)
    assert not forecasts.in_order(quote, "expected to fall sharply")


def test_unit_label_error_not_converted():
    assert build.to_crore(2079741, "₹ Lakh", "product_taxes") == 2079741
    assert build.to_crore(100, "₹ Lakh", "gdp") == 1


@pytest.mark.skipif(not (ROOT / "data" / "gdp.json").exists(), reason="data not built")
def test_checks_pass_on_saved_data():
    ds = json.loads((ROOT / "data" / "gdp.json").read_text())
    assert checks.main(ds) == 0


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
    assert failures == [] and any(n.startswith("Allowed (1 rate)") and "first releases" in n for n in notes)


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
    assert failures == [] and any(n.startswith("Allowed (1 rate)") and "mistyped" in n for n in notes)


def test_gdp_growth_exact_for_the_new_series():
    def ds(series, published):
        return {"data": {series: {"annual": {
            "2023-24": {"FINAL": {"gdp": {"con": 100.0}}},
            "2024-25": {"RE1": {"gdp": {"con": 106.0}, "growth": {"gdp": {"real": published}}}},
        }}}}
    for series, failures in (("2022-23", 1), ("2011-12", 0)):
        report = checks.Report()
        checks.check_growth(ds(series, 6.5), report)
        assert len(report.sections[0][2]) == failures

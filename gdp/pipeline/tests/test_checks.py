"""Each national-accounts check fed a small dataset with one thing wrong: it must fail, and say what is wrong."""

import pytest

from gdp_pipeline import checks


def run(check, ds):
    """(checks, failures, notes) of the one report section the check adds."""
    report = checks.Report(checks.INTRO)
    check(ds, report)
    (s,) = report.sections
    return s.checks, s.failures, s.notes


# ---- quarters ---------------------------------------------------------------------------------------------------

def quarters_ds(series, published_real, now=107.0, before=100.0):
    return {"data": {series: {"annual": {}, "quarterly": {
        "2023-24 Q1": {"LATEST": {"gdp": {"con": before}}},
        "2024-25 Q1": {"LATEST": {"gdp": {"con": now}, "growth": {"gdp": {"real": published_real}}}},
    }}}}


def test_quarterly_growth_that_follows_from_levels_passes():
    assert run(checks.check_quarters, quarters_ds("2022-23", 7.0))[:2] == (1, [])


def test_quarterly_growth_off_by_a_tenth_fails_in_the_new_series():
    _, failures, _ = run(checks.check_quarters, quarters_ds("2022-23", 7.1))
    assert failures == ["2022-23 series, 2024-25 Q1: published real growth 7.1%, levels give 7.00%"]


def test_quarterly_growth_off_by_a_tenth_fails_in_the_old_series_too():
    _, failures, _ = run(checks.check_quarters, quarters_ds("2011-12", 7.1))
    assert failures == ["2011-12 series, 2024-25 Q1: published real growth 7.1%, levels give 7.00%"]


def test_quarterly_growth_far_from_levels_fails_in_the_old_series():
    _, failures, _ = run(checks.check_quarters, quarters_ds("2011-12", 8.7))
    assert failures == ["2011-12 series, 2024-25 Q1: published real growth 8.7%, levels give 7.00%"]


def test_quarters_that_do_not_add_up_to_the_year_fail():
    def ds(q4):
        quarters = {f"2024-25 Q{i}": {"LATEST": {"gdp": {"cur": v}}} for i, v in enumerate((25.0, 25.0, 25.0, q4), 1)}
        return {"data": {"2022-23": {"annual": {"2024-25": {"RE1": {"gdp": {"cur": 100.0}}}}, "quarterly": quarters}}}
    assert run(checks.check_quarters, ds(25.0))[:2] == (1, [])
    _, failures, _ = run(checks.check_quarters, ds(45.0))
    assert failures == ["2022-23 series, 2024-25: four quarters add to 120 (cur), annual RE1 is 100"]


def test_quarters_that_add_up_to_an_earlier_estimate_of_the_year_are_noted():
    quarters = {f"2024-25 Q{i}": {"LATEST": {"gdp": {"cur": 25.0}}} for i in range(1, 5)}
    ds = {"data": {"2011-12": {"annual": {"2024-25": {"PE": {"gdp": {"cur": 100.0}}, "RE1": {"gdp": {"cur": 130.0}}}},
                               "quarterly": quarters}}}
    _, failures, notes = run(checks.check_quarters, ds)
    assert failures == [] and any("they match the PE instead" in n for n in notes)


# ---- accounting identities --------------------------------------------------------------------------------------

BROAD = {i: {"cur": 10.0} for i in checks.BROAD}
FINER = {**{i: {"cur": 10.0} for i in ("agriculture", "mining", "manufacturing", "utilities", "construction")},
         **{i: {"cur": 5.0} for i in ("trade_hotels", "transport_comm", "financial", "real_estate", "public_admin",
                                     "other_services")},
         **{g: {"cur": 10.0, "summed": True} for g in ("trade_transport", "finance_realestate", "public_other")}}
SECTORS = ("public_nonfin", "private_nonfin", "public_fin", "private_fin", "government", "households")

IDENTITY_CASES = {
    "8 industries = total GVA": {"gva_by_industry": {**BROAD, "total": {"cur": 90.0}}},
    "industry group = its parts": {"gva_by_industry": {"financial": {"cur": 4.0}, "real_estate": {"cur": 5.0},
                                                       "finance_realestate": {"cur": 10.0}}},
    "finer industries = total GVA (where groups are not published)": {"gva_by_industry": {**FINER, "total": {"cur": 90.0}}},
    "GDP = GVA + net taxes on products": {"gva_by_industry": {"total": {"cur": 90.0}}, "net_taxes": {"cur": 9.0},
                                          "gdp": {"cur": 100.0}},
    "net taxes = taxes − subsidies": {"product_taxes": {"cur": 12.0}, "product_subsidies": {"cur": 1.0},
                                      "net_taxes": {"cur": 10.0}},
    "NDP = GDP − depreciation": {"gdp": {"cur": 100.0}, "cfc": {"cur": 12.0}, "ndp": {"cur": 89.0}},
    "GNI = GDP + net primary income from abroad": {"gdp": {"cur": 100.0}, "primary_income_row": {"cur": -2.0},
                                                   "gni": {"cur": 99.0}},
    "GNDI = GNI + net current transfers from abroad": {"gni": {"cur": 98.0}, "transfers_row": {"cur": 3.0},
                                                       "gndi": {"cur": 100.0}},
    "gfcf by sector = total": {"gfcf": {"cur": 100.0}, "gfcf_by_sector": {s: {"cur": 10.0} for s in SECTORS}},
    "saving by sector = total": {"saving": {"cur": 100.0}, "saving_by_sector": {s: {"cur": 10.0} for s in SECTORS}},
}


def scaled(node):
    """The node in ₹100 crore: each case above is then ₹100 crore or more off, well past LEVEL_TOL."""
    return {k: scaled(v) if isinstance(v, dict) else v * 100 if isinstance(v, float) else v for k, v in node.items()}


def identity_failures(node, series="2022-23", year="2023-24", stage="FINAL"):
    return run(checks.check_identities, {"data": {series: {"annual": {year: {stage: scaled(node)}}}}})[1]


@pytest.mark.parametrize("name", IDENTITY_CASES)
def test_each_identity_fails_when_its_parts_do_not_add_up(name):
    (f,) = identity_failures(IDENTITY_CASES[name])
    assert f.startswith(f"2022-23 series, 2023-24, FINAL, current prices: {name} — printed ")
    assert "parts give" in f


def test_identities_within_rounding_pass():
    node = {"gdp": {"cur": 100.0}, "cfc": {"cur": 12.0}, "ndp": {"cur": 88.0 + checks.LEVEL_TOL / 100}}
    assert identity_failures(node) == []


def test_back_series_before_2004_05_may_not_add_up_but_later_years_must():
    node = {"gva_by_industry": {**BROAD, "total": {"cur": 90.0}}}
    report = checks.Report(checks.INTRO)
    checks.check_identities({"data": {"2011-12-back": {"annual": {"2003-04": {"BACK": scaled(node)}}}}}, report)
    (s,) = report.sections
    assert s.failures == [] and any(n.startswith("Allowed (1): ") and "back series" in n for n in s.notes)
    assert s.allowed == [{"reason": checks.BACK_ADDITIVITY, "cases": 1}]  # counted in validation_summary.json
    (f,) = identity_failures(node, "2011-12-back", "2004-05", "BACK")
    assert "8 industries = total GVA" in f


# ---- annual GDP growth --------------------------------------------------------------------------------------------

def gdp_growth_ds(series, published_real, now=107.0):
    return {"data": {series: {"annual": {
        "2023-24": {"RE1": {"gdp": {"con": 100.0}}, "FINAL": {"gdp": {"con": 101.0}}},
        "2024-25": {"PE": {"gdp": {"con": now}, "growth": {"gdp": {"real": published_real}}}},
    }}}}


def test_gdp_growth_matching_an_estimate_of_the_year_before_passes():
    checked, failures, notes = run(checks.check_growth, gdp_growth_ds("2011-12", 7.0))
    assert (checked, failures) == (1, []) and "PE vs RE1 (1)" in notes[0]


def test_gdp_growth_far_from_the_levels_fails():
    _, failures, _ = run(checks.check_growth, gdp_growth_ds("2011-12", 8.6))
    assert failures == ["2011-12 series, 2024-25 PE: published real growth 8.6%, levels give RE1 7.00%, FINAL 5.94%"]


def test_gdp_growth_a_little_off_is_listed_for_review_in_the_old_series():
    _, failures, notes = run(checks.check_growth, gdp_growth_ds("2011-12", 7.3))
    assert failures == [] and any("within 1.5 points" in n for n in notes)


def test_gdp_growth_without_last_years_levels_is_noted():
    ds = {"data": {"2022-23": {"annual": {"2022-23": {"FINAL": {"gdp": {"con": 1.0}, "growth": {"gdp": {"real": 7.0}}}}}}}}
    _, failures, notes = run(checks.check_growth, ds)
    assert failures == [] and any("not checkable (no 2021-22 levels)" in n for n in notes)


# ---- back series join -------------------------------------------------------------------------------------------

def join_ds(back_cur=100.0, years=("2010-11", "2011-12", "2012-13")):
    return {"data": {
        "2011-12-back": {"annual": {"2011-12": {"BACK": {"gdp": {"cur": back_cur, "con": 100.0}}}}},
        "2011-12": {"annual": {"2011-12": {"RE3": {"gdp": {"cur": 99.0, "con": 100.0}},
                                           "ADD": {"gdp": {"cur": 100.0, "con": 100.0}}}}},
    }, "long_run": [{"year": y} for y in years]}


def test_back_series_that_joins_the_latest_estimate_passes():
    assert run(checks.check_join, join_ds())[:2] == (3, [])


def test_back_series_that_does_not_join_fails():
    _, failures, _ = run(checks.check_join, join_ds(back_cur=150.0))
    assert failures == ["2011-12 GDP (cur): back series 150, current series ADD 100"]


def test_long_run_series_with_a_gap_fails():
    _, failures, _ = run(checks.check_join, join_ds(years=("2009-10", "2011-12")))
    assert failures == ["long-run series has gaps: ['2009-10 → 2011-12']"]


# ---- budget -----------------------------------------------------------------------------------------------------

def assumption(**kw):
    return {"budget": "2024-25", "printed_year": "2024-2025", "gdp_crore": 110.0, "base_gdp_crore": 100.0,
            "growth_pct": 10.0, **kw}


@pytest.fixture
def one_budget(monkeypatch):
    monkeypatch.setattr(checks, "BUDGETS", [2024])


def test_budget_assumption_that_reproduces_passes(one_budget):
    assert run(checks.check_budget, {"budget_assumptions": [assumption()]})[:2] == (2, [])


def test_budget_without_an_assumption_fails(one_budget):
    _, failures, _ = run(checks.check_budget, {"budget_assumptions": []})
    assert failures == ["Budget 2024-25: GDP assumption not found in Budget at a Glance"]


def test_budget_growth_that_does_not_follow_from_its_two_figures_fails(one_budget):
    _, failures, _ = run(checks.check_budget, {"budget_assumptions": [assumption(growth_pct=10.5)]})
    assert failures == ["Budget 2024-25: ₹110 crore is 10.00% over ₹100 crore; printed 10.5%"]


def test_budget_sentence_for_another_year_fails(one_budget):
    _, failures, _ = run(checks.check_budget, {"budget_assumptions": [assumption(printed_year="2023-2024")]})
    assert failures == ["Budget 2024-25: sentence is for 2023-2024"]


# ---- spending side ----------------------------------------------------------------------------------------------

def test_large_statistical_discrepancy_is_listed_for_review():
    def ds(gdp):
        node = {k: {"cur": v} for k, v in (("pfce", 60.0), ("gfce", 10.0), ("gfcf", 30.0), ("stocks", 1.0),
                                            ("valuables", 1.0), ("exports", 20.0), ("imports", 22.0), ("gdp", gdp))}
        return {"data": {"2022-23": {"annual": {"2023-24": {"FINAL": node}}}}}
    checked, failures, notes = run(checks.check_expenditure, ds(100.0))
    assert (checked, failures, len(notes)) == (1, [], 1)  # spending adds up to GDP: nothing listed
    _, failures, notes = run(checks.check_expenditure, ds(110.0))
    assert failures == [] and notes[1] == "2022-23 series, 2023-24 FINAL: discrepancy +9.1% of GDP (current prices)"


# ---- source rows ------------------------------------------------------------------------------------------------

def test_unknown_source_problem_fails_and_a_known_one_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(checks, "DATA", tmp_path)
    (tmp_path / "national_accounts.csv").write_text("header\nrow\n")
    known = "nas/2011-12/Current/Annually/ind19: row with year '1999' left out (not a fiscal year)"
    unknown = "nas/2022-23/Current/Annually/ind05: unknown estimate stage 'Third Advance Estimates'"
    checked, failures, notes = run(checks.check_source, {"source_problems": [known, unknown], "duplicate_rows": []})
    assert checked == 1 and failures == [unknown]
    assert notes[0].startswith("Allowed (1): MoSPI's API returns one Gross National Disposable Income")
    assert notes[0].endswith(f" Cases:\n  - {known}")


# ---- forecasts --------------------------------------------------------------------------------------------------

def forecast_run(monkeypatch, texts, **record):
    from gdp_pipeline import forecasts
    r = {"fiscal_year": "2025-26", "statement": "April 2025", "url": "https://rbi.example/p.pdf",
         "quote": "real GDP growth for 2025-26 is projected at 6.5 per cent", "value": 6.5, **record}
    monkeypatch.setattr(forecasts, "SOURCES", {"rbi": "RBI"})
    monkeypatch.setattr(forecasts, "load", lambda name: [r])
    monkeypatch.setattr(forecasts, "document_texts", lambda manifest, url, page: texts)
    return run(checks.check_forecasts, {})


def test_forecast_quoted_from_its_document_passes(monkeypatch):
    text = ["... Taking all these factors into consideration, real GDP growth for 2025-26 is projected at 6.5 per cent ..."]
    assert forecast_run(monkeypatch, text)[:2] == (2, [])


def test_forecast_quote_not_in_its_document_fails(monkeypatch):
    _, failures, _ = forecast_run(monkeypatch, ["real GDP growth for 2025-26 is projected at 6.7 per cent"])
    assert len(failures) == 1 and failures[0].startswith("RBI, April 2025 → 2025-26: quote not found")


def test_forecast_figure_not_in_its_quote_fails(monkeypatch):
    text = ["real GDP growth for 2025-26 is projected at 6.5 per cent"]
    _, failures, _ = forecast_run(monkeypatch, text, value=6.7)
    assert failures == ["RBI, April 2025 → 2025-26: recorded [6.7] not all in the quote "
                        "“real GDP growth for 2025-26 is projected at 6.5 per cent”"]


def test_forecast_document_not_downloaded_fails(monkeypatch):
    _, failures, _ = forecast_run(monkeypatch, None)
    assert failures == ["RBI, April 2025 → 2025-26: document not downloaded (https://rbi.example/p.pdf)"]


def test_back_series_rule_never_allows_a_missing_or_unknown_subindustry():
    structural = "2011-12-back series, 1990-91, BACK: sub-industries of transport_comm: missing storage"
    assert checks.EXCEPTIONS.reason("identity", structural) is None
    off_sum = ("2011-12-back series, 1990-91, BACK, constant prices: sub-industries = industry — printed 100, "
               "parts give 95 (+5)")
    assert checks.EXCEPTIONS.reason("identity", off_sum) == checks.BACK_ADDITIVITY


def test_quarterly_rate_matches_rounded_or_truncated():
    assert checks.quarterly_rate_matches(7.66, 7.7)   # rounded
    assert checks.quarterly_rate_matches(7.66, 7.6)   # truncated, as in the 2011-12 series
    assert checks.quarterly_rate_matches(-2.36, -2.3)  # truncated toward zero
    assert not checks.quarterly_rate_matches(7.66, 7.5)


def test_known_exceptions_no_longer_needed_are_listed():
    def sections():
        report = checks.Report(checks.INTRO)
        checks.check_unused_exceptions(report)
        return report.sections

    checks.EXCEPTIONS.reset()
    (s,) = sections()
    assert "no longer needed" in s.title and s.failures == [] and len(s.notes) == len(checks.KNOWN_EXCEPTIONS)
    for check, prefix in checks.KNOWN_EXCEPTIONS:
        assert checks.EXCEPTIONS.reason(check, prefix + " (as printed)")
    assert sections() == []
    checks.EXCEPTIONS.reset()

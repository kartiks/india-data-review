"""Each national-accounts check fed a small dataset with one thing wrong: it must fail, and say what is wrong."""

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


def test_quarterly_growth_off_by_a_tenth_is_listed_for_review_in_the_old_series():
    _, failures, notes = run(checks.check_quarters, quarters_ds("2011-12", 7.1))
    assert failures == [] and any("within 1.5 points" in n for n in notes)


def test_quarterly_growth_far_from_levels_fails_in_the_old_series():
    _, failures, _ = run(checks.check_quarters, quarters_ds("2011-12", 8.7))
    assert failures == ["2011-12 series, 2024-25 Q1: published real growth 8.7%, levels give 7.00%"]

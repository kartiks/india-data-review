"""Which hand-added releases are due, from fixed dates and small hand-made records (no network)."""

from datetime import date

import pytest

from gdp_pipeline import due
from pipeline_common.due import DUE

SURVEYS = [{"fiscal_year": "2026-27", "published_date": "2026-01-29"}]
RBI = [{"date": "2026-08-05"}, {"date": "2026-10-07"}]
NAS = [{"date": "2026-08-31"}]


def ds(years=("2024-25", "2025-26"), population=("2024-25", "2025-26")) -> dict:
    return {"data": {s: {"annual": {y: {} for y in years}} for s in due.SERIES},
            "population": {"by_series": {s: {y: 1.0 for y in population} for s in due.SERIES}}}


def run(today, data=None, latest_budget=2026, surveys=SURVEYS, statements=RBI, nas=NAS):
    return due.check(today, data or ds(), latest_budget, surveys, statements, nas)


def due_items(f: due.Findings, what: str) -> list[str]:
    return [d for d in f.due if d.startswith(what)]


def test_nothing_due_on_the_committed_records():
    """The repository's own forecast and population records, on a fixed date (the data and LATEST_BUDGET are fixed
    too, so a refresh bringing a new year in cannot fail this test)."""
    f = due.check(date(2026, 11, 8), ds(), latest_budget=2026)
    assert f.due == [] and len(f.ok) == 4 and f.finish() == 0


def test_economic_survey_due_with_the_budget_or_from_august():
    survey = "Economic Survey"
    assert due_items(run(date(2027, 2, 7)), survey) == []  # the budget is not added yet: budget_pipeline.due says so
    assert due_items(run(date(2027, 2, 7), latest_budget=2027), survey) == [
        "Economic Survey with the projection for 2027-28: not in forecast_sources/economic_survey.json; the data has "
        "Union Budget 2027-28 (LATEST_BUDGET), and the survey comes out the day before the budget. Add it to "
        "gdp/pipeline/gdp_pipeline/forecast_sources/economic_survey.json (gdp/README.md, 'Adding a forecast')."]
    assert due_items(run(date(2027, 7, 31)), survey) == []
    assert "late January (July after an election), and it is 1 August 2027" in due_items(run(date(2027, 8, 1)), survey)[0]


def test_rbi_statement_due_after_the_longest_gap():
    assert run(date(2026, 12, 11)).due == []  # 65 days after 7 October
    f = run(date(2026, 12, 12))
    assert f.due == ["RBI monetary policy statement: the latest recorded is of 7 October 2026, 66 days ago, and they come "
                     "every 56 to 65 days. Add the new statement's projections to "
                     "gdp/pipeline/gdp_pipeline/forecast_sources/rbi.json (gdp/README.md, 'Adding a forecast')."]


def test_population_due_for_a_year_without_one():
    f = due_items(run(date(2027, 1, 10), data=ds(years=("2025-26", "2026-27"), population=("2025-26",))), "Population")
    assert len(f) == len(due.SERIES)
    assert f[-1].startswith("Population for 2026-27 (2022-23 series): MoSPI's national accounts have the year")


def test_national_accounts_statistics_due_from_october():
    old = [{"date": "2025-09-02"}]
    assert run(date(2026, 9, 30), nas=old).due == []
    f = run(date(2026, 10, 1), nas=old)
    assert len(f.due) == 1 and f.due[0].startswith("National Accounts Statistics 2026, per-capita statement")
    assert run(date(2026, 10, 1)).due == []  # 2026's is added


def test_the_command(monkeypatch, capsys):
    monkeypatch.setattr(due, "check", lambda today: due.Findings(due=["a", "b"], ok=["c"]))
    assert due.main([]) == DUE == 11
    assert capsys.readouterr().out == "ok: c\nDUE: a\nDUE: b\n"
    for argv, code in ((["--help"], 0), (["--bogus"], 2)):
        with pytest.raises(SystemExit) as e:
            due.main(argv)
        assert e.value.code == code

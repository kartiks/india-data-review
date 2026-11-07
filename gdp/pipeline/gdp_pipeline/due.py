"""Releases this area adds by hand that are probably out but not yet added (pipeline_common.due has the output
and exit codes). Run it after the build, so data/gdp.json holds the latest national accounts:

    uv run --locked python -m gdp_pipeline.due

From dates alone, no downloads:
- Economic Survey: the survey for the year of the latest budget in the data (LATEST_BUDGET; it comes out the day
  before the budget), and from 1 August the survey for the year that started in April (it is out by then even after
  an election, when it comes with the full budget in July).
- RBI monetary policy statement: due when the latest recorded is RBI_MAX_GAP_DAYS old (the MPC meets six times a
  year; statements have come 56 to 65 days apart).
- Population, from MoSPI's press note: a year in the national accounts (the weekly refresh brings MoSPI's First
  Advance Estimates in January) with no population, so no figures per person.
- National Accounts Statistics per-capita statement: from 1 October, if none of this year's is added (published in
  August or September).
"""

import argparse
import json
import sys
from datetime import date, timedelta

from pipeline_common import log as pipeline_log
from pipeline_common.due import Findings
from pipeline_common.text import fy

from . import forecasts
from .build import DATA
from .population import SERIES
from .population_read import NAS_STATEMENTS
from .sources import LATEST_BUDGET

RBI_MAX_GAP_DAYS = 66  # one day more than the longest gap between statements since 2023 (65 days)
SURVEY_BACKSTOP = (8, 1)  # (month, day) from which the survey for the year that started in April is due
NAS_FROM = (10, 1)  # (month, day) from which this year's National Accounts Statistics statement is due
FORECAST_HOWTO = "gdp/README.md, 'Adding a forecast'"
POPULATION_HOWTO = "gdp/README.md, \"Adding a year's population\""


def day(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


def check_survey(today: date, surveys: list[dict], latest_budget: int, out: Findings) -> None:
    backstop = today.year if today >= date(today.year, *SURVEY_BACKSTOP) else today.year - 1
    start = max(latest_budget, backstop)
    if any(r["fiscal_year"] == fy(start) for r in surveys):
        out.ok.append(f"Economic Survey: the projection for {fy(start)} is recorded")
        return
    why = (f"the data has Union Budget {fy(start)} (LATEST_BUDGET), and the survey comes out the day before the budget"
           if start == latest_budget else
           f"it comes out in late January (July after an election), and it is {day(today)}")
    out.due.append(f"Economic Survey with the projection for {fy(start)}: not in forecast_sources/economic_survey.json; "
                   f"{why}. Add it to gdp/pipeline/gdp_pipeline/forecast_sources/economic_survey.json ({FORECAST_HOWTO}).")


def check_rbi(today: date, statements: list[dict], out: Findings) -> None:
    latest = max(date.fromisoformat(r["date"]) for r in statements)
    if (today - latest).days < RBI_MAX_GAP_DAYS:
        out.ok.append(f"RBI monetary policy statement: the latest recorded is of {day(latest)}; the next is due by about "
                      f"{day(latest + timedelta(days=RBI_MAX_GAP_DAYS))}")
        return
    out.due.append(f"RBI monetary policy statement: the latest recorded is of {day(latest)}, {(today - latest).days} days "
                   f"ago, and they come every 56 to 65 days. Add the new statement's projections to "
                   f"gdp/pipeline/gdp_pipeline/forecast_sources/rbi.json ({FORECAST_HOWTO}).")


def check_population(ds: dict, out: Findings) -> None:
    pop = ds.get("population", {}).get("by_series", {})
    missing = {}
    for series in SERIES:
        if years := [y for y in ds["data"].get(series, {}).get("annual", {}) if y not in pop.get(series, {})]:
            missing[series] = sorted(years)
    if not missing:
        out.ok.append("Population: every year in the national accounts has one")
        return
    for series, years in missing.items():
        out.due.append(f"Population for {', '.join(years)} ({series} series): MoSPI's national accounts have the year "
                       "but the data has no population for it, so no figures per person. Add it from MoSPI's press note "
                       f"to gdp/pipeline/gdp_pipeline/population_sources/mospi_press_notes.json ({POPULATION_HOWTO}).")


def check_nas(today: date, statements: list[dict], out: Findings) -> None:
    latest = max((s["date"] for s in statements), default="")
    if today < date(today.year, *NAS_FROM) or latest >= f"{today.year}-01-01":
        out.ok.append(f"National Accounts Statistics: the latest per-capita statement added is of {latest or 'none'}")
        return
    out.due.append(f"National Accounts Statistics {today.year}, per-capita statement: published in August or September, "
                   f"and the latest added is of {latest or 'none'}. Download it in a browser, add it to NAS_STATEMENTS "
                   f"in gdp/pipeline/gdp_pipeline/population_read.py and run python -m gdp_pipeline.population --add "
                   f"({POPULATION_HOWTO}).")


def check(today: date, ds: dict | None = None, latest_budget: int = LATEST_BUDGET,
          surveys: list[dict] | None = None, statements: list[dict] | None = None,
          nas: list[dict] | None = None) -> Findings:
    out = Findings()
    if ds is None:
        ds = json.loads((DATA / "gdp.json").read_text())
    check_survey(today, forecasts.load("economic_survey") if surveys is None else surveys, latest_budget, out)
    check_rbi(today, forecasts.load("rbi") if statements is None else statements, out)
    check_population(ds, out)
    check_nas(today, NAS_STATEMENTS if nas is None else nas, out)
    return out


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    pipeline_log.setup(__package__)
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    return check(today or date.today()).finish()


if __name__ == "__main__":
    sys.exit(main())

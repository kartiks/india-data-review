"""Checks of the population and the figures per person (population.py), added to gdp/data/validation_report.md by
check(). Every source must read cleanly (the readers' problems are failures; every quoted press-note row must be
found on its PDF page, with one figure for each year), and:

1. The projections table reads cleanly: 2011 to 2036, persons = male + female, rising.
2. Within each table, every per-person figure implies the same population, and it rounds to the printed one.
3. MoSPI's documents (and the RBI's reprint) agree on a year's population within a series.
4. The population used here agrees with the RBI's reprint (to the lakh).
5. MoSPI's own population equals the projection up to 2021-22 where a source covers it (2020-21, 2021-22), and from
   2022-23 is within PROJECTION_GAP_MAX (0.5%) of it: a quoted row under the wrong year would be about 0.9% off. This
   assumes MoSPI's population stays close to the 2019 projections. When MoSPI moves to figures based on the next
   census, a correctly quoted year may fail it: check the years first, then raise PROJECTION_GAP_MAX with a note.
6. Per-person figures here reproduce, to within PER_PERSON_TOL (₹2), every one MoSPI or the RBI printed whose total is
   the same estimate as the API's latest. Totals MoSPI has revised since are not compared; the report says how many,
   for each series.
7. For review: years with national accounts but no population.

Each check returns (checks, failures, notes).
"""

import json
from pathlib import Path

from pipeline_common.text import fy

from . import population as P
from .population import (IMPLIED_TOL, MEASURES, MISREAD_GAP, PER_PERSON_TOL, PROJECTIONS_UNTIL, SERIES, implied,
                         table_population)

ROOT = Path(__file__).resolve().parents[2]

LAKH_TOL = 0.501  # lakh: population against the RBI's figure, printed to the nearest lakh
MILLION_TOL = 0.5  # million: an implied population against the one printed to the nearest million
PROJECTION_TOL = 1e-4  # MoSPI's population (as implied) against the projection, 2011-12 to 2021-22
# MoSPI's own population from 2022-23 is 0.1-0.2% above the projection; a year's figure further away than this
# means a quoted row is under the wrong year (a year's population growth is about 0.9%).
PROJECTION_GAP_MAX = 0.005

Result = tuple[int, list[str], list[str]]


def check(ds: dict, report, manifest: dict | None = None) -> None:
    manifest = manifest or json.loads((ROOT / "sources" / "manifest.json").read_text())
    pop, src = P.population(manifest)
    checked, failures, notes = src["note_checked"], list(src["problems"]), []
    for c, f, n in (check_projections(src), check_tables(src), check_documents_agree(src), check_rbi_reprint(pop, src),
                    check_against_projections(pop, src), check_published_per_person(ds, src), missing_years(ds, pop)):
        checked += c
        failures += f
        notes += n
    report.add("Population and figures per person", checked, failures, notes)


def check_projections(src: dict) -> Result:
    """1. The projections table reads cleanly: 2011 to 2036, persons = male + female, rising."""
    proj = src["projections"]
    years = sorted(proj)
    checked, failures = 1, []
    if years != [fy(y) for y in range(2011, 2037)]:
        failures.append(f"projections: years read {years[:1]}…{years[-1:]} ({len(years)}), expected 2011 to 2036")
    for i, y in enumerate(years):
        checked += 1
        p = proj[y]
        if abs(p["male"] + p["female"] - p["persons"]) > 1:
            failures.append(f"projections {y}: male + female = {p['male'] + p['female']:,.0f}, persons {p['persons']:,.0f}")
        if i and p["persons"] <= proj[years[i - 1]]["persons"]:
            failures.append(f"projections {y}: population does not rise from {years[i - 1]}")
    return checked, failures, []


def check_tables(src: dict) -> Result:
    """2. Within each table, every per-person figure implies the same population, and it rounds to the printed one."""
    checked, failures = 0, []
    for t in src["notes"] + src["rbi"]:
        for y in t["years"]:
            vals = implied(t, y)
            if not vals:
                continue
            checked += 1
            label = f"{t['document']}{', ' + t['statement'] if t['statement'] else ''}, {y}"
            if max(vals) / min(vals) - 1 > IMPLIED_TOL:
                failures.append(f"{label}: per-person figures imply different populations "
                                f"({', '.join(f'{v:.3f}' for v in vals)} million)")
            printed = t["figures"].get("population", {}).get(y)
            if printed is not None and abs(vals[0] - printed) > MILLION_TOL:
                failures.append(f"{label}: implied population {vals[0]:.3f} million, printed {printed:,.0f}")
    return checked, failures, []


def check_documents_agree(src: dict) -> Result:
    """3. MoSPI's documents agree on a year's population within a series (so a revision of the totals, as in National
    Accounts Statistics, kept the population of the earlier press note)."""
    checked, failures = 0, []
    by_year: dict[tuple, list] = {}
    for t in src["notes"] + src["rbi"]:
        for y in t["years"]:
            million = table_population(t, y)
            if million is not None:
                by_year.setdefault((t["base"], y), []).append((million, t["document"]))
    for (series, y), vals in sorted(by_year.items()):
        docs = {d for _, d in vals}
        if len(docs) < 2:
            continue
        checked += 1
        lo, hi = min(v for v, _ in vals), max(v for v, _ in vals)
        if hi / lo - 1 > IMPLIED_TOL:
            failures.append(f"{series} series, {y}: MoSPI's documents (or the RBI's reprint) give different populations: "
                            + "; ".join(f"{v:.3f} million ({d})" for v, d in vals))
    return checked, failures, []


def check_rbi_reprint(pop: dict, src: dict) -> Result:
    """4. Population used here, against the RBI's reprint (to the lakh): both the projections and MoSPI's own."""
    checked, failures = 0, []
    for t in src["rbi"]:
        for y, lakh in t["figures"].get("population_lakh", {}).items():
            p = pop.get(t["base"], {}).get(y)
            if not p:
                continue
            checked += 1
            if abs(p["million"] * 10 - lakh) > LAKH_TOL:
                failures.append(f"{t['base']} series, {y}: population {p['million']:.3f} million here, "
                                f"RBI {lakh:,.0f} lakh")
    return checked, failures, []


def check_against_projections(pop: dict, src: dict) -> Result:
    """5. MoSPI's own population against the projection: equal up to 2021-22 (checked for the years a source covers,
    so the projections are taken as MoSPI's population for the earlier years too); from 2022-23 a little above, and
    never far off (which would mean a quoted row under the wrong year)."""
    proj = src["projections"]
    checked, failures, notes = 0, [], []
    covered = set()
    for t in src["rbi"] + src["notes"]:
        for y in t["years"]:
            million = table_population(t, y)
            if million is None or y not in proj:
                continue
            checked += 1
            diff = million / (proj[y]["persons"] / 1000) - 1
            label = (f"{t['base']} series, {y}: MoSPI's population ({'printed' if t.get('exact_population') else 'implied'}, "
                     f"{million:.3f} million, {t['document']})")
            if y <= PROJECTIONS_UNTIL:
                covered.add(y)
                if abs(diff) > PROJECTION_TOL:
                    failures.append(f"{label} differs from the projection ({proj[y]['persons'] / 1000:.3f}) by {diff:+.3%}")
            elif abs(diff) > PROJECTION_GAP_MAX:
                failures.append(f"{label} is {diff:+.2%} from the projection ({proj[y]['persons'] / 1000:.3f}): "
                                "check the years of the quoted statement")
    yrs = sorted(covered)
    notes.append(f"MoSPI's population equals the projection in {' and '.join([', '.join(yrs[:-1]), yrs[-1]] if len(yrs) > 1 else yrs) or 'no year'} (the years a "
                 f"source here covers); earlier years up to {PROJECTIONS_UNTIL} use the projection without a check.")
    for series, years_ in pop.items():
        later = [(y, p) for y, p in years_.items() if p["source"] == "mospi" and y in proj]
        if later:
            notes.append(f"{series} series: MoSPI's population from 2022-23 is above the 2019 projections ("
                         + "; ".join(f"{y}: {p['million']:,.1f} million against {proj[y]['persons'] / 1000:,.1f}"
                                     for y, p in later) + ").")
    return checked, failures, notes


def check_published_per_person(ds: dict, src: dict) -> Result:
    """6. Per-person figures here reproduce every published one where the published total is the same estimate as the
    API's latest. Totals revised since are not compared (the per-person figure then uses the revised total and the
    published population)."""
    checked, failures, notes = 0, [], []
    counts: dict[str, list[int]] = {s: [0, 0] for s in SERIES}
    for series, y, stage, m, prices, ours, pub, doc, same in P.comparisons(ds["data"], src):
        if series not in counts:
            continue
        if same is None:
            checked += 1
            failures.append(f"{series} series, {y}, {MEASURES[m]} at {'current' if prices == 'cur' else 'constant'} "
                            f"prices: the total behind {doc}'s per-person figure ({pub:,.0f}) is more than "
                            f"{MISREAD_GAP:.0%} from MoSPI's latest; a misread row, unit or section, not a revision")
            continue
        if not same:
            counts[series][1] += 1
            continue
        checked += 1
        counts[series][0] += 1
        if ours is None or abs(ours - pub) > PER_PERSON_TOL:
            failures.append(f"{series} series, {y} ({stage}), {MEASURES[m]} per person at "
                            f"{'current' if prices == 'cur' else 'constant'} prices: {ours} here, {pub:,.0f} in {doc}")
    for series, (done, skipped) in counts.items():
        yrs = sorted(ds.get("population", {}).get("checked", {}).get(series, {}))
        notes.append(f"{series} series: {done} published per-person figures reproduced to within ₹{PER_PERSON_TOL}"
                     f"{' (' + ', '.join(yrs) + ')' if yrs else ''}; {skipped} are for an earlier estimate than the "
                     "API's latest and are not compared.")
    return checked, failures, notes


def missing_years(ds: dict, pop: dict) -> Result:
    """7. Years with national accounts but no population (for review: add the year from MoSPI's press note)."""
    notes = []
    for series in SERIES:
        missing = [y for y in ds["data"].get(series, {}).get("annual", {}) if y not in pop[series]]
        if missing:
            notes.append(f"{series} series: no population for {', '.join(sorted(missing))}, so no per-person figures; "
                         "add the year from MoSPI's press note (population_sources/mospi_press_notes.json).")
    return 0, [], notes

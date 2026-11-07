"""Population, for figures per person: GDP, national income and household spending per person.

MoSPI divides its national totals by India's population at the middle of the financial year (1 October). It
prints that population in its press notes, rounded to the million; the RBI's Handbook of Statistics on the Indian
Economy reprints it to the lakh. The population differs a little between the two GDP series, so it is kept per
series and year:

- 2011-12 series, 2011-12 to 2021-22: the official projections (Census of India 2011, Population Projections for
  India and States 2011-2036, Report of the Technical Group on Population Projections, November 2019, Table 14:
  population on 1 October). MoSPI's population equals the projection in 2020-21 and 2021-22, the years the RBI's
  reprint below covers; for the earlier years it is assumed to be the projection too (MoSPI's latest figures for
  those years were compiled after the 2019 projections were published).
- Later years, and the 2022-23 series: MoSPI's own population, as printed in its National Accounts Statistics
  per-capita statement (to the thousand; downloaded by hand, NAS_STATEMENTS), or as its own per-person figures
  imply it (its GDP divided by its GDP per person, to within a few thousand people) in its press notes
  (population_sources/mospi_press_notes.json, each row quoted and found in the document), or, where no press note
  here covers the year, from the RBI's reprint of MoSPI's tables. Per-person figures here then reproduce MoSPI's to
  the rupee whenever the totals are the same estimate; the years where that is checked are listed in gdp.json
  (population.checked). A year whose total MoSPI has revised since the document quoted is not checked: its figure
  divides the revised total by that document's population (the site's Per person page says so).

MoSPI's documents agree on population: for 2022-23 to 2024-25, the June 2026 press note's implied population and NAS
2026's printed one are within 3,000 people (the implied figure's own precision), as MoSPI kept its population when it
revised the totals in August. Where they agree, the printed figure is used. A NAS statement prints no totals: its
unrounded per-person figure times its population gives the total back (to within ₹1 crore of the API's in NAS 2026),
which is how its figures are matched to the API's estimate.

Which document gives each year's population today (sources/raw/population/; gdp.json names each year's source in
population.by_series):

    2011-12 series, 2011-12 to 2021-22   the 2019 projections, Table 14, PDF page 125 (projections-2019.pdf)
    2022-23 series, 2022-23 to 2024-25   MoSPI, National Accounts Statistics 2026 (31 August 2026), Statement 1.2:
                                         Per capita income, product and final consumption, printed to the thousand
                                         (nas-2026-statement-1.2.xlsx, downloaded by hand)
    2011-12 series, 2023-24 to 2025-26;  MoSPI's press notes, implied by their per-person figures (press-note-*.pdf,
    2022-23 series, 2025-26              rows quoted in population_sources/mospi_press_notes.json)
    2011-12 series, 2022-23              RBI, Handbook of Statistics on the Indian Economy 2025-26, Tables 1 and 2,
                                         reprinting MoSPI's (rbi-hbs-table-1.xlsx, rbi-hbs-table-2.xlsx)

From 2022-23 MoSPI's population is about 0.1-0.2% above the 2019 projections, so in the 2011-12 series population
grows 1.05% in 2022-23 (0.91% from one projection to the next); MoSPI's own per-person figures have the same step.

Per-person figures are worked out for the latest estimate of each year (earlier estimates were divided by the
population known at the time, which is not kept here): the total (from MoSPI's API, refreshed weekly) divided by the
population. Net national income is not in the API; it is GNI less depreciation, worked out as NDP + GNI − GDP (the
same thing, and available in the years MoSPI's API gives no depreciation figure).

A year with national accounts but no population yet (a new year's first estimate) has no per-person figures; the
validation report lists it, to be added from MoSPI's press note, and the site shows the latest year that has one.

The documents and how they are read: population_read.py. The checks: population_checks.py.
"""

import csv
from pathlib import Path

from . import population_read as R
from .ids import STAGE_ORDER, latest_stage
from .population_read import NAS_STATEMENTS, PROJECTIONS, RBI_TABLES, press_notes

# The last year for which MoSPI's population is the projection (from 2022-23 it uses its own, higher figures).
PROJECTIONS_UNTIL = "2021-22"

MEASURES = {"gdp": "GDP", "gni": "GNI", "nni": "NNI", "pfce": "PFCE"}
SERIES = ("2011-12", "2022-23")

# Tolerances.
IMPLIED_TOL = 2e-5  # population implied by different per-person figures in one table (each rounded to ₹1)
SAME_ESTIMATE_TOL = 2  # ₹ crore: a published total and the API's total are the same estimate
# A statement that prints population to the thousand but no totals is matched by per person × population; if MoSPI
# divided by an unrounded population, that total is off by up to half a thousand people's worth (about ₹12 crore).
POPULATION_ROUNDING = 0.0005  # million
# For a statement with no printed totals (NAS), a total (per person × population) further than this from the API's
# is not a revision but a misread (wrong row, unit or section). Press-note totals are quoted and found in the PDF, so
# they are not tested this way: a large real revision of one (7.5% has happened) must not stop the weekly refresh.
MISREAD_GAP = 0.25
PER_PERSON_TOL = 2  # ₹: a per-person figure here and MoSPI's printed one


def table_population(table: dict, year: str) -> float | None:
    """MoSPI's population in a table: printed (to the thousand) where it is exact, else implied by its figures."""
    if table.get("exact_population"):
        return table["figures"].get("population", {}).get(year)
    vals = implied(table, year)
    return vals[0] if vals else None


def implied(table: dict, year: str) -> list[float]:
    """Population (million) implied by each total and its per-person figure in a table."""
    f = table["figures"]
    out = []
    for m in MEASURES:
        if year in f.get(m, {}) and f.get(f"pc_{m}", {}).get(year):
            out.append(f[m][year] * 1e7 / f[f"pc_{m}"][year] / 1e6)
    return out


def population(manifest: dict) -> tuple[dict, dict]:
    """{series: {year: {million, source, ...}}} and the parsed sources (for the checks)."""
    proj, proj_problems = R.read_projections(manifest)
    notes, note_problems, note_checked = R.read_notes(manifest)
    rbi, rbi_problems = R.read_rbi(manifest)
    nas, nas_problems = R.read_nas(manifest)
    notes = notes + nas  # MoSPI's own documents, ordered by date below
    out: dict[str, dict] = {s: {} for s in SERIES}
    for y, p in proj.items():
        if y <= PROJECTIONS_UNTIL:
            out["2011-12"][y] = {"million": round(p["persons"] / 1000, 3), "source": "projections"}
    # MoSPI's own figures: its documents first (latest first), then the RBI's reprint for years none covers.
    for t in sorted(notes, key=lambda t: t["date"], reverse=True) + rbi:
        if t["base"] not in out:
            continue
        for y in t["years"]:
            million = table_population(t, y)
            if million is None or y in out[t["base"]] or y <= PROJECTIONS_UNTIL:
                continue
            printed = None if t.get("exact_population") else t["figures"].get("population", {}).get(y)
            lakh = t["figures"].get("population_lakh", {}).get(y)
            out[t["base"]][y] = {"million": round(million, 3), "source": "mospi", "document": t["document"],
                                 **({"printed_million": printed} if printed else {}),
                                 **({"printed_lakh": lakh} if lakh else {})}
    # A newer document's implied population replaces an exact printed one only if they disagree (they agree to within
    # the implied figure's precision when MoSPI kept its population; then the exact one is used).
    for t in notes:
        if not t.get("exact_population") or t["base"] not in out:
            continue
        for y in t["years"]:
            exact, chosen = table_population(t, y), out[t["base"]].get(y)
            from_exact = chosen and any(x["document"] == chosen["document"] and x.get("exact_population") for x in notes)
            if exact and chosen and not from_exact and abs(chosen["million"] / exact - 1) <= IMPLIED_TOL:
                out[t["base"]][y] = {"million": round(exact, 3), "source": "mospi", "document": t["document"]}
    sources = {"projections": proj, "notes": notes, "rbi": rbi, "note_checked": note_checked,
               "problems": proj_problems + note_problems + rbi_problems + nas_problems}
    return {s: dict(sorted(v.items())) for s, v in out.items()}, sources


def nni(node: dict, price: str) -> float | None:
    """Net national income = GNI − depreciation = NDP + GNI − GDP."""
    parts = [node.get(k, {}).get(price) for k in ("ndp", "gni", "gdp")]
    return parts[0] + parts[1] - parts[2] if all(v is not None for v in parts) else None


def totals(node: dict, price: str) -> dict:
    out = {m: node.get(m, {}).get(price) for m in ("gdp", "gni", "pfce")}
    out["nni"] = nni(node, price)
    return {m: v for m, v in out.items() if v is not None}


def per_person(node: dict, million: float) -> dict:
    """₹ per person, for each measure and price basis available."""
    out: dict = {}
    for price in ("cur", "con"):
        for m, v in totals(node, price).items():
            out.setdefault(m, {})[price] = round(v * 1e7 / (million * 1e6))
    return out


def write_csv(tree: dict, pop: dict, path: Path) -> int:
    """per_person.csv: one row per series, year, estimate and measure."""
    rows = []
    for series in SERIES:
        for year, stages in sorted(tree.get(series, {}).get("annual", {}).items()):
            for stage in sorted(stages, key=lambda s: STAGE_ORDER.get(s, 99)):
                for m, v in stages[stage].get("per_person", {}).items():
                    rows.append({"series": series, "year": year, "stage": stage, "measure": m,
                                 "population_million": pop[series][year]["million"],
                                 "current_prices_rupees": v.get("cur", ""), "constant_prices_rupees": v.get("con", "")})
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def comparisons(data: dict, src: dict):
    """Every published per-person figure against ours: (series, year, stage, measure, prices, ours, published,
    document, same_estimate). same_estimate: the published total equals the API's latest (so ours should equal it)."""
    for t in src["notes"] + src["rbi"]:
        series = t["base"]
        for y in t["years"]:
            stages = data.get(series, {}).get("annual", {}).get(y)
            if not stages:
                continue
            stage, node = latest(stages)
            for m in MEASURES:
                pub_total = t["figures"].get(m, {}).get(y)
                pub_pp = t["figures"].get(f"pc_{m}", {}).get(y)
                tol = SAME_ESTIMATE_TOL
                if pub_total is None and pub_pp is not None and t["figures"].get("population", {}).get(y) and t.get("exact_population"):
                    # No total printed: the unrounded per-person figure times the population gives it back.
                    pub_total = pub_pp * t["figures"]["population"][y] * 1e6 / 1e7
                    tol += pub_pp * POPULATION_ROUNDING * 1e6 / 1e7
                if pub_total is None or pub_pp is None:
                    continue
                ours_total = totals(node, t["prices"]).get(m)
                same = ours_total is not None and abs(ours_total - pub_total) <= tol
                if t.get("exact_population") and ours_total and not same and abs(pub_total / ours_total - 1) > MISREAD_GAP:
                    same = None  # not a revision: a misread (reported by the check)
                ours = node.get("per_person", {}).get(m, {}).get(t["prices"])
                yield series, y, stage, m, t["prices"], ours, pub_pp, t["document"], same


def build(manifest: dict, tree: dict) -> dict:
    """Adds per_person to the latest estimate of every year that has a population; returns the population block."""
    pop, src = population(manifest)
    for series in SERIES:
        for year, stages in tree.get(series, {}).get("annual", {}).items():
            p = pop[series].get(year)
            if not p:
                continue
            _, node = latest(stages)
            pp = per_person(node, p["million"])
            if pp:
                node["per_person"] = pp
    # Years whose per-person figures reproduce a published one (same estimate, within the tolerance).
    checked: dict[str, dict[str, str]] = {s: {} for s in SERIES}
    for series, y, _, _, _, ours, pub, doc, same in comparisons(tree, src):
        if same and ours is not None and abs(ours - pub) <= PER_PERSON_TOL:
            checked[series].setdefault(y, doc)
    return {
        "description": "Population at the middle of the financial year (1 October), in millions, as MoSPI uses it "
                       "for figures per person. Per-person figures are in rupees.",
        "by_series": pop,
        "sources": {
            "projections": {k: PROJECTIONS[k] for k in ("title", "table", "url")},
            "press_notes": [{k: n[k] for k in ("document", "date", "base", "url")} for n in press_notes()],
            "rbi": [{k: t[k] for k in ("title", "url")} for t in RBI_TABLES.values()],
            "nas": [{k: n[k] for k in ("document", "date", "base", "url")} for n in NAS_STATEMENTS],
        },
        "projections_until": PROJECTIONS_UNTIL,
        "checked": {s: dict(sorted(v.items())) for s, v in checked.items()},
    }


def latest(stages: dict) -> tuple[str, dict]:
    s = latest_stage(stages)
    return s, stages[s]


def main(argv: list[str] | None = None) -> None:
    """Add a hand-downloaded NAS statement: python -m gdp_pipeline.population --add <file> [--replace]."""
    import argparse

    from pipeline_common import log as pipeline_log

    from .fetch import add_by_hand  # the downloader is needed only here

    pipeline_log.setup(__package__)
    p = argparse.ArgumentParser(
        description="Add a National Accounts Statistics per-capita statement downloaded by hand (gdp/README.md, "
                    "Adding a year's population). The file goes under the last entry of NAS_STATEMENTS in "
                    "population_read.py.")
    p.add_argument("--add", metavar="FILE", required=True, help="the downloaded NAS statement (.xlsx)")
    p.add_argument("--replace", action="store_true", help="replace the file already added for that edition")
    args = p.parse_args(argv)
    add_by_hand(Path(args.add).expanduser(), NAS_STATEMENTS[-1]["key"], replace=args.replace)


if __name__ == "__main__":
    main()

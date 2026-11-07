"""RBI Handbook of Statistics on Indian States: every table read in its unit, state inflation against MoSPI's
indices, totals within their parts, and state GDP and income per person at current and constant prices."""

import re
from collections import defaultdict

from pipeline_common.report import Allowed, Report
from pipeline_common.text import fy_start, prev_fy

from ..rbi import RBI_STATE_TABLES

# points: RBI's state inflation (printed to one decimal) against the rate worked out from MoSPI's monthly indices,
# which are printed to one decimal too and averaged over the year
RBI_INFLATION_TOL = 0.15
NEW_SERIES_START = "2026-01"  # the first month of the base-2024 CPI (press releases); base 2012 ends the month before


def state_key(s: str) -> str:
    """One key for a state however a source spells it ('Andaman & Nicobar Islands', 'NCT of Delhi' ...)."""
    s = s.lower().replace("&", "and")
    s = re.sub(r"^the |^nct of |\bislands?\b", "", s)
    return re.sub(r"[^a-z]", "", s)


def check_rbi_read(ds: dict, report: Report) -> None:
    """Every table read, with enough states, in its unit and with its expected sub-titles, all from one edition."""
    recs = ds["rbi"]
    failures, notes, checked = list(ds["rbi_problems"]), [], 0
    editions = set(ds["rbi_editions"].values())
    for n, spec in RBI_STATE_TABLES.items():
        checked += 1
        rows = [r for r in recs if r["table"] == n]
        states = {r["state"] for r in rows}
        minimum = 18 if spec.id.startswith("wage") else 30
        if len(states) < minimum:
            failures.append(f"RBI table {n} ({spec.id}): {len(states)} states read, expected at least {minimum}")
        # The site looks figures up by variant and shows them in the table's unit.
        units = {r["unit"] for r in rows} - {spec.unit}
        variants = {r["variant"] for r in rows} - set(spec.variants)
        if units or variants:
            failures.append(f"RBI table {n} ({spec.id}): unexpected units {sorted(units)} or sub-titles {sorted(variants)} "
                            f"(expected {spec.unit}, {list(spec.variants)})")
    if len(editions) > 1:
        failures.append(f"RBI tables come from different editions: {sorted(editions)}")
    notes.append(f"Edition: {', '.join(sorted(editions))}. Tables {', '.join(str(n) for n in RBI_STATE_TABLES)}.")
    report.add("RBI state tables: every table read", checked, failures, notes)


# months of MoSPI's base-2012 state indices missing because of the April-May 2020 lockdown (June too for three states)
LOCKDOWN_MONTHS = {"2020-04", "2020-05", "2020-06"}
LOCKDOWN = (
    "MoSPI published no state index for April and May 2020 (the lockdown; June too for Manipur, Nagaland and "
    "Puducherry), so 2020-21, and 2021-22 compared with it, lack months. RBI's notes say it used fewer months for "
    "those years. Not compared."
)


def month_before(month: str, years: int = 1) -> str:
    return f"{int(month[:4]) - years}{month[4:]}"


def chained_indices(ds: dict) -> tuple[dict[str, dict[str, float]], dict[str, set[str]]]:
    """MoSPI's monthly general index (combined) by state key and month, on base 2012: the old series to December 2025,
    then the base-2024 press releases chained on with their year-on-year inflation (index a year earlier × (1 +
    inflation)), which is how the new series links to the old one month by month: states as first published, All
    India from the latest release's series. Also the months chained, by state."""
    idx: dict[str, dict[str, float]] = defaultdict(dict)
    for r in ds["cpi"]:
        if r["subgroup"] == "General-Overall" and r["sector"] == "Combined" and r["index"] is not None:
            idx[state_key(r["state"])][r["month"]] = r["index"]
    c = ds.get("cpi2024", {})
    # (month, state, combined inflation): each release's states, and All India from the latest release's series
    new = [(m, s["name"], s["values"][5]) for m, rel in c.get("releases", {}).items() for s in rel["states"]]
    new += [(x["month"], "All India", x["values"][5]) for x in c.get("series", []) if x["month"] >= NEW_SERIES_START]
    chained: dict[str, set[str]] = defaultdict(set)
    for month, name, inflation in sorted(new):
        k = state_key(name)
        prev = idx.get(k, {}).get(month_before(month))
        if month in idx.get(k, {}) or prev is None or inflation is None:
            continue
        idx[k][month] = prev * (1 + inflation / 100)
        chained[k].add(month)
    return idx, chained


def fy_months(fy: str) -> list[str]:
    y = fy_start(fy)
    return [f"{y}-{m:02d}" for m in range(4, 13)] + [f"{y + 1}-{m:02d}" for m in range(1, 4)]


def check_rbi_inflation(ds: dict, report: Report) -> None:
    """The handbook's average inflation by state (table 108) equals the change in the yearly average of MoSPI's
    monthly general index (combined), base 2012 chained on with the base-2024 releases. Every pair not compared is
    counted under its reason: lockdown months (allowed), a state with no MoSPI index under its name, or months not
    published yet; any other missing month is a failure."""
    failures, notes, checked, allowed = [], [], 0, Allowed(more_hint=" state-years")
    idx, chained = chained_indices(ds)
    latest = max((m for months in idx.values() for m in months), default="")
    no_state: dict[str, list[str]] = defaultdict(list)
    not_yet: dict[str, int] = defaultdict(int)
    with_chained = 0
    for r in ds["rbi"]:
        if r["table"] != 108 or r["value"] is None:
            continue
        k, fy = state_key(r["state"]), r["year"]
        months = fy_months(prev_fy(fy)) + fy_months(fy)
        have = idx.get(k, {})
        missing = [m for m in months if m not in have]
        if not have:
            no_state[r["state"]].append(fy)
            continue
        if missing:
            if set(missing) <= LOCKDOWN_MONTHS:
                allowed.add(LOCKDOWN, f"{r['state']} {fy}")
            elif min(missing) > latest:
                not_yet[fy] += 1
            elif (late := [m for m in missing if m >= NEW_SERIES_START]) == missing:
                no_state[r["state"]].append(f"{fy} (no base-2024 index for {late[0]} onward)")
            else:
                failures.append(f"{r['state']} {fy}: MoSPI's indices lack {', '.join(missing)}")
            continue
        checked += 1
        with_chained += bool(chained.get(k, set()) & set(months))
        a, b = (sum(have[m] for m in fy_months(y)) / 12 for y in (fy, prev_fy(fy)))
        calc = (a / b - 1) * 100
        if abs(calc - r["value"]) > RBI_INFLATION_TOL:
            failures.append(f"{r['state']} {fy}: RBI {r['value']}%, MoSPI's indices give {calc:.2f}%")
    if no_state:
        notes.append(f"Not compared, {sum(map(len, no_state.values()))} state-years: no MoSPI index under the "
                     f"handbook's state name: {dict(sorted(no_state.items()))}.")
    if not_yet:
        notes.append(f"Not compared yet (MoSPI's indices so far run to {latest}): {dict(sorted(not_yet.items()))}.")
    notes.append(f"From January {NEW_SERIES_START[:4]} the index is the base-2024 series from MoSPI's press releases "
                 f"(each state as first published), chained to base 2012 with its year-on-year inflation; "
                 f"{with_chained} comparisons use chained months.")
    report.add("RBI state inflation agrees with MoSPI's consumer price indices", checked, failures, notes, allowed, limit=6)


def check_rbi_totals(ds: dict, report: Report) -> None:
    """Unemployment (tables 8-9): overall between male and female. Rural wages (112-115): All India within the
    states' range."""
    recs = ds["rbi"]
    failures, checked = [], 0
    by = {(r["table"], r["variant"], r["state"], r["year"]): r["value"] for r in recs if r["table"] in (8, 9)}
    for (n, variant, state, year), v in by.items():
        if not variant.endswith("Overall") or v is None:
            continue
        area = variant.split()[0]
        m, f = by.get((n, f"{area} Male", state, year)), by.get((n, f"{area} Female", state, year))
        if m is None or f is None:
            continue
        checked += 1
        if not (min(m, f) - 1 <= v <= max(m, f) + 1):
            failures.append(f"RBI table {n} {state} {year}: overall {v} outside male {m} and female {f} (per thousand)")
    for n in (112, 113, 114, 115):
        for year in sorted({r["year"] for r in recs if r["table"] == n}):
            vals = [r["value"] for r in recs if r["table"] == n and r["year"] == year and r["state"] != "All India" and r["value"] is not None]
            india = next((r["value"] for r in recs if r["table"] == n and r["year"] == year and r["state"] == "All India"), None)
            if india is None or not vals:
                continue
            checked += 1
            if not (min(vals) <= india <= max(vals)):
                failures.append(f"RBI table {n} {year}: All India ₹{india} outside the states' ₹{min(vals)}–₹{max(vals)}")
    report.add("RBI state tables: totals lie within their parts", checked, failures,
               ["Unemployment: the overall rate lies between men's and women's (published per thousand, so within 1). "
                "Rural wages: the All-India average lies within the range of the states' averages."])


RBI_BASE_YEAR = "2011-12"  # the base year of the handbook's constant-price state accounts (tables 20 and 22)
RBI_INCOME = {"gsdp": (21, 22), "per_capita_nsdp": (19, 20)}  # (current prices, constant prices)
RBI_PRICE_RATIO_TOL = 0.25  # catches a swapped table or a unit slip (×10, ×100), not ordinary revisions (worst today ~6.5%)


def check_rbi_income(ds: dict, report: Report) -> None:
    """State GDP (GSDP, tables 21-22) and income per person (per capita NSDP, tables 19-20), at current and constant
    prices. The tables give no NSDP level, population or growth rate, so the checks tie the four tables together:
    - in the base year, current and constant prices are the same figure (within rounding);
    - after it, current prices are not below constant prices (prices have risen every year since 2011-12);
    - GSDP ÷ per capita NSDP is population × GSDP/NSDP, so it is about the same at current and constant prices
      (within 25%); a table swapped for its pair, or read in the wrong unit, breaks this."""
    v = {(r["table"], r["state"], r["year"]): r["value"] for r in ds["rbi"]
         if r["table"] in (19, 20, 21, 22) and r["value"] is not None}
    failures, checked = [], 0
    if not any(y == RBI_BASE_YEAR for (_, _, y) in v):
        failures.append(f"RBI tables 19-22: no figures for the base year {RBI_BASE_YEAR} (a new base? update RBI_BASE_YEAR)")
    for name, (cur, const) in RBI_INCOME.items():
        for (t, state, year), c in sorted(v.items()):
            k = v.get((const, state, year))
            if t != cur or k is None:
                continue
            checked += 1
            if year == RBI_BASE_YEAR and abs(c - k) > max(2, c * 1e-4):
                failures.append(f"{name} {state} {year} (base year): current prices {c:,.0f} ≠ constant prices {k:,.0f}")
            elif year > RBI_BASE_YEAR and c < k:
                failures.append(f"{name} {state} {year}: current prices {c:,.0f} below constant prices {k:,.0f}")
    for (t, state, year), g in sorted(v.items()):
        if t != 21 or None in (pc := v.get((19, state, year)), gk := v.get((22, state, year)), pk := v.get((20, state, year))):
            continue
        checked += 1
        ratio = (g / pc) / (gk / pk)
        if abs(ratio - 1) > RBI_PRICE_RATIO_TOL:
            failures.append(f"{state} {year}: GSDP ÷ per capita NSDP is {g / pc * 1e5:,.0f} at current prices and "
                            f"{gk / pk * 1e5:,.0f} at constant prices ({ratio - 1:+.0%})")
    report.add("RBI state GDP and income per person: current and constant prices agree", checked, failures,
               [f"Base year {RBI_BASE_YEAR}: current = constant prices; later years: current ≥ constant; GSDP ÷ per "
                f"capita NSDP (population × GSDP/NSDP) within {RBI_PRICE_RATIO_TOL:.0%} at current and constant prices."])

"""RBI Handbook of Statistics on Indian States: every table read in its unit, state inflation against MoSPI's
indices, totals within their parts, and state GDP and income per person at current and constant prices."""

import re
from collections import defaultdict

from pipeline_common.report import Report
from pipeline_common.text import fy_start, prev_fy

from ..rbi import RBI_STATE_TABLES

# points: RBI's state inflation (printed to one decimal) against the rate worked out from MoSPI's monthly indices,
# which are printed to one decimal too and averaged over the year
RBI_INFLATION_TOL = 0.15


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


def fy_average(months: dict[str, float], fy: str) -> float | None:
    """The average index over a financial year ('2023-24': April 2023 to March 2024), if every month has one."""
    y = fy_start(fy)
    vals = [months.get(m) for m in [f"{y}-{m:02d}" for m in range(4, 13)] + [f"{y + 1}-{m:02d}" for m in range(1, 4)]]
    return None if None in vals else sum(vals) / 12


def check_rbi_inflation(ds: dict, report: Report) -> None:
    """The handbook's average inflation by state (table 108) equals the change in the yearly average of MoSPI's
    monthly general index (combined)."""
    failures, notes, checked = [], [], 0
    idx: dict[str, dict[str, float]] = defaultdict(dict)
    for r in ds["cpi"]:
        if r["subgroup"] == "General-Overall" and r["sector"] == "Combined" and r["index"] is not None:
            idx[state_key(r["state"])][r["month"]] = r["index"]
    skipped = defaultdict(int)
    for r in ds["rbi"]:
        if r["table"] != 108 or r["value"] is None:
            continue
        k, fy = state_key(r["state"]), r["year"]
        prev = prev_fy(fy)
        a, b = fy_average(idx[k], fy), fy_average(idx[k], prev)
        if a is None or b is None:
            skipped[fy] += 1
            continue
        checked += 1
        calc = (a / b - 1) * 100
        if abs(calc - r["value"]) > RBI_INFLATION_TOL:
            failures.append(f"{r['state']} {fy}: RBI {r['value']}%, MoSPI's indices give {calc:.2f}%")
    if skipped:
        notes.append("Not compared (a year without all 12 monthly indices in MoSPI's data, such as the April-May 2020 "
                     f"lockdown; RBI's notes say it used fewer months for those years): {dict(sorted(skipped.items()))}.")
    report.add("RBI state inflation agrees with MoSPI's consumer price indices", checked, failures, notes)


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

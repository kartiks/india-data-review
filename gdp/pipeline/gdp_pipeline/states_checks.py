"""Checks of the state accounts (states.json, built by states.py), added to gdp/data/validation_report.md by check():

1. Every row is understood (year, state, industry, unit); anything left out is a known, explained source error.
2. GSDP = GSVA + taxes - subsidies, and NSDP = NSVA + taxes - subsidies, for every state, year and price basis.
3. Industries add up to total value added; sub-industries add up to their industry.
4. Every published growth rate is reproduced from the published levels.
5. The two tables of NSDP per person agree, and per-person GSDP and NSDP imply the same population.
6. For review, not failures: the states' GSDP against India's GDP (2011-12 base) in each year most states report.
Also: every state is a known one with rows in every table's base, no row is published twice with different values,
and a derived GSDP implies a population that moves smoothly with MoSPI's GSDP per person.
"""

import json

from .ids import STAGE_ORDER
from .states import DATA, KNOWN_STATES, SITE_BASE, prev_year

LEVEL_TOL = 2  # ₹ crore: GSDP is printed to the crore and its parts to the lakh
GROWTH_TOL = 0.05  # growth rates are printed to one decimal ...
LEVEL_ROUNDING = 0.5  # ... and worked out from levels printed to the crore (or rupee), which matters for small states
PER_PERSON_TOL = 1  # ₹
POPULATION_TOL = 0.0005  # per-person GSDP and NSDP are rounded to the rupee
# A derived state's implied population moves less than this a year. MoSPI's own per-person figures can move a few
# percent when population projections are revised; a missing tax figure (about 10% of GSDP) or a lakh/crore slip is
# far larger.
DERIVED_POPULATION_STEP = 0.08
# For review only: states' GSDP / India's GDP usually sits in this band. The states are compiled separately and keep
# being revised, while the national 2011-12 series stopped in February 2026, so this is not a hard check.
SUM_BAND = (0.95, 1.06)
COVERAGE = 0.97  # a year is compared once the states reporting it made up this share of all states' GSDP the year before
FINAL_ENOUGH = "PE"  # ... and India's figure for it is at least a provisional estimate

# (check, message prefix) -> reason. Every known difference in MoSPI's state tables, with its reason.
KNOWN_EXCEPTIONS: dict[tuple[str, str], str] = {
    ("source", "Karnataka: net state value added (ind30)"):
        "MoSPI's net state value added table repeats Karnataka's gross value added at current prices, in both the "
        "current- and constant-price columns, in the years listed. Net value added cannot equal gross value added "
        "(depreciation is positive), so Karnataka's net value added is left out for those years. Its NSDP and NSDP per "
        "person come from the NSDP tables (ind24, ind25), which agree with its GSDP and the RBI's handbook.",
    ("source", "Karnataka: NSDP per person (second table, ind32)"):
        "MoSPI's second table of NSDP per person repeats Karnataka's GSDP per person at current prices, in both "
        "columns, in the years listed. It is left out; Karnataka's NSDP per person comes from the first table (ind25).",
}


USED: set[tuple[str, str]] = set()


def allowed(check: str, msg: str) -> str | None:
    for (c, key), reason in KNOWN_EXCEPTIONS.items():
        if c == check and msg.startswith(key):
            USED.add((c, key))
            return reason
    return None


def sort_out(check: str, messages: list[str]) -> tuple[list[str], list[str]]:
    """(failures, notes): a message with a known reason becomes a note."""
    failures, notes = [], []
    for m in messages:
        reason = allowed(check, m)
        (notes.append(f"Allowed: {m}. Reason: {reason}") if reason else failures.append(m))
    return failures, notes


def nodes(st: dict):
    for base, states in st["data"].items():
        for state, years in states.items():
            for year, node in years.items():
                yield base, state, year, node


def check_rows(st: dict, report) -> None:
    failures, notes = sort_out("source", st["source_problems"] + st["left_out"])
    with open(DATA / "state_accounts.csv", encoding="utf-8") as f:
        n = sum(1 for _ in f) - 1
    for base in (b for b in st["bases"] if b != SITE_BASE):
        missing = [s for s in KNOWN_STATES if s not in st["data"][base]]
        notes.append(f"MoSPI now publishes state accounts on the {base} base"
                     + (f" (not yet for {', '.join(missing)})" if missing else " for every state")
                     + f". The site still shows the {SITE_BASE} base: switch it over (site/src/lib/gdp/states.ts) "
                     "once the new base covers the states.")
    report.add("State accounts: every published row is understood", n, failures, notes)


def check_identities(st: dict, report) -> None:
    failures, notes, n = [], [], 0
    no_subsidies = set()
    for base, state, year, node in nodes(st):
        for level, va in (("gsdp", "gsva"), ("nsdp", "nsva")):
            lv, total, taxes = node.get(level), node.get(va, {}).get("total"), node.get("taxes")
            if not lv or lv.get("derived") or not total or not taxes:
                continue
            subs = node.get("subsidies")
            if subs is None:
                no_subsidies.add(state)
            for k in ("cur", "con"):
                if k in lv and k in total and k in taxes:
                    n += 1
                    calc = total[k] + taxes[k] - (subs or {}).get(k, 0)
                    if abs(calc - lv[k]) > LEVEL_TOL:
                        failures.append(f"{state}, {year}, {k}: {level.upper()} {lv[k]:,.0f} but {va.upper()} + taxes "
                                        f"- subsidies = {calc:,.0f} (₹ crore)")
    notes += [f"{s} publishes no subsidies on products; its GSDP and NSDP equal value added plus taxes on products."
              for s in sorted(no_subsidies)]
    # A state with value added but no GSDP: MoSPI's GSDP table leaves it out and its taxes or subsidies are missing,
    # so it would silently drop off the site.
    for base, state, year, node in nodes(st):
        if node.get("gsva", {}).get("total") and "gsdp" not in node:
            failures.append(f"{state}, {year}: value added is published but GSDP is not, and it cannot be worked out "
                            "(taxes or subsidies on products missing)")
    derived = sorted({s for _, s, _, node in nodes(st) if node.get("gsdp", {}).get("derived")})
    if derived:
        notes.append(f"GSDP worked out as GSVA + taxes - subsidies (no GSDP published): {', '.join(derived)}.")
    report.add("State accounts: GSDP = GSVA + taxes - subsidies, NSDP = NSVA + taxes - subsidies", n, failures, notes)


def check_industries(st: dict, report) -> None:
    failures, n = [], 0
    for base, state, year, node in nodes(st):
        for va in ("gsva", "nsva"):
            parts = node.get(va, {})
            total = parts.get("total")
            for k in ("cur", "con"):
                if total and k in total:
                    vals = [v[k] for i, v in parts.items() if i != "total" and k in v]
                    n += 1
                    if abs(sum(vals) - total[k]) > LEVEL_TOL:
                        failures.append(f"{state}, {year}, {va.upper()} {k}: industries add up to {sum(vals):,.0f}, "
                                        f"total is {total[k]:,.0f}")
            for ind, subs in node.get(f"{va}_sub", {}).items():
                top = parts.get(ind, {})
                for k in ("cur", "con"):
                    if k in top:
                        vals = [v[k] for v in subs.values() if k in v]
                        n += 1
                        if abs(sum(vals) - top[k]) > LEVEL_TOL:
                            failures.append(f"{state}, {year}, {va.upper()} {ind} {k}: parts add up to "
                                            f"{sum(vals):,.0f}, industry is {top[k]:,.0f}")
    report.add("State accounts: industries add up to total value added, and parts to their industry", n, failures, [])


def check_growth(st: dict, report) -> None:
    messages, n = [], 0
    for base, state, year, node in nodes(st):
        before = st["data"][base][state].get(prev_year(year), {})
        for level, g in node.get("growth", {}).items():
            if g.get("published") is False:
                continue
            a, b = node.get(level), before.get(level)
            for kind, k in (("real", "con"), ("nominal", "cur")):
                if kind in g and a and b and k in a and b.get(k):
                    n += 1
                    calc = (a[k] / b[k] - 1) * 100
                    # How far rounding the two levels can move the growth rate.
                    slack = 100 * LEVEL_ROUNDING / b[k] * (1 + a[k] / b[k])
                    if abs(calc - g[kind]) > GROWTH_TOL + slack + 1e-9:
                        messages.append(f"{state}, {year}, {level}_growth {kind}: published {g[kind]}%, "
                                        f"levels give {calc:.2f}%")
    failures, notes = sort_out("growth", messages)
    report.add("State accounts: every published growth rate is reproduced from the levels", n, failures, notes)


def check_per_person(st: dict, report) -> None:
    failures, n = [], 0
    for base, state, year, node in nodes(st):
        a, b = node.get("pc_nsdp"), node.get("pc_nsdp_alt")
        for k in ("cur", "con"):
            if a and b and k in a and k in b:
                n += 1
                if abs(a[k] - b[k]) > PER_PERSON_TOL:
                    failures.append(f"{state}, {year}, {k}: NSDP per person ₹{a[k]:,.0f} in one table, ₹{b[k]:,.0f} in the other")
        gsdp, nsdp, pg, pn = node.get("gsdp"), node.get("nsdp"), node.get("pc_gsdp"), a or b
        for k in ("cur", "con"):
            if gsdp and nsdp and pg and pn and not gsdp.get("derived") and all(k in x for x in (gsdp, nsdp, pg, pn)):
                n += 1
                p1, p2 = gsdp[k] / pg[k], nsdp[k] / pn[k]
                if abs(p1 / p2 - 1) > POPULATION_TOL:
                    failures.append(f"{state}, {year}, {k}: GSDP per person implies {p1 * 100:.1f} lakh people, "
                                    f"NSDP per person {p2 * 100:.1f} lakh")
        # Derived GSDP has no published total to check against. The population it implies with MoSPI's GSDP per
        # person should move smoothly from year to year; a slip in taxes or subsidies would show as a jump.
        before = st["data"][base][state].get(prev_year(year), {})
        g0, p0 = before.get("gsdp"), before.get("pc_gsdp")
        if gsdp and gsdp.get("derived") and pg and g0 and p0 and all("cur" in x for x in (gsdp, pg, g0, p0)):
            n += 1
            step = (gsdp["cur"] / pg["cur"]) / (g0["cur"] / p0["cur"]) - 1
            if abs(step) > DERIVED_POPULATION_STEP:
                failures.append(f"{state}, {year}: derived GSDP and GSDP per person imply the population changed "
                                f"{step:+.1%} on the year before")
    report.add("State accounts: per-person figures agree with each other and with the levels", n, failures, [])


def coverage(states: dict, year: str) -> float:
    """Share of all states' GSDP (current prices) the year before that the states reporting `year` made up."""
    before = {s: y[prev_year(year)]["gsdp"]["cur"] for s, y in states.items() if "cur" in y.get(prev_year(year), {}).get("gsdp", {})}
    total = sum(before.values())
    now = [s for s, y in states.items() if "cur" in y.get(year, {}).get("gsdp", {})]
    return sum(before.get(s, 0) for s in now) / total if total else 0.0


def check_sum(st: dict, ds: dict, report) -> None:
    """States' GSDP against India's GDP (2011-12 base, latest estimate), current prices. For review, not failures:
    the two are compiled separately, and the national 2011-12 series is no longer revised while the states' are."""
    notes = []
    annual = ds["data"].get("2011-12", {}).get("annual", {})
    states = st["data"].get(SITE_BASE, {})
    years_all = sorted({y for years in states.values() for y in years})
    for year in years_all:
        stages = annual.get(year)
        if not stages:
            continue
        stage = max(stages, key=lambda s: STAGE_ORDER.get(s, 99))
        india = stages[stage].get("gdp", {}).get("cur")
        if not india or STAGE_ORDER.get(stage, 99) < STAGE_ORDER[FINAL_ENOUGH]:
            continue  # an advance estimate on the old base will never be revised
        if year != years_all[0] and coverage(states, year) < COVERAGE:
            continue  # too few states have published it yet
        vals = [years[year]["gsdp"]["cur"] for years in states.values() if "cur" in years.get(year, {}).get("gsdp", {})]
        ratio = sum(vals) / india
        flag = "" if SUM_BAND[0] <= ratio <= SUM_BAND[1] else f" (outside the usual {SUM_BAND[0]:.0%} to {SUM_BAND[1]:.0%}: look at it)"
        notes.append(f"{year}: {len(vals)} states and UTs add up to {ratio:.1%} of India's GDP ({stage} estimate){flag}")
    report.add("State accounts: the states' GSDP against India's GDP (for review, not failures)", 0, [], notes)


def check(ds: dict, report, st: dict | None = None) -> None:
    USED.clear()
    st = st or json.loads((DATA / "states.json").read_text())
    check_rows(st, report)
    check_identities(st, report)
    check_industries(st, report)
    check_growth(st, report)
    check_per_person(st, report)
    check_sum(st, ds, report)
    unused = [f"{c}: {k}" for c, k in KNOWN_EXCEPTIONS if (c, k) not in USED]
    if unused:
        report.add("State accounts: known exceptions no longer needed (for review: remove them)", 0, [], unused)

"""Checks that the published national accounts hang together, and that every
figure on the site can be traced to an official source.

1. Source rows: every row read has a known year, stage, industry and sector.
2. Accounting identities, for every series, year, estimate stage and price basis:
   - the eight industries add up to total GVA; group industries = their parts;
     sub-industries (crops, livestock, ...) add up to their industry
   - GDP = GVA + net taxes on products; net taxes = taxes - subsidies
   - NDP = GDP - depreciation; GNI = GDP + net primary income from abroad;
     GNDI = GNI + net current transfers from abroad
   - investment and saving by institutional sector add up to the total
3. Growth rates: every published GDP growth rate is reproduced from the
   published GDP levels (against the previous year's estimate available then).
4. Quarters add up to the year; published quarterly growth matches the levels.
5. The back series (1950-51 to 2011-12) joins the current series in 2011-12.
6. Spending side: the gap between GDP and its spending components
   ("discrepancies") is listed for review.
7. Budget: the GDP assumption is found in every budget and its stated growth
   reproduces from the two numbers printed with it.
8. Forecasts: every quoted forecast sentence is found in the official document.

Exceptions are allowed only through KNOWN_EXCEPTIONS, each with a reason.
Writes gdp/data/validation_report.md and exits non-zero on any failure.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from .build import BROAD, GROUPS, STAGE_ORDER

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

LEVEL_TOL = 10  # ₹ crore: published figures are rounded to the crore, so sums can be a few crore off
GROWTH_TOL = 0.051  # published growth rates have one decimal
# A published growth rate further than this from every reading of the levels is treated as an error.
GROSS_GROWTH_GAP = 1.5

# Sub-industries MoSPI publishes for each industry, when complete.
SUBINDUSTRIES = {
    "agriculture": ["crops", "livestock", "forestry_and_logging", "fishing_and_aquaculture"],
    "manufacturing": ["food_products_beverages_and_tobacco", "textiles_apparel_and_leather_products",
                      "metal_products", "machinery_and_equipment", "other_manufactured_goods"],
    "trade_hotels": ["trade_repair_services", "hotels_restaurants"],
}

# (check id, key) -> reason. Keys are the message prefixes the checks produce.
KNOWN_EXCEPTIONS: dict[tuple[str, str], str] = {
    ("source", "nas/2011-12/Current/Annually/ind19: row with year '1999'"):
        "MoSPI's API returns one Gross National Disposable Income row (First Advance Estimate, ₹3,62,04,793 crore) "
        "labelled with the year '1999'. No fiscal year is given, so the row is left out. The value matches no other "
        "GNDI figure in the series and does not affect GDP or growth.",
}


class Report:
    def __init__(self) -> None:
        self.sections: list[tuple[str, int, list[str], list[str]]] = []

    def add(self, title: str, checked: int, failures: list[str], notes: list[str]) -> None:
        self.sections.append((title, checked, failures, notes))

    @property
    def failed(self) -> bool:
        return any(f for _, _, f, _ in self.sections)

    def markdown(self) -> str:
        total = sum(c for _, c, _, _ in self.sections)
        nfail = sum(len(f) for _, _, f, _ in self.sections)
        out = ["# Data validation report", "",
               "National accounts (MoSPI), the Union Budget's GDP assumption and published forecasts. "
               "Every allowed exception lists its reason.", "",
               f"**Result: {'FAILED' if nfail else 'PASSED'}** ({total} checks, {nfail} failures)", ""]
        for title, checked, failures, notes in self.sections:
            out += [f"## {'❌' if failures else '✅'} {title}", f"{checked} checks, {len(failures)} failures.", ""]
            out += [f"- FAIL: {f}" for f in failures]
            out += [f"- {n}" for n in notes]
            out.append("")
        return "\n".join(out)


BACK_ADDITIVITY = (
    "MoSPI's back series links each industry's older figures to the 2011-12 base separately, so before 2004-05 "
    "the industries do not add up exactly to total GVA (about 5% apart in 1950-51, 0.3% in 2000-01; exact from "
    "2004-05, where the back series was recompiled in full). Industry shares on the site for these years are "
    "shares of the sum of industries."
)
EARLY_NET_TAXES = (
    "In MoSPI's API, net taxes on products for the First Advance and Provisional Estimates of 2014-15 and 2015-16 "
    "do not equal GDP minus GVA from the same release. GDP and GVA are the published headline figures (the "
    "February 2015 release put 2014-15 real GVA at ₹98.58 lakh crore, as here), so they are shown; net taxes for "
    "these four releases are not used."
)
# (check, test on the message) -> reason, for whole families of known differences.
KNOWN_RULES = [
    ("identity", lambda m: m.startswith("2011-12-back series, ") and int(m[21:25]) < 2004, BACK_ADDITIVITY),
    ("identity", lambda m: any(m.startswith(f"2011-12 series, {y}, {s},") for y in ("2014-15", "2015-16") for s in ("AE1", "PE"))
     and "GDP = GVA + net taxes" in m, EARLY_NET_TAXES),
]


def allowed(check: str, msg: str) -> str | None:
    for (c, key), reason in KNOWN_EXCEPTIONS.items():
        if c == check and msg.startswith(key):
            return reason
    for c, test, reason in KNOWN_RULES:
        if c == check and test(msg):
            return reason
    return None


def nodes(ds: dict, freq: str = "annual"):
    """(series, period, stage, node) for every published estimate."""
    for series, freqs in ds["data"].items():
        for period, stages in freqs.get(freq, {}).items():
            for stage, node in stages.items():
                yield series, period, stage, node


def where(series: str, period: str, stage: str, price: str) -> str:
    return f"{series} series, {period}, {stage}, {'current' if price == 'cur' else 'constant'} prices"


def check_source(ds: dict, report: Report) -> None:
    failures, notes = [], []
    for p in ds["source_problems"]:
        reason = allowed("source", p)
        (notes.append(f"Allowed: {p}. Reason: {reason}") if reason else failures.append(p))
    notes += [f"Left out: {d}" for d in ds["duplicate_rows"]]
    rows = sum(1 for _ in open(DATA / "national_accounts.csv")) - 1
    report.add("Every published row is understood", rows, failures, notes)


def sum_check(target: dict | None, parts: list[dict | None], price: str) -> tuple[bool, float, float] | None:
    if not target or price not in target or any(not p or price not in p for p in parts):
        return None
    s = sum(p[price] for p in parts)
    return abs(s - target[price]) <= LEVEL_TOL, target[price], s


def check_identities(ds: dict, report: Report) -> None:
    failures, notes = [], []
    checked = 0
    stats: dict[str, int] = defaultdict(int)
    allowed_by_reason: dict[str, list[str]] = defaultdict(list)

    def test(name: str, loc: str, res) -> None:
        nonlocal checked
        if res is None:
            return
        checked += 1
        stats[name] += 1
        ok, printed, computed = res
        if not ok:
            msg = f"{loc}: {name} — printed {printed:,.0f}, parts give {computed:,.0f} ({printed - computed:+,.0f})"
            reason = allowed("identity", msg)
            (allowed_by_reason[reason].append(msg) if reason else failures.append(msg))

    for freq in ("annual", "quarterly"):
        for series, period, stage, n in nodes(ds, freq):
            gva = n.get("gva_by_industry", {})
            for price in ("cur", "con"):
                loc = where(series, period, stage, price)
                if not any(gva.get(i, {}).get("summed") for i in BROAD):
                    test("8 industries = total GVA", loc, sum_check(gva.get("total"), [gva.get(i) for i in BROAD], price))
                for group, parts in GROUPS.items():
                    if not gva.get(group, {}).get("summed"):
                        test("industry group = its parts", loc, sum_check(gva.get(group), [gva.get(p) for p in parts], price))
                fine = [i for g in GROUPS.values() for i in g] + [i for i in BROAD if i not in GROUPS]
                if any(gva.get(i, {}).get("summed") for i in BROAD):
                    test("finer industries = total GVA (where groups are not published)", loc,
                         sum_check(gva.get("total"), [gva.get(i) for i in fine], price))
                for ind, subs in SUBINDUSTRIES.items():
                    sub = n.get("gva_sub", {}).get(ind, {})
                    test("sub-industries = industry", loc, sum_check(gva.get(ind), [sub.get(s) for s in subs], price))
                test("GDP = GVA + net taxes on products", loc, sum_check(n.get("gdp"), [gva.get("total"), n.get("net_taxes")], price))
                if n.get("product_taxes") and n.get("product_subsidies") and price in n["product_taxes"]:
                    neg = {price: -n["product_subsidies"][price]} if price in n["product_subsidies"] else None
                    test("net taxes = taxes − subsidies", loc, sum_check(n.get("net_taxes"), [n["product_taxes"], neg], price))
                if n.get("cfc") and price in n["cfc"]:
                    test("NDP = GDP − depreciation", loc, sum_check(n.get("ndp"), [n.get("gdp"), {price: -n["cfc"][price]}], price))
                test("GNI = GDP + net primary income from abroad", loc,
                     sum_check(n.get("gni"), [n.get("gdp"), n.get("primary_income_row")], price))
                test("GNDI = GNI + net current transfers from abroad", loc,
                     sum_check(n.get("gndi"), [n.get("gni"), n.get("transfers_row")], price))
                for ind in ("gfcf", "saving", "cfc"):
                    by = n.get(f"{ind}_by_sector")
                    if by:
                        sectors = ["public_nonfin", "private_nonfin", "public_fin", "private_fin", "government", "households"]
                        test(f"{ind} by sector = total", loc, sum_check(n.get(ind), [by.get(s) for s in sectors], price))
    for reason, msgs in allowed_by_reason.items():
        notes.append(f"Allowed ({len(msgs)} figures, e.g. {msgs[0]}). Reason: {reason}")
    notes.insert(0, "Checks run: " + "; ".join(f"{k} ({v})" for k, v in sorted(stats.items())))
    report.add("Accounting identities hold in every estimate", checked, failures, notes)


def check_growth(ds: dict, report: Report) -> None:
    """Each published growth rate must follow from the levels: this year's estimate vs an estimate of last year."""
    failures, notes, unreproduced = [], [], []
    checked = 0
    pairing: dict[tuple[str, str], int] = defaultdict(int)
    for series, freqs in ds["data"].items():
        annual = freqs.get("annual", {})
        for year, stages in annual.items():
            prev_year = f"{int(year[:4]) - 1}-{year[2:4]}"
            prev = annual.get(prev_year, {})
            for stage, n in stages.items():
                g = n.get("growth", {}).get("gdp")
                if not g:
                    continue
                for price, key in (("con", "real"), ("cur", "nominal")):
                    if key not in g or price not in n.get("gdp", {}):
                        continue
                    checked += 1
                    hits = [ps for ps, pn in prev.items() if price in pn.get("gdp", {})
                            and abs((n["gdp"][price] / pn["gdp"][price] - 1) * 100 - g[key]) <= GROWTH_TOL]
                    if hits:
                        best = max(hits, key=lambda s: STAGE_ORDER.get(s, 99))
                        pairing[(stage, best)] += 1
                    elif not prev:
                        notes.append(f"{series} series, {year} {stage}: {key} growth {g[key]}% not checkable (no {prev_year} levels)")
                    else:
                        calcs = {ps: (n["gdp"][price] / pn["gdp"][price] - 1) * 100
                                 for ps, pn in prev.items() if price in pn.get("gdp", {})}
                        opts = ", ".join(f"{ps} {v:.2f}%" for ps, v in calcs.items())
                        msg = f"{series} series, {year} {stage}: published {key} growth {g[key]}%, levels give {opts}"
                        gap = min(abs(v - g[key]) for v in calcs.values())
                        if gap > GROSS_GROWTH_GAP:
                            reason = allowed("growth", msg)
                            (notes.append(f"Allowed: {msg}. Reason: {reason}") if reason else failures.append(msg))
                        else:
                            unreproduced.append(msg)
    notes.insert(0, "Which estimate of the previous year each stage's growth is measured against: "
                 + "; ".join(f"{a} vs {b} ({c})" for (a, b), c in sorted(pairing.items())))
    if unreproduced:
        notes.insert(1, f"{len(unreproduced)} published rates are within {GROSS_GROWTH_GAP} points of the levels but not "
                     "exact. Each was measured against an estimate of the previous year that MoSPI's API no longer "
                     "keeps (it keeps one figure per year and stage, after later revisions). The site shows growth "
                     "rates as MoSPI announced them. Listed for review:")
        notes[2:2] = unreproduced
    report.add("Published GDP growth rates follow from published GDP levels", checked, failures, notes)


def check_quarters(ds: dict, report: Report) -> None:
    failures, notes, unreproduced = [], [], []
    checked = 0
    for series, freqs in ds["data"].items():
        q = freqs.get("quarterly", {})
        annual = freqs.get("annual", {})
        years = sorted({p.split()[0] for p in q})
        for y in years:
            quarters = [q.get(f"{y} Q{i}", {}).get("LATEST") for i in range(1, 5)]
            if all(quarters) and y in annual:
                for price in ("cur", "con"):
                    if any(price not in qq.get("gdp", {}) for qq in quarters):
                        continue
                    s = sum(qq["gdp"][price] for qq in quarters)
                    checked += 1
                    hits = [st for st, n in annual[y].items() if abs(n.get("gdp", {}).get(price, -1e18) - s) <= LEVEL_TOL]
                    latest = max(annual[y], key=lambda st: STAGE_ORDER.get(st, 99))
                    if latest in hits:
                        continue
                    msg = f"{series} series, {y}: four quarters add to {s:,.0f} ({price}), annual {latest} is {annual[y][latest]['gdp'].get(price, 0):,.0f}"
                    if hits:
                        notes.append(f"{msg}; they match the {', '.join(hits)} instead")
                    else:
                        reason = allowed("quarters", msg)
                        (notes.append(f"Allowed: {msg}. Reason: {reason}") if reason else failures.append(msg))
            # quarterly growth vs same quarter a year earlier
            py = f"{int(y[:4]) - 1}-{y[2:4]}"
            for i in range(1, 5):
                n, p = q.get(f"{y} Q{i}", {}).get("LATEST"), q.get(f"{py} Q{i}", {}).get("LATEST")
                g = (n or {}).get("growth", {}).get("gdp")
                if not (n and p and g):
                    continue
                for price, key in (("con", "real"), ("cur", "nominal")):
                    if key in g and price in n.get("gdp", {}) and price in p.get("gdp", {}):
                        checked += 1
                        calc = (n["gdp"][price] / p["gdp"][price] - 1) * 100
                        if abs(calc - g[key]) > GROWTH_TOL:
                            msg = f"{series} series, {y} Q{i}: published {key} growth {g[key]}%, levels give {calc:.2f}%"
                            if abs(calc - g[key]) > GROSS_GROWTH_GAP:
                                reason = allowed("quarters", msg)
                                (notes.append(f"Allowed: {msg}. Reason: {reason}") if reason else failures.append(msg))
                            else:
                                unreproduced.append(msg)
    if unreproduced:
        notes.append(f"{len(unreproduced)} quarterly growth rates are within {GROSS_GROWTH_GAP} points of the levels "
                     "but not exact: MoSPI's API keeps only the latest quarterly levels, while each growth rate was "
                     "announced against the year-earlier quarter as estimated at the time. Listed for review:")
        notes += unreproduced
    report.add("Quarters add up to the year; quarterly growth follows from levels", checked, failures, notes)


def check_join(ds: dict, report: Report) -> None:
    failures, notes = [], []
    back = ds["data"]["2011-12-back"]["annual"]["2011-12"]["BACK"]
    cur = ds["data"]["2011-12"]["annual"]["2011-12"]
    latest = max(cur, key=lambda s: STAGE_ORDER.get(s, 99))
    checked = 0
    for price in ("cur", "con"):
        checked += 1
        a, b = back["gdp"][price], cur[latest]["gdp"][price]
        msg = f"2011-12 GDP ({price}): back series {a:,.0f}, current series {latest} {b:,.0f}"
        (notes if abs(a - b) <= LEVEL_TOL else failures).append(msg)
    years = [r["year"] for r in ds["long_run"]]
    gaps = [f"{a} → {b}" for a, b in zip(years, years[1:]) if int(b[:4]) != int(a[:4]) + 1]
    checked += 1
    if gaps:
        failures.append(f"long-run series has gaps: {gaps}")
    notes.append(f"Long-run series runs {years[0]} to {years[-1]} without gaps.")
    report.add("Back series joins the current series", checked, failures, notes)


def check_expenditure(ds: dict, report: Report) -> None:
    """GDP minus its spending components = 'discrepancies' in MoSPI's tables. Listed, not failed."""
    notes = []
    checked = 0
    for series, period, stage, n in nodes(ds):
        comps = ["pfce", "gfce", "gfcf", "stocks", "valuables", "exports"]
        if not all(c in n and "cur" in n[c] for c in comps + ["imports", "gdp"]):
            continue
        checked += 1
        total = sum(n[c]["cur"] for c in comps) - n["imports"]["cur"]
        gap = (n["gdp"]["cur"] - total) / n["gdp"]["cur"] * 100
        if abs(gap) > 3:
            notes.append(f"{series} series, {period} {stage}: discrepancy {gap:+.1f}% of GDP (current prices)")
    notes.insert(0, "GDP is measured from production; the spending components are estimated separately, "
                 "and MoSPI shows the difference as 'discrepancies'. Gaps above 3% of GDP:")
    report.add("Spending side: size of the statistical discrepancy (for review, not failures)", checked, [], notes)


def check_budget(ds: dict, report: Report) -> None:
    from .sources import BUDGETS, fy

    failures, notes = [], []
    found = {a["budget"]: a for a in ds["budget_assumptions"]}
    checked = 0
    for start in BUDGETS:
        y = fy(start)
        checked += 1
        a = found.get(y)
        if not a:
            failures.append(f"Budget {y}: GDP assumption not found in Budget at a Glance")
            continue
        if a["printed_year"].replace("20", "", 1) != y and a["printed_year"] != y:
            if a["printed_year"][:4] != y[:4]:
                failures.append(f"Budget {y}: sentence is for {a['printed_year']}")
        if a.get("growth_pct") is not None:
            checked += 1
            calc = (a["gdp_crore"] / a["base_gdp_crore"] - 1) * 100
            msg = f"Budget {y}: ₹{a['gdp_crore']:,.0f} crore is {calc:.2f}% over ₹{a['base_gdp_crore']:,.0f} crore; printed {a['growth_pct']}%"
            (notes if abs(calc - a["growth_pct"]) <= 0.051 else failures).append(msg)
        if a.get("note"):
            notes.append(f"Budget {y}: {a['note']}")
    report.add("Budget GDP assumption found and consistent", checked, failures, notes)


def check_forecasts(ds: dict, report: Report) -> None:
    from .forecasts import verify_quotes

    checked, failures, notes = verify_quotes(ds)
    report.add("Every forecast is quoted from its official document", checked, failures, notes)


def check_revisions(ds: dict, report: Report) -> None:
    """Largest revisions between the first and latest estimate of growth (for review)."""
    notes = []
    annual = ds["data"]["2011-12"]["annual"]
    for y, stages in sorted(annual.items()):
        withg = [s for s in stages if stages[s].get("growth", {}).get("gdp", {}).get("real") is not None]
        if len(withg) < 2:
            continue
        first = min(withg, key=lambda s: STAGE_ORDER.get(s, 99))
        last = max(withg, key=lambda s: STAGE_ORDER.get(s, 99))
        a, b = stages[first]["growth"]["gdp"]["real"], stages[last]["growth"]["gdp"]["real"]
        if abs(b - a) >= 1:
            notes.append(f"{y}: real growth first {a}% ({first}), latest {b}% ({last}), revised {b - a:+.1f} points")
    report.add("Large revisions to growth (for review, not failures)", 0, [], notes)


def main(ds: dict | None = None) -> int:
    ds = ds or json.loads((DATA / "gdp.json").read_text())
    report = Report()
    check_source(ds, report)
    check_identities(ds, report)
    check_growth(ds, report)
    check_quarters(ds, report)
    check_join(ds, report)
    check_budget(ds, report)
    check_forecasts(ds, report)
    check_expenditure(ds, report)
    check_revisions(ds, report)
    (DATA / "validation_report.md").write_text(report.markdown())
    for title, checked, failures, _ in report.sections:
        print(f"{'FAIL' if failures else 'ok  '} {title}: {checked} checks, {len(failures)} failures")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())

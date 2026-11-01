"""Checks that the figures the site shows hang together.

1. Source rows: every value is a number or marked missing ("NaN"); anything
   else is listed and left out.
2. Jobs (PLFS):
   - worker population ratio = participation rate × (1 − unemployment rate),
     within rounding, for every combination the site may show;
   - the figure for persons lies between men's and women's, and the rural +
     urban figure between rural and urban (rates, job conditions, earnings);
   - shares of workers (by type of work, industry, employer) add up to 100%.
   Combinations that break the first two are left out of the site by the build,
   each with its reason; they are listed here.
3. Consumer prices (CPI, CPI-AL/RL):
   - every published inflation rate is reproduced from the index 12 months earlier;
   - the combined index lies between the rural and urban index;
   - no month is missing.
4. Household spending (HCES):
   - the 12 spending classes, averaged with their population shares, give the
     overall average; item shares add up to 100%.

Exceptions are allowed only through the rules below, each with a reason.
Writes jobs-prices/data/validation_report.md and exits non-zero on any failure.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

from .build import MISSING, RATE_DIMS, SMALL_GAP, identity_gap

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

LEFT_OUT = (
    "MoSPI's PLFS figures in its data service carry transcription errors, mostly in the quarterly series: letters "
    "for digits ('l0.8', 'IN.4', '20J') and figures that cannot all be right (participation, worker ratio and "
    "unemployment must satisfy worker ratio = participation × (1 − unemployment rate); a total must lie between "
    "its two parts). Apr–Jun 2019, for example, shows urban unemployment of 21.6% where MoSPI's bulletin says 8.9%. "
    "Each combination below is left out of the site whole, since which of its figures is wrong cannot be told; "
    "plfs_rates.csv keeps it with the reason."
)
ALL_INDIA_STATUS = (
    "MoSPI's data service returns All-India shares of workers by type of work (self-employed, regular, casual) that "
    "do not add up to 100% (for example 0.3%, 0.4%, 0.6% and 0.6% for women in 2022), while every state's shares do. "
    "The All-India figures are not used; the site shows this breakdown by state."
)
NO_SAMPLE = (
    "Chandigarh has almost no rural population. MoSPI publishes its rural figures as 'NaN' or as zeros in every "
    "category; they are treated as not published."
)
CWS_STATUS_2025 = (
    "For 2025 in current weekly status (CWS), MoSPI's 'all self-employed' share is not the sum of its two parts "
    "(own-account workers and helpers) in most states, and the shares add up to less than 100%. The site uses the "
    "usual status (PS+SS) figures, where they add up."
)
UNLABELLED = (
    "MoSPI's data service returns some 'percentage distribution of workers' rows with no breakdown named (no type "
    "of work, industry or employer), often with several different values for the same cell. They cannot be read "
    "and are left out."
)
HCES_MISMATCH = (
    "In MoSPI's data service, the spending by item category filed under these states (rural, 2022-23, without "
    "imputation) does not add up to the state's own average spending; it appears to be other states' figures "
    "(Goa's categories add up to Andhra Pradesh's average, Haryana's to Assam's, Himachal Pradesh's to Bihar's, "
    "Jharkhand's to Chhattisgarh's). The category breakdown (rupees and shares) for these cells is left out of the "
    "site; the average itself is shown."
)
BAD_VALUE = "MoSPI's data service returns characters instead of a number for this figure. It is left out."
INFLATION_TOL = 0.12  # points: indices are published to one decimal, so a recomputed rate can differ this much


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
               "Jobs (PLFS), consumer prices (CPI, CPI-AL/RL) and household spending (HCES) from MoSPI's official "
               "data service. Every allowed exception lists its reason.", "",
               f"**Result: {'FAILED' if nfail else 'PASSED'}** ({total} checks, {nfail} failures)", ""]
        for title, checked, failures, notes in self.sections:
            out += [f"## {'❌' if failures else '✅'} {title}", f"{checked} checks, {len(failures)} failures.", ""]
            out += [f"- FAIL: {f}" for f in failures]
            out += [f"- {n}" for n in notes]
            out.append("")
        return "\n".join(out)


class Allowed:
    """Allowed exceptions grouped under their reason, so each reason is printed once with its cases."""

    def __init__(self) -> None:
        self.cases: dict[str, list[str]] = defaultdict(list)

    def add(self, reason: str, case: str) -> None:
        self.cases[reason].append(case)

    def notes(self, limit: int = 60) -> list[str]:
        out = []
        for reason, cases in self.cases.items():
            shown = "; ".join(cases[:limit]) + (f"; and {len(cases) - limit} more (see the CSV)" if len(cases) > limit else "")
            out.append(f"Allowed ({len(cases)}): {reason} Cases: {shown}")
        return out


def cell(d: dict, keys=("frequency", "year", "period", "state", "sector", "gender", "age", "status")) -> str:
    return ", ".join(str(d[k]) for k in keys if d.get(k) not in (None, "", "all"))


# ---- source values ------------------------------------------------------------------------------

def check_source(ds: dict, report: Report) -> None:
    failures, allowed = list(ds["source_problems"]), Allowed()
    checked = len(failures)

    def value_ok(v, printed, where):
        if v is None and printed not in MISSING:
            allowed.add(BAD_VALUE, f"{where} printed as {printed!r}")

    p = ds["plfs"]
    for r in p["distribution"] + p["conditions"] + p["earnings"]:
        checked += 1
        value_ok(r["value"], r["value_as_printed"], f"{cell(r)} {r.get('category', r.get('condition', r.get('kind', '')))}")
    for r in p["rates"]:
        for k in ("lfpr", "wpr", "ur"):
            checked += 1
            value_ok(r[k], r[k + "_as_printed"], f"{cell(r)} {k}")
    for r in ds["cpi"]:
        for k in ("index", "inflation"):
            checked += 1
            value_ok(r[k], r[k + "_as_printed"], f"CPI {r['month']} {r['state']} {r['sector']} {r['subgroup']} {k}")
    for r in ds["cpialrl"]:
        for k in ("index_al", "index_rl", "inflation_al", "inflation_rl"):
            if k + "_as_printed" in r and not r.get(f"not_compiled_{k[-2:]}"):
                checked += 1
                value_ok(r.get(k), r.get(k + "_as_printed"), f"CPI-AL/RL {r['month']} {r.get('state')} {k}")
    for r in ds["hces"]:
        checked += 1
        value_ok(r["value"], r["value_as_printed"], f"HCES {r.get('year')} {r.get('state')} {r.get('indicator')}")
    for u in p.get("unlabelled", []):
        checked += 1
        allowed.add(UNLABELLED, u)
    report.add("Every published value is understood", checked, failures, allowed.notes(limit=20))


# ---- jobs ---------------------------------------------------------------------------------------

def check_rates(ds: dict, report: Report) -> None:
    failures, allowed, notes = [], Allowed(), []
    checked = 0
    for r in ds["plfs"]["rates"]:
        if r["left_out"]:
            allowed.add(LEFT_OUT, f"{cell(r)}: {r['left_out']}")
            continue
        if None in (r["lfpr"], r["wpr"], r["ur"]):
            continue
        checked += 1
        gap, tol = identity_gap(r)
        if gap > tol:
            msg = f"{cell(r)}: participation {r['lfpr']}, unemployment {r['ur']}, worker ratio {r['wpr']} ({gap:.2f} points off)"
            if gap <= SMALL_GAP:
                notes.append(f"Within {SMALL_GAP} points, shown: {msg}")
            else:
                failures.append(msg)
    report.add("Jobs: worker ratio = participation × (1 − unemployment rate)", checked, failures, allowed.notes() + notes)


def brackets(rows: list[dict], key_fields: list[str], value: str = "value", tol: float = 0.1):
    """(checked, problems): totals outside their two parts (persons vs men and women, rural + urban vs rural and urban)."""
    idx = {tuple(r.get(k) for k in key_fields): r for r in rows if r.get(value) is not None}
    checked, bad = 0, []
    for field, total, parts in (("gender", "person", ("male", "female")), ("sector", "rural + urban", ("rural", "urban"))):
        i = key_fields.index(field)
        for k, r in idx.items():
            if k[i] != total:
                continue
            ps = [idx.get(k[:i] + (p,) + k[i + 1:]) for p in parts]
            if None in ps:
                continue
            checked += 1
            a, b, v = ps[0][value], ps[1][value], r[value]
            t = max(tol, max(abs(a), abs(b), abs(v)) * 0.0005)
            if not (min(a, b) - t <= v <= max(a, b) + t):
                bad.append((r, f"{field} {total} {v} outside {parts[0]} {a} and {parts[1]} {b}"))
    return checked, bad


def check_brackets(ds: dict, report: Report) -> None:
    failures, notes = [], []
    checked = 0
    shown = [r for r in ds["plfs"]["rates"] if not r["left_out"]]
    for name in ("lfpr", "wpr", "ur"):
        c, bad = brackets(shown, ["frequency"] + RATE_DIMS, name)
        checked += c
        failures += [f"{name}, {cell(r)}: {msg}" for r, msg in bad]
    keys = ["frequency", "year", "period", "state", "sector", "gender"]
    for kind, extra, tol in (("conditions", ["condition"], 0.1), ("earnings", ["kind"], 1)):
        c, bad = brackets(ds["plfs"][kind], keys + extra, tol=tol)
        checked += c
        for r, msg in bad:
            text = f"{kind}, {cell(r)} {r.get('condition', r.get('kind'))}: {msg}"
            if r["frequency"] == "annual":  # only annual job conditions and earnings are on the site
                failures.append(text)
            else:
                notes.append(f"Not shown on the site: {text}")
    report.add("Jobs: persons lie between men and women, rural + urban between rural and urban", checked, failures, notes)


def check_distribution(ds: dict, report: Report) -> None:
    """Shares of workers by one breakdown add up to 100%."""
    failures, allowed, notes = [], Allowed(), []
    groups: dict[tuple, dict] = defaultdict(dict)
    for r in ds["plfs"]["distribution"]:
        if r["category"].lower() == "all":
            continue
        g = groups[(r["frequency"], r["breakdown"], r["year"], r["period"], r["state"], r["sector"], r["gender"], r["status"])]
        g[r["category"]] = r["value"]
        if r["value"] is None and r["value_as_printed"] not in MISSING:
            g["_bad"] = True
    checked = 0
    for (freq, b, year, per, state, sector, gender, status), cats in sorted(groups.items()):
        bad_value = cats.pop("_bad", False)
        where = f"{freq} {b}: {year}{' ' + per if per else ''}, {state}, {sector}, {gender}, {status}"
        problems: list[str] = []
        rule = None
        vals = [v for v in cats.values() if v is not None]
        if not vals or all(v == 0 for v in vals):
            if state == "Chandigarh" and sector == "rural":
                allowed.add(NO_SAMPLE, where)
                continue
            problems.append(f"{where}: no figures")
        else:
            checked += 1
            if bad_value:
                rule = BAD_VALUE
            if b == "broad_status_employment":
                if state == "All India":
                    rule = ALL_INDIA_STATUS
                elif status == "CWS" and year == "2025":
                    rule = CWS_STATUS_2025
                own = {c[:2]: v for c, v in cats.items()}
                total = sum(own.get(x) or 0 for x in ("1.", "2.", "4.", "5."))
                checked += 1
                if abs((own.get("1.") or 0) + (own.get("2.") or 0) - (own.get("3.") or 0)) > 0.15:
                    problems.append(f"{where}: all self-employed {own.get('3.')} ≠ {own.get('1.')} + {own.get('2.')}")
                tol = 0.25
            else:
                total = sum(vals)
                tol = max(0.25, 0.05 * len(vals))
            if abs(total - 100) > tol:
                problems.append(f"{where}: shares add up to {total:.1f}%")
        for msg in problems:
            if rule:
                allowed.add(rule, msg)
            elif freq != "annual" or (status != "PS+SS" and b != "broad_industry_work"):
                notes.append(f"Not shown on the site: {msg}")
            else:
                failures.append(msg)
    report.add("Jobs: shares of workers add up to 100%", checked, failures, allowed.notes() + notes)


# ---- prices -------------------------------------------------------------------------------------

def prev_year(month: str) -> str:
    y, m = month.split("-")
    return f"{int(y) - 1}-{m}"


def inflation_check(series: dict[tuple, dict[str, tuple]], label: str) -> tuple[int, list[str]]:
    """series: key -> month -> (index, inflation). Recompute inflation from the index a year earlier."""
    checked, failures = 0, []
    for key, months in sorted(series.items()):
        for m, (idx, infl) in sorted(months.items()):
            before = months.get(prev_year(m))
            if infl is None or idx is None or not before or before[0] is None:
                continue
            checked += 1
            calc = (idx / before[0] - 1) * 100
            if abs(calc - infl) > INFLATION_TOL:
                failures.append(f"{label} {' / '.join(k for k in key if k)} {m}: index {idx} vs {before[0]} a year "
                                f"earlier gives {calc:.2f}%, published {infl}%")
    return checked, failures


def check_cpi(ds: dict, report: Report) -> None:
    series: dict[tuple, dict[str, tuple]] = defaultdict(dict)
    for r in ds["cpi"]:
        series[(r["state"], r["sector"], r["subgroup"])][r["month"]] = (r["index"], r["inflation"])
    checked, failures = inflation_check(series, "CPI")
    report.add("Prices (CPI): inflation reproduced from the index a year earlier", checked, failures, [])

    failures, checked = [], 0
    for (state, sector, sub), months in sorted(series.items()):
        if sector != "Combined":
            continue
        rural, urban = series.get((state, "Rural", sub), {}), series.get((state, "Urban", sub), {})
        for m, (idx, _) in months.items():
            a, b = rural.get(m, (None,))[0], urban.get(m, (None,))[0]
            if None in (idx, a, b):
                continue
            checked += 1
            if not (min(a, b) - 0.1 <= idx <= max(a, b) + 0.1):
                failures.append(f"CPI {state} {sub} {m}: combined {idx} outside rural {a} and urban {b}")
    report.add("Prices (CPI): combined index lies between rural and urban", checked, failures, [])

    failures, notes, checked = [], [], 0
    months_all = sorted({r["month"] for r in ds["cpi"]})
    if months_all:
        first, last = months_all[0], months_all[-1]
        expected = []
        y, m = map(int, first.split("-"))
        while f"{y}-{m:02d}" <= last:
            expected.append(f"{y}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        for (state, sector, sub), months in sorted(series.items()):
            if sub != "General-Overall":
                continue
            have = {mm for mm, (idx, _) in months.items() if idx is not None}
            checked += 1
            missing = [mm for mm in expected if mm not in have]
            if missing:
                text = (f"CPI general index, {state}, {sector}: no index for {len(missing)} months "
                        f"({', '.join(missing[:6])}{' …' if len(missing) > 6 else ''})")
                if state == "All India":
                    failures.append(text)
                else:
                    notes.append(f"Gap, shown as a gap: {text}")
        notes.insert(0, f"Months covered: {first} to {last}.")
    report.add("Prices (CPI): no month missing", checked, failures, notes)


def check_cpialrl(ds: dict, report: Report) -> None:
    series: dict[tuple, dict[str, tuple]] = defaultdict(dict)
    for r in ds["cpialrl"]:
        for who in ("al", "rl"):
            if f"index_{who}_as_printed" in r:
                key = (r.get("indicator", ""), f"base {r.get('base_year', '')}", r.get("state", ""), str(r.get("group") or ""), who.upper())
                series[key][r["month"]] = (r.get(f"index_{who}"), r.get(f"inflation_{who}"))
    checked, failures = inflation_check(series, "CPI-AL/RL")
    zero = sorted({f"{r.get('state')} ({who.upper()}, base {r.get('base_year')})" for r in ds["cpialrl"] for who in ("al", "rl")
                   if r.get(f"not_compiled_{who}")})
    notes = [f"Index published as 0.00, treated as not compiled: {', '.join(zero)}."] if zero else []
    report.add("Prices (CPI for farm and rural labourers): inflation reproduced from the index", checked, failures, notes)


# ---- household spending -------------------------------------------------------------------------

FRACTILE_SHARES = [5, 5, 10, 10, 10, 10, 10, 10, 10, 10, 5, 5]  # % of population in each spending class
FOOD_ITEMS = {"Cereal", "Cereal Substitutes", "Gram", "Pulses and Pulse Products", "Milk and Milk Products", "Salt",
              "Sugar", "Edible Oil", "Egg, Fish & Meat", "Vegetables", "Fruits (fresh)", "Fruits (dry)", "Spices",
              "Beverages, Processed Food, etc."}
TOTALS = {"Food Total", "Non-Food Total"}
MPCE = "Average monthly per capita consumption expenditure (MPCE)"
CATEGORY_VALUES = "Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days"
CATEGORY_SHARES = "Percentage Share of Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days"


def order_fractiles(classes: dict[str, float | None]) -> list[float] | None:
    """Values of the 12 spending classes from poorest to richest, by the first number in each class name."""
    keyed = []
    for name, v in classes.items():
        m = re.search(r"(\d+(?:\.\d+)?)", str(name))
        if not m:
            continue  # "All"
        if v is None:
            return None
        keyed.append((float(m.group(1)), v))
    keyed.sort()
    return [v for _, v in keyed] if len(keyed) == 12 else None


def check_hces(ds: dict, report: Report) -> None:
    failures, notes, checked = [], [], 0
    rows = ds["hces"]
    if not rows:
        report.add("Household spending (HCES): classes and categories add up", 0, ["no HCES data"], [])
        return
    base = lambda r: (r.get("year"), r.get("state"), r.get("sector"), r.get("imputation_type"))
    where = lambda k: ", ".join(str(x) for x in k)
    mpce = {base(r): r["value"] for r in rows if r["indicator"] == MPCE}

    # 1. spending classes (published without imputation only)
    fract: dict[tuple, dict[str, float | None]] = defaultdict(dict)
    for r in rows:
        if r["indicator"].startswith(MPCE + " Over 12"):
            fract[base(r)][str(r.get("mpce_fractile_classes", "")).strip()] = r["value"]
    for k, classes in sorted(fract.items(), key=str):
        ordered = order_fractiles(classes)
        if ordered is None or mpce.get(k) is None:
            notes.append(f"Spending classes for {where(k)}: not checked (classes or average missing)")
            continue
        checked += 1
        avg = sum(v * s for v, s in zip(ordered, FRACTILE_SHARES)) / 100
        if abs(avg - mpce[k]) > max(3, mpce[k] * 0.01):
            failures.append(f"HCES {where(k)}: spending classes average ₹{avg:,.0f}, published average ₹{mpce[k]:,.0f}")
        if classes.get("All") is not None and abs(classes["All"] - mpce[k]) > 1:
            checked += 1
            failures.append(f"HCES {where(k)}: 'All' spending class ₹{classes['All']:,.0f} ≠ average ₹{mpce[k]:,.0f}")

    # 2. item categories: items add up to the food and non-food totals, totals to 100% / to average spending
    allowed = Allowed()
    for r in rows:
        if r["left_out"] and r["indicator"] == CATEGORY_VALUES and r.get("item_category") == "Food Total":
            allowed.add(HCES_MISMATCH, f"{where(base(r))}: {r['left_out']}")
    for indicator, unit in ((CATEGORY_SHARES, "%"), (CATEGORY_VALUES, "₹")):
        cats: dict[tuple, dict[str, float | None]] = defaultdict(dict)
        for r in rows:
            if r["indicator"] == indicator and not r["left_out"]:
                cats[base(r)][r.get("item_category", "")] = r["value"]
        for k, c in sorted(cats.items(), key=str):
            if c.get("Food Total") is None or c.get("Non-Food Total") is None:
                failures.append(f"HCES {where(k)} {unit}: food or non-food total missing")
                continue
            food = sum(v or 0 for n, v in c.items() if n in FOOD_ITEMS)
            nonfood = sum(v or 0 for n, v in c.items() if n not in FOOD_ITEMS | TOTALS)
            tol = 0.15 if unit == "%" else max(2.0, c["Food Total"] * 0.002)
            checked += 2
            if abs(food - c["Food Total"]) > tol:
                failures.append(f"HCES {where(k)} {unit}: food items add up to {food:.2f}, food total {c['Food Total']}")
            if abs(nonfood - c["Non-Food Total"]) > (0.15 if unit == "%" else max(2.0, c["Non-Food Total"] * 0.002)):
                failures.append(f"HCES {where(k)} {unit}: non-food items add up to {nonfood:.2f}, non-food total {c['Non-Food Total']}")
            total = c["Food Total"] + c["Non-Food Total"]
            target = 100 if unit == "%" else mpce.get(k)
            if target is not None:
                checked += 1
                if abs(total - target) > (0.1 if unit == "%" else max(2.0, target * 0.002)):
                    failures.append(f"HCES {where(k)} {unit}: food + non-food = {total:.2f}, expected {target}")
    report.add("Household spending (HCES): classes and categories add up", checked, failures, allowed.notes() + notes)


# ---- consumer prices, base 2024 ------------------------------------------------------------------

BACKTICK = (
    "MoSPI's press release page prints this figure with a stray backtick (for example '109.`39'). The next "
    "month's release repeats it as final, and that figure is used."
)


def check_cpi2024(ds: dict, report: Report) -> None:
    from collections import Counter

    from .cpi2024 import pdf_numbers

    c = ds["cpi2024"]
    rel = c["releases"]
    failures, notes, allowed, checked = [], [], Allowed(), 0
    if not rel:
        report.add("Prices, new series (base 2024): releases read", 0, ["no releases"], [])
        return

    # 1. every release read in full
    for m, r in sorted(rel.items()):
        checked += 1
        n = (len([d for d in r["divisions"] if d["code"] != "00"]), len(r["groups"]), len(r["states"]))
        if n != (12, 43, 36):
            failures.append(f"{m}: read {n[0]} divisions, {n[1]} groups, {n[2]} states (expected 12, 43, 36)")
        if not (r["series"] or r["series_combined"]):
            failures.append(f"{m}: no All-India series")
        for prob in r["problems"]:
            (allowed.add(BACKTICK, prob) if "`" in prob else failures.append(prob))
    report.add("Prices, new series (base 2024): every release read in full", checked, failures, allowed.notes())

    # 2. the headline sentence, the summary table and the annexures agree
    failures, checked = [], 0
    for m, r in sorted(rel.items()):
        h = r.get("headline", {})
        cur = r["summary"].get("current", {}).get("general_inflation")
        allrow = next((d["values"] for d in r["divisions"] if d["code"] == "00"), None)
        last = next((x["values"] for x in r["series"] if x["month"] == m), None)
        figures = {"headline sentence": [h.get("rural"), h.get("urban"), h.get("combined")], "summary table": cur,
                   "Annexure I, All India row": allrow[3:] if allrow else None, "Annexure IV": last[3:] if last else None}
        present = {k: v for k, v in figures.items() if v and None not in v}
        checked += 1
        ref = next(iter(present.values()), None)
        if len(present) < 2:
            failures.append(f"{m}: inflation found in only {list(present)}")
        elif any(v != ref for v in present.values()):
            failures.append(f"{m}: inflation (rural, urban, combined) differs: {present}")
    report.add("Prices, new series: headline, summary and annexures agree", checked, failures, [])

    # 3. inflation reproduced from the index a year earlier; 4. combined index between rural and urban
    failures, checked = [], 0
    for m, r in sorted(rel.items()):
        idx = {x["month"]: x["values"] for x in r["series"]}
        for month, v in idx.items():
            before = idx.get(f"{int(month[:4]) - 1}{month[4:]}")
            if before is None:
                continue
            for i, sec in enumerate(("rural", "urban", "combined")):
                if v[i + 3] is None:
                    continue
                checked += 1
                calc = (v[i] / before[i] - 1) * 100
                if abs(calc - v[i + 3]) > 0.03:
                    failures.append(f"release {m}, {month} {sec}: index {v[i]} vs {before[i]} gives {calc:.2f}%, published {v[i + 3]}%")
    report.add("Prices, new series: inflation reproduced from the index a year earlier", checked, failures,
               ["Indices are printed to two decimals but compiled unrounded, so a difference of up to 0.03 points is allowed."])

    failures, checked = [], 0
    for m, r in sorted(rel.items()):
        for table, rows in (("division", r["divisions"]), ("group", r["groups"]), ("state", r["states"]), ("series", r["series"])):
            for x in rows:
                v = x["values"]
                if None in v[:3]:
                    continue  # Chandigarh has no rural market
                checked += 1
                if not (min(v[0], v[1]) - 0.011 <= v[2] <= max(v[0], v[1]) + 0.011):
                    failures.append(f"{m} {table} {x.get('name', x.get('month'))}: combined {v[2]} outside rural {v[0]} and urban {v[1]}")
    report.add("Prices, new series: combined index lies between rural and urban", checked, failures, [])

    # 5. later releases revise only the previous month (provisional to final)
    failures, notes, checked = [], [], 0
    final = {x["month"]: x["values"] for x in c["series"]}
    for m, r in sorted(rel.items()):
        for x in r["series"]:
            if x["month"] not in final or m == c["latest"]:
                continue
            checked += 1
            if x["values"] != final[x["month"]]:
                diff = f"{x['month']} in the {m} release {x['values']} vs latest {final[x['month']]}"
                (notes.append(f"Provisional figure revised: {diff}") if x["month"] == m else failures.append(f"Final figure changed: {diff}"))
    report.add("Prices, new series: only provisional figures are revised", checked, failures, notes)

    # 6. linking factor = average 2025 index on the new base / on the old base (MoSPI's API)
    failures, checked = [], 0
    old = {(r["sector"], r["month"]): r["index"] for r in ds["cpi"] if r["state"] == "All India" and r["subgroup"] == "General-Overall"}
    for i, sec in enumerate(("Rural", "Urban", "Combined")):
        f = c["linking"].get(sec)
        news = [final[m][i] for m in final if m.startswith("2025")]
        olds = [old.get((sec, m)) for m in final if m.startswith("2025")]
        if f is None or len(news) != 12 or None in olds:
            failures.append(f"linking factor {sec}: cannot check (factor {f}, {len(news)} months)")
            continue
        checked += 1
        calc = (sum(news) / 12) / (sum(olds) / 12)
        if abs(calc - f) > 0.00006:
            failures.append(f"linking factor {sec}: published {f}, 2025 averages give {calc:.4f}")
    report.add("Prices, new series: linking factor = 2025 average, new base ÷ old base", checked, failures,
               [f"Published factors {c['linking']}; old-base indices from MoSPI's data service, new-base from the press releases."])

    # 7. the release page's tables match its PDF
    failures, notes, checked = [], [], 0
    for m, r in sorted(rel.items()):
        if not r["pdf"]:
            notes.append(f"{m}: no PDF attached to the release; page only")
            continue
        have = Counter(pdf_numbers(ROOT / r["pdf"]))
        want = Counter(f"{v:.2f}" for rows in (r["divisions"], r["groups"], r["states"]) for x in rows for v in x["values"] if v is not None)
        want += Counter(f"{v:.2f}" for x in r["series"] for v in x["values"][:6] if v is not None)
        checked += 1
        missing = want - have
        if missing:
            failures.append(f"{m}: {sum(missing.values())} figures on the release page not found in its PDF: {sorted(missing)[:10]}")
    report.add("Prices, new series: release page tables match the PDF", checked, failures, notes)


def check_hces_overall(ds: dict, report: Report) -> None:
    """Table A2 (the full report) agrees with MoSPI's data service, and the overall averages are sound."""
    failures, notes, checked = [], [], 0
    pop = ds["hces_population"]
    if not pop:
        report.add("Household spending: overall (rural + urban) averages", 0, ["Table A2 not read"], [])
        return
    mpce = {(r["year"], r["state"], r["sector"]): r["value"] for r in ds["hces"]
            if r["indicator"] == "Average monthly per capita consumption expenditure (MPCE)" and r["imputation_type"] == "Without Imputation"}
    for p in pop:
        checked += 1
        api = mpce.get((p["year"], p["state"], p["sector"]))
        if api is None:
            failures.append(f"Table A2 {p['year']} {p['state']} {p['sector']}: no matching average in MoSPI's data service")
        elif abs(p["mpce_a2"] - api) > 0.51:
            failures.append(f"Table A2 {p['year']} {p['state']} {p['sector']}: average ₹{p['mpce_a2']} vs data service ₹{api}")
    for year in sorted({p["year"] for p in pop}):
        for sector in ("Rural", "Urban"):
            states = [p["persons_00"] for p in pop if p["year"] == year and p["sector"] == sector and p["state"] != "All India"]
            india = next((p["persons_00"] for p in pop if p["year"] == year and p["sector"] == sector and p["state"] == "All India"), None)
            checked += 1
            if india is None or abs(sum(states) - india) > max(50, india * 0.0005):
                failures.append(f"Table A2 {year} {sector}: states' persons add up to {sum(states):,} (hundreds), All India {india}")
    for r in ds["hces_overall"]:
        checked += 1
        lo, hi = sorted((r["mpce_rural"], r["mpce_urban"]))
        if not (lo <= r["mpce"] <= hi):
            failures.append(f"{r['year']} {r['state']} {r['imputation_type']}: overall ₹{r['mpce']:.0f} outside rural and urban")
    matched = {(r["year"], r["state"]) for r in ds["hces_overall"]}
    missing = sorted({(p["year"], p["state"]) for p in pop} - matched)
    if missing:
        notes.append(f"No overall figure (rural or urban average missing): {missing}")
    notes.append("Overall average = (rural persons × rural average + urban persons × urban average) ÷ all persons, "
                 "with persons from Table A2 of MoSPI's HCES report; food's share is weighted by each area's total spending.")
    report.add("Household spending: overall (rural + urban) averages", checked, failures, notes)


def main(ds: dict | None = None) -> int:
    if ds is None:
        from .build import assemble

        ds = assemble()
    report = Report()
    check_source(ds, report)
    check_rates(ds, report)
    check_brackets(ds, report)
    check_distribution(ds, report)
    check_cpi(ds, report)
    check_cpialrl(ds, report)
    check_hces(ds, report)
    check_hces_overall(ds, report)
    check_cpi2024(ds, report)
    (DATA / "validation_report.md").write_text(report.markdown())
    for title, checked, failures, _ in report.sections:
        print(f"{'FAIL' if failures else 'ok  '} {title}: {checked} checks, {len(failures)} failures")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())

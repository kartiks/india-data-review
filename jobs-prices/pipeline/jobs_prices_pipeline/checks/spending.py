"""Household spending (HCES): spending classes and item categories add up; Table A2 and the overall averages."""

import re
from collections import defaultdict

from pipeline_common.report import Allowed, Report


HCES_MISMATCH = (
    "In MoSPI's data service, the spending by item category filed under these states (rural, 2022-23, without "
    "imputation) does not add up to the state's own average spending; it appears to be other states' figures "
    "(Goa's categories add up to Andhra Pradesh's average, Haryana's to Assam's, Himachal Pradesh's to Bihar's, "
    "Jharkhand's to Chhattisgarh's). The category breakdown (rupees and shares) for these cells is left out of the "
    "site; the average itself is shown."
)


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


def hces_key(r: dict) -> tuple:
    return (r.get("year"), r.get("state"), r.get("sector"), r.get("imputation_type"))


def where(k: tuple) -> str:
    return ", ".join(str(x) for x in k)


def hces_classes(rows: list[dict], mpce: dict[tuple, float | None]) -> tuple[int, list[str], list[str]]:
    """(checked, failures, notes): the 12 spending classes (published without imputation only), weighted by their
    population shares, give the average; the 'All' class equals it."""
    failures, notes, checked = [], [], 0
    fract: dict[tuple, dict[str, float | None]] = defaultdict(dict)
    for r in rows:
        if r["indicator"].startswith(MPCE + " Over 12"):
            fract[hces_key(r)][str(r.get("mpce_fractile_classes", "")).strip()] = r["value"]
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
    return checked, failures, notes


def hces_categories(rows: list[dict], mpce: dict[tuple, float | None]) -> tuple[int, list[str], Allowed]:
    """(checked, failures, allowed): item categories add up to the food and non-food totals, and the totals to 100%
    (shares) or to the average (rupees). Cells the build left out are allowed with their reason."""
    failures, checked, allowed = [], 0, Allowed()
    for r in rows:
        if r["left_out"] and r["indicator"] == CATEGORY_VALUES and r.get("item_category") == "Food Total":
            allowed.add(HCES_MISMATCH, f"{where(hces_key(r))}: {r['left_out']}")
    for indicator, unit in ((CATEGORY_SHARES, "%"), (CATEGORY_VALUES, "₹")):
        cats: dict[tuple, dict[str, float | None]] = defaultdict(dict)
        for r in rows:
            if r["indicator"] == indicator and not r["left_out"]:
                cats[hces_key(r)][r.get("item_category", "")] = r["value"]
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
    return checked, failures, allowed


def check_hces(ds: dict, report: Report) -> None:
    rows = ds["hces"]
    if not rows:
        report.add("Household spending (HCES): classes and categories add up", 0, ["no HCES data"], [])
        return
    mpce = {hces_key(r): r["value"] for r in rows if r["indicator"] == MPCE}
    checked, failures, notes = hces_classes(rows, mpce)
    c, f, allowed = hces_categories(rows, mpce)
    report.add("Household spending (HCES): classes and categories add up", checked + c, failures + f, notes, allowed)


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

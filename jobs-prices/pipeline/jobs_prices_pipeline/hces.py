"""Household Consumption Expenditure Survey (HCES): MoSPI's data service, and Table A2 of the full report for overall
(rural + urban) averages."""

from collections import defaultdict

from pipeline_common.numbers import number

from .common import ROOT, load

HCES_MPCE = "Average monthly per capita consumption expenditure (MPCE)"
HCES_CATEGORIES = ("Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days",
                   "Percentage Share of Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days")


def read(manifest: dict, problems: list[str]) -> list[dict]:
    out = []
    for key, entry, body in load(manifest, "hces/"):
        for r in body["rows"]:
            cat = next((r[k] for k in ("mpce_fractile_classes", "item_category", "employment_of_households", "social_group", "cereal")
                        if r.get(k) not in (None, "")), "")
            out.append({**{k: v for k, v in r.items() if k != "value"}, "category": str(cat).strip(),
                        "value": number(r.get("value")), "value_as_printed": r.get("value"), "left_out": "", "source": key})
    # Spending by item category must add up to the average spending of the same state, year, area and method.
    # Where it does not, the category rows appear to be another state's, so both the rupee values and the
    # shares for that cell are left out.
    base = lambda r: (r.get("year"), r.get("state"), r.get("sector"), r.get("imputation_type"))
    mpce = {base(r): r["value"] for r in out if r["indicator"] == HCES_MPCE}
    totals: dict[tuple, float] = defaultdict(float)
    for r in out:
        if r["indicator"] == HCES_CATEGORIES[0] and r.get("item_category") in ("Food Total", "Non-Food Total"):
            totals[base(r)] += r["value"] or 0
    for k, total in totals.items():
        m = mpce.get(k)
        if m and abs(total - m) > max(2.0, m * 0.002):
            why = f"spending by category adds up to ₹{total:,.0f}, but average spending for this cell is ₹{m:,.0f}"
            for r in out:
                if r["indicator"] in HCES_CATEGORIES and base(r) == k:
                    r["left_out"] = why
    return out


# Table A2 spellings -> the names MoSPI's data service uses for the same state or UT
A2_NAMES = {"All-India": "All India", "Dadra and Nagar Haveli & Daman and Diu": "Dadra & Nagar Haveli and Daman & Diu"}


def population(manifest: dict) -> list[dict]:
    """Table A2 of MoSPI's HCES report: estimated households and persons (adults + children), and average MPCE, for
    each state's rural and urban areas ('All classes' rows). Estimated numbers are printed in hundreds."""
    import openpyxl

    out = []
    for key, e in sorted(manifest.items()):
        if not key.startswith("hces_report/") or not key.endswith("/TableA2") or e.get("empty"):
            continue
        year = key.split("/")[1]
        ws = openpyxl.load_workbook(ROOT / e["file"], data_only=True, read_only=True).worksheets[0]
        sector = state = None
        for r in ws.iter_rows(min_row=6, values_only=True):
            if r[0] in ("Rural", "Urban"):
                sector = r[0]
            if r[1]:
                state = str(r[1]).strip()
            if r[2] == "All classes":
                name = A2_NAMES.get(state, state)
                out.append({"year": year, "state": name, "sector": sector,
                            "households_00": r[3], "persons_00": (r[6] or 0) + (r[9] or 0), "mpce_a2": r[10],
                            "source": key})
    return out


def overall(population: list[dict], rows: list[dict]) -> list[dict]:
    """Rural + urban averages, weighting MoSPI's rural and urban figures by the survey's own estimated persons
    (Table A2). Average spending per person is a person-weighted mean, so this is the all-area average. Food's share
    of spending weights each area's share by its total spending (persons x average spending)."""
    pop = {(p["year"], p["state"], p["sector"]): p for p in population}
    mpce = {(r["year"], r["state"], r["sector"], r["imputation_type"]): r["value"] for r in rows
            if r["indicator"] == HCES_MPCE and not r["left_out"]}
    food = {(r["year"], r["state"], r["sector"], r["imputation_type"]): r["value"] for r in rows
            if r["indicator"] == HCES_CATEGORIES[1] and r.get("item_category") == "Food Total" and not r["left_out"]}
    out = []
    for (year, state, sector), p in sorted(pop.items()):
        if sector != "Rural":
            continue
        u = pop.get((year, state, "Urban"))
        for imp in ("Without Imputation", "With Imputation"):
            mr, mu = mpce.get((year, state, "Rural", imp)), mpce.get((year, state, "Urban", imp))
            pr, pu = p["persons_00"], (u or {}).get("persons_00")
            if None in (mr, mu, pr, pu) or not (pr + pu):
                continue
            rec = {"year": year, "state": state, "imputation_type": imp, "persons_rural_00": pr, "persons_urban_00": pu,
                   "mpce_rural": mr, "mpce_urban": mu, "mpce": (pr * mr + pu * mu) / (pr + pu), "source": p["source"]}
            fr, fu = food.get((year, state, "Rural", imp)), food.get((year, state, "Urban", imp))
            if fr is not None and fu is not None:
                rec["food_share"] = (pr * mr * fr + pu * mu * fu) / (pr * mr + pu * mu)
            out.append(rec)
    return out

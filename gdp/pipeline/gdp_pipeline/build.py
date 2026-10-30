"""Turn the downloaded files into the site's datasets.

Outputs (in gdp/data/):
- national_accounts.csv : every row MoSPI published, one line per value, with
                          names as printed, our ids, and the source URL.
- gdp.json              : the same figures arranged for the site (by series,
                          year and estimate stage), plus the Budget's GDP
                          assumptions and the forecasts.

Nothing here changes a published number. The only arithmetic is:
- growth for the back series (1950-51 to 2011-12), which MoSPI publishes as
  levels only: growth = this year / last year - 1, from constant-price GDP;
- nothing is converted from ₹ lakh: the two indicators labelled "₹ Lakh"
  (taxes and subsidies on products) are in fact in ₹ crore (see UNIT_LABEL_ERRORS);
- where only the finer industries are published, the three broad service
  groups are added up from their parts (checks confirm parts = groups wherever
  MoSPI publishes both).

Run: uv run python -m gdp_pipeline.build
"""

import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import budget, forecasts
from .sources import BUDGETS, NAS_INDICATORS, NAS_SERIES

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "manifest.json"

INDICATORS = {
    1: ("gva", "Gross value added (GVA)"),
    2: ("net_taxes", "Net taxes on products"),
    3: ("product_taxes", "Taxes on products"),
    4: ("product_subsidies", "Subsidies on products"),
    5: ("gdp", "Gross domestic product (GDP)"),
    6: ("cfc", "Consumption of fixed capital (depreciation)"),
    7: ("ndp", "Net domestic product"),
    8: ("gcf_by_industry", "Gross capital formation by industry of use"),
    9: ("gfcf", "Gross fixed capital formation (investment in fixed assets)"),
    10: ("pfce", "Private final consumption expenditure (household spending)"),
    11: ("gfce", "Government final consumption expenditure"),
    12: ("stocks", "Change in stocks"),
    13: ("valuables", "Valuables"),
    14: ("exports", "Exports of goods and services"),
    15: ("imports", "Imports of goods and services"),
    16: ("primary_income_row", "Primary income receivable, net, from rest of world"),
    17: ("gni", "Gross national income"),
    18: ("transfers_row", "Other current transfers, net, from rest of world"),
    19: ("gndi", "Gross national disposable income"),
    20: ("saving", "Gross saving"),
    21: ("gva_growth", "GVA growth rate"),
    22: ("gdp_growth", "GDP growth rate"),
}
GROWTH_INDICATORS = {21, 22}

# Official estimate stages, in the order they are published.
STAGES = [
    ("AE1", "First Advance Estimates", "First Advance Estimate", "about 1 week after the year's 9th month (early January)"),
    ("AE2", "Second Advance Estimates", "Second Advance Estimate", "end of February, before the year ends"),
    ("PE", "Provisional Estimates", "Provisional Estimate", "end of May, 2 months after the year ends"),
    ("RE1", "First Revised Estimates", "First Revised Estimate", "about 1 year after the year ends"),
    ("RE2", "Second Revised Estimates", "Second Revised Estimate", "about 2 years after the year ends"),
    ("RE3", "Third Revised Estimates", "Third Revised Estimate", "about 3 years after the year ends"),
    ("ADD", "Additional Revision", "Additional revision", "special revision of 2011-12 to 2013-14"),
    ("FINAL", "Final Estimates", "Final Estimate", "the last revision under MoSPI's current revision policy"),
]
STAGE_BY_LABEL = {label: sid for sid, label, _, _ in STAGES}
STAGE_ORDER = {sid: i for i, (sid, _, _, _) in enumerate(STAGES)}

INDUSTRIES = {
    "Agriculture, Livestock, Forestry and Fishing": "agriculture",
    "Mining and Quarrying": "mining",
    "Manufacturing": "manufacturing",
    "Electricity, Gas, Water Supply & Other Utility Services": "utilities",
    "Construction": "construction",
    "Trade, Hotels, Transport, Communication & Services Related to Broadcasting": "trade_transport",
    "Trade, Repair, Hotels and Restaurants": "trade_hotels",
    "Transport, Storage, Communication & Services Related to Broadcasting": "transport_comm",
    "Financial, Real Estate & Professional Services": "finance_realestate",
    "Financial Services": "financial",
    "Real Estate, Ownership of Dwelling & Professional Services": "real_estate",
    "Public Administration, Defence & Other Services": "public_other",
    "Public Administration and Defence": "public_admin",
    "Other Services": "other_services",
    "Total Gross Value Added": "total",
    "Total Gross Capital Formation": "total",
    "Total GVA Growth Rate": "total",
}
# The eight broad groups MoSPI uses in its press notes, and the finer industries that make up three of them.
GROUPS = {
    "trade_transport": ["trade_hotels", "transport_comm"],
    "finance_realestate": ["financial", "real_estate"],
    "public_other": ["public_admin", "other_services"],
}
BROAD = ["agriculture", "mining", "manufacturing", "utilities", "construction",
         "trade_transport", "finance_realestate", "public_other"]
INDUSTRY_LABELS = {
    "agriculture": "Agriculture, forestry & fishing",
    "mining": "Mining & quarrying",
    "manufacturing": "Manufacturing",
    "utilities": "Electricity, gas, water & utilities",
    "construction": "Construction",
    "trade_transport": "Trade, hotels, transport & communication",
    "trade_hotels": "Trade, repair, hotels & restaurants",
    "transport_comm": "Transport, storage & communication",
    "finance_realestate": "Finance, real estate & professional services",
    "financial": "Financial services",
    "real_estate": "Real estate, dwellings & professional services",
    "public_other": "Public administration, defence & other services",
    "public_admin": "Public administration & defence",
    "other_services": "Other services",
    "total": "Total GVA",
}
SECTORS = {
    "Public Non-Financial Corporations": "public_nonfin",
    "Private Non-Financial Corporations": "private_nonfin",
    "Public Financial Corporations": "public_fin",
    "Private Financial Corporations": "private_fin",
    "General Government": "government",
    "Household Sector": "households",
    "Households Including NPISH": "households",
    "Total Gross Fixed Capital Formation": "total",
    "Total Gross Saving": "total",
    "Total Consumption of Fixed Capital": "total",
    "Total Gross Value Added": "total",
}
SECTOR_LABELS = {
    "public_nonfin": "Public non-financial companies",
    "private_nonfin": "Private non-financial companies",
    "public_fin": "Public financial companies",
    "private_fin": "Private financial companies",
    "government": "Government",
    "households": "Households",
    "total": "Total",
}


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_").replace("__", "_")


def number(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", ""))
    except ValueError:
        return None
    return None if math.isnan(x) else x


def series_key(base: str, series: str) -> str:
    return base if series == "Current" else f"{base}-back"


def load_rows(manifest: dict) -> tuple[list[dict], list[str]]:
    """Every published row with ids attached. Returns (rows, problems)."""
    out: list[dict] = []
    problems: list[str] = []
    for base, series, freq in NAS_SERIES:
        for code in NAS_INDICATORS:
            key = f"nas/{base}/{series}/{freq}/ind{code:02d}"
            entry = manifest.get(key)
            if not entry or entry.get("empty"):
                continue
            body = json.loads((ROOT / entry["file"]).read_text())
            ind_id, _ = INDICATORS[code]
            for r in body["rows"]:
                if not re.fullmatch(r"\d{4}-(\d{2}|2000)", str(r.get("year"))):
                    problems.append(f"{key}: row with year {r.get('year')!r} left out (not a fiscal year): {r.get('indicator')} "
                                    f"{r.get('revision')} {r.get('current_price')}")
                    continue
                stage_label = r.get("revision")
                stage = STAGE_BY_LABEL.get(stage_label) if stage_label else ("BACK" if series == "Back" else "LATEST")
                if stage is None:
                    problems.append(f"{key}: unknown estimate stage {stage_label!r}")
                    continue
                industry = r.get("industry")
                sector = r.get("institutional_sector")
                ind = INDUSTRIES.get(industry) if industry else None
                if industry and ind is None:
                    problems.append(f"{key}: unknown industry {industry!r}")
                sec = SECTORS.get(sector) if sector else None
                if sector and sec is None:
                    problems.append(f"{key}: unknown institutional sector {sector!r}")
                unit = r.get("unit") or ""
                cur, con = number(r.get("current_price")), number(r.get("constant_price"))
                out.append({
                    "series": series_key(base, series),
                    "base_year": base,
                    "frequency": "annual" if freq == "Annually" else "quarterly",
                    "year": r["year"],
                    "quarter": r.get("quarter") or "",
                    "indicator_code": code,
                    "indicator": ind_id,
                    "indicator_as_printed": r.get("indicator"),
                    "stage": stage,
                    "stage_as_printed": stage_label or "",
                    "industry": ind or "",
                    "industry_as_printed": industry or "",
                    "subindustry": slug(r["subindustry"]) if r.get("subindustry") else "",
                    "subindustry_as_printed": r.get("subindustry") or "",
                    "sector": sec or "",
                    "sector_as_printed": sector or "",
                    "current_price": cur,
                    "constant_price": con,
                    "unit": unit,
                    "source_url": entry["url"],
                    "source_sha256": entry["sha256"],
                })
    return out, problems


def dedupe(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """MoSPI sometimes repeats a total with the industry/sector left blank. Keep one; report any disagreement."""
    seen: dict[tuple, dict] = {}
    notes: list[str] = []
    conflicts: set[tuple] = set()
    for r in rows:
        dim = r["industry"] or r["sector"] or ("total" if r["indicator"] in ("gva", "saving", "cfc", "gfcf", "gva_growth", "gcf_by_industry") else "")
        k = (r["series"], r["frequency"], r["year"], r["quarter"], r["indicator"], r["stage"], dim, r["subindustry"])
        if k in seen:
            a = seen[k]
            for p in ("current_price", "constant_price"):
                if a[p] is not None and r[p] is not None and abs(a[p] - r[p]) > (0.05 if r["unit"] == "%" else 2):
                    conflicts.add(k)
                    what = ({"current_price": "nominal growth", "constant_price": "real growth"} if r["unit"] == "%" else
                            {"current_price": "current-price value", "constant_price": "constant-price value"})[p]
                    notes.append(f"{label(k)}: published twice with different {what} ({a[p]:g} and {r[p]:g}); "
                                 "neither is used")
            # keep the row that names its industry/sector, fill gaps from the other
            for p in ("current_price", "constant_price"):
                if a[p] is None and r[p] is not None:
                    a[p] = r[p]
            if not a["industry"] and r["industry"]:
                a["industry"], a["industry_as_printed"] = r["industry"], r["industry_as_printed"]
            if not a["sector"] and r["sector"]:
                a["sector"], a["sector_as_printed"] = r["sector"], r["sector_as_printed"]
            continue
        r = dict(r)
        if dim == "total" and not r["industry"] and not r["sector"]:
            if r["indicator"] in ("saving", "cfc", "gfcf"):
                r["sector"] = "total"
            else:
                r["industry"] = "total"
        seen[k] = r
    return [r for k, r in seen.items() if k not in conflicts], sorted(set(notes))


def label(k: tuple) -> str:
    series, freq, year, quarter, ind, stage, dim, sub = k
    parts = [f"{series} series", year + (f" {quarter}" if quarter else ""), ind, stage, dim, sub]
    return ", ".join(p for p in parts if p)


# MoSPI labels taxes and subsidies on products "₹ Lakh", but the values are ₹ crore:
# taxes − subsidies equals net taxes on products (published in ₹ crore) exactly
# (checked in checks.py). So the label is not applied.
UNIT_LABEL_ERRORS = {"product_taxes", "product_subsidies"}


def to_crore(v: float | None, unit: str, indicator: str = "") -> float | None:
    if v is None:
        return None
    return v / 100 if unit == "₹ Lakh" and indicator not in UNIT_LABEL_ERRORS else v


def pair(r: dict) -> dict:
    cur = to_crore(r["current_price"], r["unit"], r["indicator"])
    con = to_crore(r["constant_price"], r["unit"], r["indicator"])
    out = {}
    if cur is not None:
        out["cur"] = cur
    if con is not None:
        out["con"] = con
    return out


def growth_pair(r: dict) -> dict:
    out = {}
    if r["constant_price"] is not None:
        out["real"] = r["constant_price"]
    if r["current_price"] is not None:
        out["nominal"] = r["current_price"]
    return out


def arrange(rows: list[dict]) -> dict:
    """series -> frequency -> year[/quarter] -> stage -> figures."""
    tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    for r in rows:
        period = r["year"] if r["frequency"] == "annual" else f"{r['year']} {r['quarter']}"
        node = tree[r["series"]][r["frequency"]][period][r["stage"]]
        ind = r["indicator"]
        if ind == "gdp_growth":
            node.setdefault("growth", {})["gdp"] = growth_pair(r)
        elif ind == "gva_growth":
            node.setdefault("gva_growth", {})[r["industry"] or "total"] = growth_pair(r)
        elif ind == "gva":
            if r["subindustry"]:
                node.setdefault("gva_sub", {}).setdefault(r["industry"], {})[r["subindustry"]] = pair(r)
            else:
                node.setdefault("gva_by_industry", {})[r["industry"] or "total"] = pair(r)
        elif ind == "gcf_by_industry":
            if not r["subindustry"]:
                node.setdefault("gcf_by_industry", {})[r["industry"] or "total"] = pair(r)
        elif ind in ("gfcf", "saving", "cfc") and r["sector"] and r["sector"] != "total":
            node.setdefault(f"{ind}_by_sector", {})[r["sector"]] = pair(r)
        else:
            node[ind] = pair(r)
    # Where MoSPI gives only the finer industries (the back series; early years of the 2011-12 series),
    # build the three broad service groups from their parts, marked "summed".
    for freq in (f for series in tree.values() for f in series.values()):
        for stages in freq.values():
            for node in stages.values():
                gva = node.get("gva_by_industry", {})
                for group, parts in GROUPS.items():
                    if group not in gva and all(p in gva for p in parts):
                        gva[group] = {k: sum(gva[p][k] for p in parts) for k in ("cur", "con") if all(k in gva[p] for p in parts)}
                        gva[group]["summed"] = True
    return json.loads(json.dumps(tree))


def latest_stage(stages: dict) -> str:
    return max(stages, key=lambda s: STAGE_ORDER.get(s, 99))


def long_run(tree: dict) -> list[dict]:
    """One row per year, 1950-51 onward, on the 2011-12 base: back series to 2010-11, then the latest estimate."""
    back = tree["2011-12-back"]["annual"]
    cur = tree["2011-12"]["annual"]
    years = sorted(set(back) | set(cur))
    out = []
    prev = None
    for y in years:
        if y in cur and y != "2011-12":
            stage = latest_stage(cur[y])
            node, series = cur[y][stage], "2011-12"
        else:
            stage, node, series = "BACK", back[y]["BACK"], "2011-12-back"
        gdp = node.get("gdp", {})
        row = {"year": y, "series": series, "stage": stage, "gdp": gdp}
        g = node.get("growth", {}).get("gdp")
        if g:
            row["growth"] = {**g, "published": True}
        elif prev and "con" in gdp and "con" in prev.get("gdp", {}):
            row["growth"] = {
                "real": round((gdp["con"] / prev["gdp"]["con"] - 1) * 100, 1),
                "nominal": round((gdp["cur"] / prev["gdp"]["cur"] - 1) * 100, 1) if "cur" in gdp and "cur" in prev["gdp"] else None,
                "published": False,
            }
        out.append(row)
        prev = row
    return out


def main() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    rows, problems = load_rows(manifest)
    rows, dup_notes = dedupe(rows)
    rows.sort(key=lambda r: (r["series"], r["frequency"], r["year"], r["quarter"], r["indicator_code"],
                             STAGE_ORDER.get(r["stage"], 99), r["industry"], r["subindustry"], r["sector"]))
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "national_accounts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tree = arrange(rows)
    assumptions = [a for s in BUDGETS if (a := budget.assumption(s, manifest))]
    dataset = {
        "description": "India's GDP and national accounts from MoSPI, with the Union Budget's GDP assumption and published forecasts.",
        "units": "₹ crore for levels; % for growth rates. 'cur' = current prices (nominal), 'con' = constant prices of the base year (real).",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "series": {
            "2011-12": "Base year 2011-12, released January 2015 and replaced in February 2026. Annual figures at every estimate stage.",
            "2011-12-back": "1950-51 to 2011-12 recomputed on the 2011-12 base by MoSPI (one estimate per year).",
            "2022-23": "Base year 2022-23, released 27 February 2026. MoSPI's API keeps the latest estimate per year only.",
        },
        "stages": [{"id": sid, "as_printed": label, "label": short, "when": when} for sid, label, short, when in STAGES]
        + [{"id": "BACK", "as_printed": "", "label": "Back series", "when": "recomputed on the 2011-12 base"},
           {"id": "LATEST", "as_printed": "", "label": "Latest estimate", "when": "quarterly figures: latest estimate only"}],
        "indicators": {v[0]: v[1] for v in INDICATORS.values()},
        "industries": INDUSTRY_LABELS,
        "broad_industries": BROAD,
        "industry_groups": GROUPS,
        "sectors": SECTOR_LABELS,
        "data": tree,
        "long_run": long_run(tree),
        "budget_assumptions": assumptions,
        "forecasts": forecasts.build(manifest),
        "source_problems": problems,
        "duplicate_rows": dup_notes,
    }
    (DATA / "gdp.json").write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n")
    print(f"national_accounts.csv: {len(rows)} rows; gdp.json written; {len(problems)} problems, {len(dup_notes)} duplicate notes")
    return dataset


if __name__ == "__main__":
    main()

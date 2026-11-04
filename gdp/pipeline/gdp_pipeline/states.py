"""State accounts: gross and net state domestic product (GSDP, NSDP), income per person, growth, and value added by
industry, for each state and union territory, from MoSPI's national accounts API (indicator codes 23-34).

Outputs (in gdp/data/):
- state_accounts.csv : every row MoSPI published, one line per value, as printed, with our ids and the source URL.
- states.json        : the same figures arranged for the site (base -> state -> year), in ₹ crore for levels.

What MoSPI publishes, and what is done with it:
- Annual figures, latest estimate only, on the 2011-12 base. There is no All-India row (compare with national GDP).
- Value added by industry, taxes and subsidies on products are labelled ₹ lakh and are divided by 100 to give
  ₹ crore (they then add up to the GSDP published in ₹ crore: see the checks).
- The GSDP table leaves out a few states (Assam, Haryana, Ladakh, Nagaland) that the value-added table covers. For
  them GSDP is worked out by MoSPI's own definition, GSVA + taxes on products - subsidies on products, and marked
  "derived"; their growth is then worked out from those levels. Where MoSPI publishes GSDP, it equals that sum.
- A net figure (net value added, NSDP, NSDP per person) can never reach the gross one, because depreciation is
  positive. A net figure that does is a copying error at the source: it is left out, and listed in the report.

The checks are in states_checks.py.
"""

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .ids import INDUSTRY_LABELS, number, slug
from .sources import STATE_INDICATORS, STATE_SERIES

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "manifest.json"

# code -> (id, unit MoSPI prints, divide by this to get the unit we store)
INDICATORS = {
    23: ("gsdp", "₹ Crore", 1),
    24: ("nsdp", "₹ Crore", 1),
    25: ("pc_nsdp", "₹", 1),
    26: ("gsdp_growth", "%", 1),
    27: ("nsdp_growth", "%", 1),
    28: ("pc_nsdp_growth", "%", 1),
    29: ("gsva", "₹ Lakh", 100),
    30: ("nsva", "₹ Lakh", 100),
    31: ("pc_gsdp", "Rs.", 1),
    32: ("pc_nsdp_alt", "Rs.", 1),  # a second table of NSDP per person, covering more states
    33: ("taxes", "₹ Lakh", 100),
    34: ("subsidies", "₹ Lakh", 100),
}
LABELS = {
    "gsdp": "Gross state domestic product (GSDP)",
    "nsdp": "Net state domestic product (NSDP)",
    "pc_nsdp": "NSDP per person (income per person)",
    "pc_nsdp_alt": "NSDP per person (second table)",
    "pc_gsdp": "GSDP per person",
    "gsdp_growth": "GSDP growth rate",
    "nsdp_growth": "NSDP growth rate",
    "pc_nsdp_growth": "Growth of NSDP per person",
    "gsva": "Gross state value added (GSVA)",
    "nsva": "Net state value added (NSVA)",
    "taxes": "Taxes on products",
    "subsidies": "Subsidies on products",
}
GROWTH = {"gsdp_growth": "gsdp", "nsdp_growth": "nsdp", "pc_nsdp_growth": "pc_nsdp"}

INDUSTRIES = {
    "Agriculture, Livestock, Forestry and Fishing": "agriculture",
    "Mining and Quarrying": "mining",
    "Manufacturing": "manufacturing",
    "Electricity, Gas, Water Supply & Other Utility Services": "utilities",
    "Construction": "construction",
    "Trade, Repair, Hotels and Restaurants": "trade_hotels",
    "Transport, Storage, Communication & Services Related to Broadcasting": "transport_comm",
    "Financial Services": "financial",
    "Real Estate, Ownership of Dwelling & Professional Services": "real_estate",
    "Public Administration": "public_admin",
    "Other Services": "other_services",
    "Total Gross State Value Added": "total",  # MoSPI uses this label for the net table's total too
}
# The three broad sectors, from MoSPI's eleven industries.
SECTORS = {
    "agriculture": ["agriculture"],
    "industry": ["mining", "manufacturing", "utilities", "construction"],
    "services": ["trade_hotels", "transport_comm", "financial", "real_estate", "public_admin", "other_services"],
}
SECTOR_LABELS = {"agriculture": "Agriculture", "industry": "Industry", "services": "Services"}

# States that publish no subsidies on products at all: their GSDP is value added plus taxes.
NO_SUBSIDIES = {"Chhattisgarh"}
SITE_BASE = "2011-12"  # the base the site shows (STATE_BASE in site/src/lib/gdp/states.ts)
# Every state and union territory in MoSPI's state accounts. A new or renamed one fails the checks until it is added
# here (and, if renamed, its old rows are looked at); one that disappears fails too.
KNOWN_STATES = [
    "Andaman & Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
    "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala",
    "Ladakh", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]


def prev_year(y: str) -> str:
    start = int(y[:4]) - 1
    return f"{start}-{str(start + 1)[-2:]}"


def load(manifest: dict) -> tuple[list[dict], list[str]]:
    """Every published row with ids attached. Returns (rows, problems)."""
    rows: list[dict] = []
    problems: list[str] = []
    seen: dict[tuple, tuple] = {}
    for base, series, freq in STATE_SERIES:
        for code in STATE_INDICATORS:
            key = f"nas/{base}/{series}/{freq}/ind{code:02d}"
            entry = manifest.get(key)
            if not entry or entry.get("empty"):
                continue
            ind, unit, _ = INDICATORS[code]
            for r in json.loads((ROOT / entry["file"]).read_text())["rows"]:
                if not re.fullmatch(r"\d{4}-\d{2}", str(r.get("year"))) or not r.get("state"):
                    problems.append(f"{key}: row with year {r.get('year')!r}, state {r.get('state')!r} not understood")
                    continue
                if r.get("unit") != unit:
                    problems.append(f"{key}: unit {r.get('unit')!r}, expected {unit!r} ({r['state']}, {r['year']})")
                    continue
                industry = r.get("industry") or ""
                if ind in ("gsva", "nsva") and industry not in INDUSTRIES:
                    problems.append(f"{key}: unknown industry {industry!r}")
                    continue
                if r["state"] not in KNOWN_STATES:
                    problems.append(f"{key}: unknown state or union territory {r['state']!r} (add it to KNOWN_STATES "
                                    "once it is checked; if it is a renamed one, see that its old rows still join up)")
                    continue
                k = (base, r["state"], r["year"], code, industry, r.get("subindustry") or "")
                v = (r.get("current_price"), r.get("constant_price"))
                if k in seen:
                    if seen[k] != v:
                        problems.append(f"{key}: {r['state']}, {r['year']} {industry} {r.get('subindustry') or ''} "
                                        f"published twice with different values ({seen[k]} and {v})")
                    continue
                seen[k] = v
                rows.append({
                    "base_year": base,
                    "state": r["state"],
                    "year": r["year"],
                    "indicator_code": code,
                    "indicator": ind,
                    "indicator_as_printed": r.get("indicator") or "",
                    "industry": INDUSTRIES.get(industry, ""),
                    "industry_as_printed": industry,
                    "subindustry": slug(r["subindustry"]) if r.get("subindustry") else "",
                    "subindustry_as_printed": r.get("subindustry") or "",
                    "current_price": number(r.get("current_price")),
                    "constant_price": number(r.get("constant_price")),
                    "unit": r.get("unit"),
                    "left_out": "",
                    "source_url": entry["url"],
                    "source_sha256": entry["sha256"],
                })
    # Every state must be in the series the site shows. A newer base is expected to fill up state by state; check_rows
    # lists the states not on it yet.
    present = {r["state"] for r in rows if r["base_year"] == SITE_BASE}
    if present:
        problems += [f"{SITE_BASE} base: no rows at all for {s}" for s in KNOWN_STATES if s not in present]
    return rows, problems


def pair(r: dict) -> dict:
    div = INDICATORS[r["indicator_code"]][2]
    out = {}
    if r["current_price"] is not None:
        out["cur"] = round(r["current_price"] / div, 2)
    if r["constant_price"] is not None:
        out["con"] = round(r["constant_price"] / div, 2)
    return out


def arrange(rows: list[dict]) -> tuple[dict, list[str]]:
    """base -> state -> year -> figures. Leaves out impossible net figures and works out GSDP where MoSPI's GSDP table
    leaves a state out. Returns (tree, notes on what was left out)."""
    tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for r in rows:
        node = tree[r["base_year"]][r["state"]][r["year"]]
        p = pair(r)
        if not p:
            continue
        ind = r["indicator"]
        if ind in GROWTH:
            g = {}
            if "con" in p:
                g["real"] = p["con"]
            if "cur" in p:
                g["nominal"] = p["cur"]
            node.setdefault("growth", {})[GROWTH[ind]] = g
        elif ind in ("gsva", "nsva"):
            if r["subindustry"]:
                node.setdefault(f"{ind}_sub", {}).setdefault(r["industry"], {})[r["subindustry"]] = p
            else:
                node.setdefault(ind, {})[r["industry"]] = p
        else:
            node[ind] = p
    notes = leave_out_impossible_net(tree, rows)
    derive_gsdp(tree)
    return json.loads(json.dumps(tree)), notes


def leave_out_impossible_net(tree: dict, rows: list[dict]) -> list[str]:
    """Net figures that are not below the gross figure are copying errors at the source: removed from the tree and
    marked left_out in rows. Returns one note per state, figure and base."""
    dropped: dict[tuple, list[str]] = defaultdict(list)
    for base, states in tree.items():
        for state, years in states.items():
            for year, node in years.items():
                for net, gross, what in (
                    ("nsva", "gsva", "net state value added (ind30)"),
                    ("nsdp", "gsdp", "NSDP (ind24)"),
                    ("pc_nsdp", "pc_gsdp", "NSDP per person (ind25)"),
                    ("pc_nsdp_alt", "pc_gsdp", "NSDP per person (second table, ind32)"),
                ):
                    n = node.get(net, {}).get("total") if net == "nsva" else node.get(net)
                    g = node.get(gross, {}).get("total") if gross == "gsva" else node.get(gross)
                    if n and g and any(k in n and k in g and n[k] >= g[k] for k in ("cur", "con")):
                        node.pop(net)
                        if net == "nsva":
                            node.pop("nsva_sub", None)
                        dropped[(base, state, what, net)].append(year)
    notes = []
    for (base, state, what, net), years in sorted(dropped.items()):
        years.sort()
        span = years[0] if len(years) == 1 else f"{years[0]} to {years[-1]} ({len(years)} years)"
        notes.append(f"{state}: {what} is not below the gross figure, {span}, {base} base; left out")
        code = {"nsva": 30, "nsdp": 24, "pc_nsdp": 25, "pc_nsdp_alt": 32}[net]
        for r in rows:
            if r["base_year"] == base and r["state"] == state and r["indicator_code"] == code and r["year"] in years:
                r["left_out"] = "net figure not below the gross figure (source error)"
    return notes


def derive_gsdp(tree: dict) -> None:
    """GSDP where MoSPI's GSDP table leaves the state out: GSVA + taxes - subsidies, and growth from those levels."""
    for states in tree.values():
        for state, years in states.items():
            for year, node in years.items():
                total, taxes = node.get("gsva", {}).get("total"), node.get("taxes")
                subs = node.get("subsidies") or ({"cur": 0, "con": 0} if state in NO_SUBSIDIES else None)
                if "gsdp" in node or not (total and taxes and subs):
                    continue
                gsdp = {k: round(total[k] + taxes[k] - subs[k], 2) for k in ("cur", "con") if k in total and k in taxes and k in subs}
                if gsdp:
                    node["gsdp"] = {**gsdp, "derived": True}
            for year, node in years.items():
                g, before = node.get("gsdp"), years.get(prev_year(year), {}).get("gsdp")
                if not g or not g.get("derived") or not before or "growth" in node and "gsdp" in node["growth"]:
                    continue
                growth = {}
                if "con" in g and before.get("con"):
                    growth["real"] = round((g["con"] / before["con"] - 1) * 100, 1)
                if "cur" in g and before.get("cur"):
                    growth["nominal"] = round((g["cur"] / before["cur"] - 1) * 100, 1)
                if growth:
                    node.setdefault("growth", {})["gsdp"] = {**growth, "published": False}


def build(manifest: dict) -> dict:
    rows, problems = load(manifest)
    tree, left_out = arrange(rows)
    write_csv(rows, DATA / "state_accounts.csv")
    dataset = {
        "description": "State accounts from MoSPI: gross and net state domestic product, income per person, growth "
                       "and value added by industry, for each state and union territory.",
        "units": "₹ crore for levels (value added, taxes and subsidies converted from ₹ lakh); ₹ for per-person "
                 "figures; % for growth. 'cur' = current prices, 'con' = constant 2011-12 prices. 'derived': worked "
                 "out as GSVA + taxes - subsidies (MoSPI publishes no GSDP for the state); growth with "
                 "'published': false is worked out from the levels.",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bases": sorted(tree),
        "indicators": LABELS,
        "industries": {k: INDUSTRY_LABELS[k] for k in dict.fromkeys(INDUSTRIES.values())},
        "sectors": SECTORS,
        "sector_labels": SECTOR_LABELS,
        "data": tree,
        "source_problems": problems,
        "left_out": left_out,
    }
    (DATA / "states.json").write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n")
    print(f"state_accounts.csv: {len(rows)} rows; states.json written; {len(problems)} problems, {len(left_out)} left out")
    return dataset


def write_csv(rows: list[dict], path: Path) -> None:
    """state_accounts.csv: every row, sorted by base, state, year, indicator, industry and sub-industry."""
    rows.sort(key=lambda r: (r["base_year"], r["state"], r["year"], r["indicator_code"], r["industry"], r["subindustry"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

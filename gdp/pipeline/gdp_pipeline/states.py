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

Checks (added to gdp/data/validation_report.md by check()):
1. Every row is understood (year, state, industry, unit); anything left out is a known, explained source error.
2. GSDP = GSVA + taxes - subsidies, and NSDP = NSVA + taxes - subsidies, for every state, year and price basis.
3. Industries add up to total value added; sub-industries add up to their industry.
4. Every published growth rate is reproduced from the published levels.
5. The two tables of NSDP per person agree, and per-person GSDP and NSDP imply the same population.
6. For review, not failures: the states' GSDP against India's GDP (2011-12 base) in each year most states report.
Also: every state is a known one with rows in every table's base, no row is published twice with different values,
and a derived GSDP implies a population that moves smoothly with MoSPI's GSDP per person.
"""

import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .build import INDUSTRY_LABELS, slug
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

LEVEL_TOL = 2  # ₹ crore: GSDP is printed to the crore and its parts to the lakh
GROWTH_TOL = 0.05  # growth rates are printed to one decimal ...
LEVEL_ROUNDING = 0.5  # ... and worked out from levels printed to the crore (or rupee), which matters for small states
PER_PERSON_TOL = 1  # ₹
POPULATION_TOL = 0.0005  # per-person GSDP and NSDP are rounded to the rupee
DERIVED_POPULATION_STEP = 0.03  # a derived state's implied population moves less than this a year (catches unit slips)
# For review only: states' GSDP / India's GDP usually sits in this band. The states are compiled separately and keep
# being revised, while the national 2011-12 series stopped in February 2026, so this is not a hard check.
SUM_BAND = (0.95, 1.06)
COVERAGE = 0.97  # a year is compared once the states reporting it made up this share of all states' GSDP the year before
FINAL_ENOUGH = "PE"  # ... and India's figure for it is at least a provisional estimate

# Every state and union territory in MoSPI's state accounts. A new or renamed one fails the checks until it is added
# here (and, if renamed, its old rows are looked at); one that disappears fails too.
KNOWN_STATES = [
    "Andaman & Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chandigarh", "Chhattisgarh",
    "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala",
    "Ladakh", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry",
    "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
]

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


def number(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", ""))
    except ValueError:
        return None
    return None if math.isnan(x) else x


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
    for base in sorted({r["base_year"] for r in rows}):
        present = {r["state"] for r in rows if r["base_year"] == base}
        problems += [f"{base} base: no rows at all for {s}" for s in KNOWN_STATES if s not in present]
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
    """base -> state -> year -> figures. Leaves out impossible net figures. Returns (tree, notes on what was left out)."""
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

    # Net figures that are not below the gross figure: copying errors at the source.
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

    # GSDP where MoSPI's GSDP table leaves the state out: GSVA + taxes - subsidies, and growth from those levels.
    for states in tree.values():
        for years in states.values():
            for year, node in years.items():
                total, taxes, subs = node.get("gsva", {}).get("total"), node.get("taxes"), node.get("subsidies")
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
    return json.loads(json.dumps(tree)), notes


def build(manifest: dict) -> dict:
    rows, problems = load(manifest)
    tree, left_out = arrange(rows)
    rows.sort(key=lambda r: (r["base_year"], r["state"], r["year"], r["indicator_code"], r["industry"], r["subindustry"]))
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "state_accounts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
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


# ---------------------------------------------------------------------------------------------- checks


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
    other = [b for b in st["bases"] if b != "2011-12"]
    if other:
        notes.append(f"MoSPI now publishes state accounts on the {', '.join(other)} base. The site still shows the "
                     "2011-12 base: switch it over (site/src/lib/gdp/states.ts).")
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
    from .build import STAGE_ORDER

    notes = []
    annual = ds["data"].get("2011-12", {}).get("annual", {})
    states = st["data"].get("2011-12", {})
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


def check(ds: dict, report) -> None:
    st = json.loads((DATA / "states.json").read_text())
    check_rows(st, report)
    check_identities(st, report)
    check_industries(st, report)
    check_growth(st, report)
    check_per_person(st, report)
    check_sum(st, ds, report)
    unused = [f"{c}: {k}" for c, k in KNOWN_EXCEPTIONS if (c, k) not in USED]
    if unused:
        report.add("State accounts: known exceptions no longer needed (for review: remove them)", 0, [], unused)

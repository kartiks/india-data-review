"""Turn the downloaded files into the site's datasets.

Outputs (in gdp/data/):
- national_accounts.csv : every row MoSPI published, one line per value, with
                          names as printed, our ids, and the source URL.
- gdp.json              : the same figures arranged for the site (by series,
                          year and estimate stage), plus the Budget's GDP
                          assumptions and the forecasts.
- per_person.csv        : GDP, national income and household spending per
                          person, with the population used (see population.py).
- state_accounts.csv, states.json : the state accounts (see states.py).

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
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import budget, forecasts, population, states
from .ids import (BROAD, GROUPS, INDICATORS, INDUSTRIES, INDUSTRY_LABELS, SECTOR_LABELS, SECTORS, STAGE_BY_LABEL,
                  STAGE_ORDER, STAGES, latest_stage, number, slug)
from .sources import BUDGETS, NAS_INDICATORS, NAS_SERIES

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "manifest.json"


def series_key(base: str, series: str) -> str:
    return base if series == "Current" else f"{base}-back"


def versions(entry: dict) -> list[dict]:
    """The file a manifest entry points to, then each earlier version of it kept in sources/snapshots/ (the entry's
    history), newest first: {file, sha256, fetched_at}.

    An estimate MoSPI later withdraws is still read back from a snapshot. If that ever happens, remove the
    snapshot's entry from the history in sources/manifest.json (and its file) rather than keep it."""
    current = {"file": entry["file"], "sha256": entry["sha256"], "fetched_at": entry.get("fetched_at")}
    earlier = [{k: h.get(k) for k in ("file", "sha256", "fetched_at")} for h in reversed(entry.get("history", []))]
    return [current] + earlier


def read_row(r: dict, key: str, base: str, series: str, freq: str, code: int, url: str,
             sha: str) -> tuple[dict | None, list[str]]:
    """One API row with our ids attached, or None if it cannot be used; and the problems found in it."""
    if not re.fullmatch(r"\d{4}-(\d{2}|2000)", str(r.get("year"))):
        return None, [f"{key}: row with year {r.get('year')!r} left out (not a fiscal year): {r.get('indicator')} "
                      f"{r.get('revision')} {r.get('current_price')}"]
    stage_label = r.get("revision")
    stage = STAGE_BY_LABEL.get(stage_label) if stage_label else ("BACK" if series == "Back" else "LATEST")
    if stage is None:
        return None, [f"{key}: unknown estimate stage {stage_label!r}"]
    problems = []
    industry = r.get("industry")
    sector = r.get("institutional_sector")
    ind = INDUSTRIES.get(industry) if industry else None
    if industry and ind is None:
        problems.append(f"{key}: unknown industry {industry!r}")
    sec = SECTORS.get(sector) if sector else None
    if sector and sec is None:
        problems.append(f"{key}: unknown institutional sector {sector!r}")
    return {
        "series": series_key(base, series),
        "base_year": base,
        "frequency": "annual" if freq == "Annually" else "quarterly",
        "year": r["year"],
        "quarter": r.get("quarter") or "",
        "indicator_code": code,
        "indicator": INDICATORS[code][0],
        "indicator_as_printed": r.get("indicator"),
        "stage": stage,
        "stage_as_printed": stage_label or "",
        "industry": ind or "",
        "industry_as_printed": industry or "",
        "subindustry": slug(r["subindustry"]) if r.get("subindustry") else "",
        "subindustry_as_printed": r.get("subindustry") or "",
        "sector": sec or "",
        "sector_as_printed": sector or "",
        "current_price": number(r.get("current_price")),
        "constant_price": number(r.get("constant_price")),
        "unit": r.get("unit") or "",
        "source_url": url,
        "source_sha256": sha,
    }, problems


def load_rows(manifest: dict) -> tuple[list[dict], list[str], list[dict]]:
    """Every published row with ids attached. Returns (rows, problems, earlier): earlier lists the estimates read from
    an earlier version of a file.

    MoSPI's API keeps only the latest estimate of each year in the 2022-23 series: when a year moves from the
    Provisional to the First Revised Estimate, its Provisional Estimate is gone from the API. fetch.py keeps every
    replaced file in sources/snapshots/ (the manifest entry's history), so an official estimate (year, quarter and
    stage) that the current file no longer has is read from the newest earlier version that has it. Where versions
    share an estimate, the newest wins. Rows without a stage of their own (the quarters' and the back series' latest
    figures) come from the current file only. Each row's source_sha256 is that of the version it was read from."""
    out: list[dict] = []
    problems: list[str] = []
    earlier: dict[tuple, set[str]] = {}
    for base, series, freq in NAS_SERIES:
        for code in NAS_INDICATORS:
            key = f"nas/{base}/{series}/{freq}/ind{code:02d}"
            entry = manifest.get(key)
            if not entry or entry.get("empty"):
                continue
            have: set[tuple] = set()  # (year, quarter, stage as printed) already read from a newer version
            for n, version in enumerate(versions(entry)):
                found = set()
                if not version["file"] or not (ROOT / version["file"]).exists():
                    raise FileNotFoundError(f"{key}: version {version['sha256']} of {version['fetched_at']} is "
                                            f"listed in sources/manifest.json but its file {version['file']!r} is missing")
                for r in json.loads((ROOT / version["file"]).read_text())["rows"]:
                    estimate = (r.get("year"), r.get("quarter") or "", r.get("revision"))
                    if n and (r.get("revision") not in STAGE_BY_LABEL or estimate in have):
                        continue
                    row, why = read_row(r, key, base, series, freq, code, entry["url"], version["sha256"])
                    problems += why
                    if row is None:
                        continue
                    out.append(row)
                    found.add(estimate)
                    if n:
                        k = (row["series"], row["frequency"], row["year"], row["quarter"], row["stage"],
                             (version["fetched_at"] or "")[:10])
                        earlier.setdefault(k, set()).add(row["indicator"])
                have |= found
    earlier_list = [{"series": s, "frequency": f, "year": y, "quarter": q, "stage": st, "fetched_on": at,
                     "indicators": sorted(inds)} for (s, f, y, q, st, at), inds in sorted(earlier.items())]
    return out, list(dict.fromkeys(problems)), earlier_list


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
            # Sub-industry rates share the industry's key; keep only the industry's own rate.
            if not r["subindustry"]:
                node.setdefault("gva_growth", {})[r["industry"] or "total"] = growth_pair(r)
        elif ind == "gva":
            if r["sector"] and r["sector"] != "total" and not r["industry"]:
                continue  # GVA by institutional sector: kept in national_accounts.csv, not in the tree
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
    rows, problems, earlier = load_rows(manifest)
    rows, dup_notes = dedupe(rows)
    rows.sort(key=lambda r: (r["series"], r["frequency"], r["year"], r["quarter"], r["indicator_code"],
                             STAGE_ORDER.get(r["stage"], 99), r["industry"], r["subindustry"], r["sector"]))
    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "national_accounts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    tree = arrange(rows)
    pop = population.build(manifest, tree)  # adds per_person to every estimate with a population
    assumptions = [a for s in BUDGETS if (a := budget.assumption(s, manifest))]
    dataset = {
        "description": "India's GDP and national accounts from MoSPI, with the Union Budget's GDP assumption and published forecasts.",
        "units": "₹ crore for levels; % for growth rates. 'cur' = current prices (nominal), 'con' = constant prices of the base year (real).",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "series": {
            "2011-12": "Base year 2011-12, released January 2015 and replaced in February 2026. Annual figures at every estimate stage.",
            "2011-12-back": "1950-51 to 2011-12 recomputed on the 2011-12 base by MoSPI (one estimate per year).",
            "2022-23": "Base year 2022-23, released 27 February 2026. MoSPI's API keeps the latest estimate per year only; "
                       "earlier estimates come from the downloads this site saved before each revision (earlier_releases).",
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
        "population": pop,
        "long_run": long_run(tree),
        "budget_assumptions": assumptions,
        "forecasts": forecasts.build(manifest),
        "source_problems": problems,
        "duplicate_rows": dup_notes,
        "earlier_releases": earlier,
    }
    n = population.write_csv(tree, pop["by_series"], DATA / "per_person.csv")
    print(f"per_person.csv: {n} rows")
    (DATA / "gdp.json").write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n")
    print(f"national_accounts.csv: {len(rows)} rows; gdp.json written; {len(problems)} problems, {len(dup_notes)} duplicate notes")

    states.build(manifest)
    return dataset


if __name__ == "__main__":
    main()

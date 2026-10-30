"""Turn the downloaded files into the site's datasets.

Outputs (in jobs-prices/data/):
- plfs_rates.csv       participation, worker ratio and unemployment, one line per published combination
- plfs_workers.csv     distribution of workers (type of work, industry, employer, occupation)
- plfs_conditions.csv  regular employees without a written contract, paid leave or social security
- plfs_earnings.csv    average earnings (regular wage, casual wage, self-employment)
- cpi.csv, cpialrl.csv consumer price indices and inflation
- hces.csv             household spending
- sources.csv          every downloaded file: key, URL, SHA-256, date (each CSV row names its source key)
- jobs_prices.json     what the site uses, in compact form

Every CSV keeps MoSPI's values and names as printed. Nothing here changes a
published number.

Run: uv run python -m jobs_prices_pipeline.build
"""

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .sources import queries

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "manifest.json"

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
MONTH_NO = {m: i + 1 for i, m in enumerate(MONTHS)}
QUARTERS = {"Jan-Mar": 1, "Apr-Jun": 2, "Jul-Sep": 3, "Oct-Dec": 4}

# PLFS fields -> our names. Any other field is a breakdown (industry, type of work ...).
PLFS_FIELDS = {
    "year": "year", "year_type": "year_type", "quarter": "quarter", "month": "month", "state": "state",
    "sector": "sector", "gender": "gender", "AgeGroup": "age", "weekly_status": "status", "religion": "religion",
    "socialGroup": "social_group", "General_Education": "education",
}
PLFS_SKIP = {"frequency", "indicator", "value", "unit"}
RATES = {1: "lfpr", 2: "wpr", 3: "ur"}
EARNINGS = {6: "regular", 7: "casual", 8: "self"}
RATE_DIMS = ["year", "period", "state", "sector", "gender", "age", "status", "religion", "social_group", "education"]
# Breakdowns of workers the site shows for every state; the others for All India only.
STATE_BREAKDOWNS = {"broad_status_employment", "broad_industry_work"}


def number(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(str(v).replace(",", ""))
    except ValueError:
        return None
    return None if math.isnan(x) else x


def load(manifest: dict, prefix: str) -> list[tuple[str, dict, dict]]:
    """(key, manifest entry, file body) for every downloaded file under a prefix."""
    out = []
    for key, _, _ in queries():
        if not key.startswith(prefix):
            continue
        entry = manifest.get(key)
        if not entry or entry.get("empty"):
            continue
        out.append((key, entry, json.loads((ROOT / entry["file"]).read_text())))
    return out


def write_csv(name: str, fields: list[str], rows: list[dict]) -> None:
    """'..._as_printed' columns are filled only where MoSPI's text is not simply the number (e.g. 'NaN', 'l0.8')."""
    with open(DATA / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = {k: ("" if r.get(k) is None else r.get(k)) for k in fields}
            for k in fields:
                if k.endswith("_as_printed"):
                    v = r.get(k.removesuffix("_as_printed"))
                    if v is not None and number(out[k]) == v:
                        out[k] = ""
            w.writerow(out)


def period(r: dict) -> str:
    """'' for a year, 'Q2' (Apr-Jun) for a quarter, '07' for a month."""
    if r.get("month"):
        return f"{MONTH_NO[r['month']]:02d}"
    if r.get("quarter") and r["quarter"] != "all":
        return f"Q{QUARTERS[r['quarter']]}"
    return ""


def cell_text(dims: dict) -> str:
    return ", ".join(str(dims[k]) for k in ("year", "period", "state", "sector", "gender", "status") if dims.get(k))


# ---- PLFS ---------------------------------------------------------------------------------------

def plfs(manifest: dict, problems: list[str]) -> dict:
    rates: dict[str, dict[tuple, dict]] = defaultdict(dict)  # frequency -> dims -> {lfpr, wpr, ur}
    other: dict[str, list[dict]] = defaultdict(list)  # "distribution" | "conditions" | "earnings"
    unlabelled: list[str] = []
    labels: dict[int, str] = {}
    for key, entry, body in load(manifest, "plfs/"):
        freq = key.split("/")[1]
        code = body["query"]["indicator_code"]
        for r in body["rows"]:
            labels[code] = r["indicator"]
            v = number(r.get("value"))
            dims = {ours: r.get(api) or "" for api, ours in PLFS_FIELDS.items()}
            dims["period"] = period(r)
            extra = {k: val for k, val in r.items() if k not in PLFS_FIELDS and k not in PLFS_SKIP and val not in (None, "")}
            if code in RATES:
                k = tuple(dims[d] for d in RATE_DIMS)
                rec = rates[freq].setdefault(k, {"year_type": dims["year_type"], "source": []})
                name = RATES[code]
                if name in rec and rec[name] != v:
                    problems.append(f"{key}: {dict(zip(RATE_DIMS, k))} published twice ({rec[name]} and {v})")
                rec[name] = v
                rec[name + "_raw"] = r.get("value")
                rec["source"].append(key)
                continue
            kind = "earnings" if code in EARNINGS else "distribution" if code == 4 else "conditions"
            rec = {"frequency": freq, **{d: dims[d] for d in ("year", "year_type", "period", "state", "sector",
                                                                 "gender", "age", "status")},
                   "value": v, "value_as_printed": r.get("value"), "unit": r.get("unit") or "", "source": key}
            if code in EARNINGS:
                rec["kind"] = EARNINGS[code]
                rec["indicator"] = r["indicator"]
            elif code == 5:
                rec["indicator"] = r["indicator"]
                rec["condition"] = r.get("employee_contract") or ""
            else:
                # One breakdown per row (type of work, broad industry, industry section, employer, occupation).
                if len(extra) != 1:
                    unlabelled.append(f"{key}: {cell_text(dims)} value {r.get('value')}")
                    continue
                (field, category), = extra.items()
                rec["breakdown"], rec["category"] = field, category
            other[kind].append(rec)
    rate_rows = []
    for freq, recs in rates.items():
        for k, rec in sorted(recs.items()):
            rate_rows.append({"frequency": freq, "year_type": rec["year_type"], **dict(zip(RATE_DIMS, k)),
                              "lfpr": rec.get("lfpr"), "wpr": rec.get("wpr"), "ur": rec.get("ur"),
                              "lfpr_as_printed": rec.get("lfpr_raw"), "wpr_as_printed": rec.get("wpr_raw"),
                              "ur_as_printed": rec.get("ur_raw"), "left_out": "", "source": " ".join(rec["source"])})
    flag_rates(rate_rows)
    return {"indicators": {str(c): labels[c] for c in sorted(labels)}, "rates": rate_rows,
            "distribution": other["distribution"], "conditions": other["conditions"], "earnings": other["earnings"],
            "unlabelled": unlabelled}


SMALL_GAP = 0.3  # points: a worker ratio further than this from participation × (1 − unemployment) is wrong
# How MoSPI marks "no figure": NaN, a dash, or ** (too few people in the sample to publish)
MISSING = ("NaN", "nan", "-", "**", None, "")


def identity_gap(r: dict) -> tuple[float, float]:
    """(gap, rounding tolerance) between the published worker ratio and participation × (1 − unemployment)."""
    l, w, u = r["lfpr"], r["wpr"], r["ur"]
    expected = l * (1 - u / 100)
    return abs(expected - w), 0.05 + 0.05 * (1 - u / 100) + l * 0.0005 + 1e-9  # each figure is rounded to 0.1


def flag_rates(rows: list[dict]) -> None:
    """Mark the combinations the site must not show, with the reason (kept in plfs_rates.csv).

    MoSPI's PLFS figures, especially the quarterly ones, carry transcription errors: letters for digits
    ('l0.8', 'IN.4') and numbers that cannot all be right. The three rates are tied by an identity, and a
    total lies between its parts; a combination that breaks either is left out whole, since which of its
    figures is wrong cannot be told.
    """
    for r in rows:
        bad = [f"{k} printed as {r[k + '_as_printed']!r}" for k in ("lfpr", "wpr", "ur")
               if r[k] is None and r[k + "_as_printed"] not in MISSING]
        if bad:
            r["left_out"] = "not a number: " + "; ".join(bad)
        elif None not in (r["lfpr"], r["wpr"], r["ur"]):
            gap, _ = identity_gap(r)
            if gap > SMALL_GAP:
                r["left_out"] = (f"inconsistent: participation {r['lfpr']} and unemployment {r['ur']} give a worker ratio of "
                                 f"{r['lfpr'] * (1 - r['ur'] / 100):.1f}, published {r['wpr']}")
    idx = {tuple(r[k] for k in ["frequency"] + RATE_DIMS): r for r in rows}
    for field, total, parts in (("gender", "person", ("male", "female")), ("sector", "rural + urban", ("rural", "urban"))):
        i = (["frequency"] + RATE_DIMS).index(field)
        for k, r in idx.items():
            if k[i] != total:
                continue
            ps = [idx.get(k[:i] + (p,) + k[i + 1:]) for p in parts]
            if None in ps or any(x["left_out"] for x in ps + [r]):
                continue
            for name in ("lfpr", "wpr", "ur"):
                a, b, v = ps[0][name], ps[1][name], r[name]
                if None in (a, b, v):
                    continue
                if not (min(a, b) - 0.1 <= v <= max(a, b) + 0.1):
                    why = f"inconsistent: {name} for {total} {v} is outside {parts[0]} {a} and {parts[1]} {b}"
                    for x in ps + [r]:
                        x["left_out"] = x["left_out"] or why
                    break


# ---- prices -------------------------------------------------------------------------------------

def ym(r: dict) -> str:
    """'2025-12'. Years written '2024-2025' are agricultural years (July to June), as in the Labour Bureau's CPI-AL/RL."""
    m = MONTH_NO[r["month"]]
    y = str(r["year"])
    if "-" in y:
        start = int(y[:4])
        return f"{start if m >= 7 else start + 1}-{m:02d}"
    return f"{int(y)}-{m:02d}"


def cpi(manifest: dict, problems: list[str]) -> list[dict]:
    out, seen = [], {}
    for key, entry, body in load(manifest, "cpi/"):
        file = "all_india" if key.startswith("cpi/all_india/") else "states"
        for r in body["rows"]:
            if file == "states" and r.get("subgroup") != "General-Overall":
                problems.append(f"{key}: unexpected subgroup {r.get('subgroup')!r} in the general-index file")
                continue
            rec = {"month": ym(r), "state": r["state"], "sector": r["sector"], "group": r["group"],
                   "subgroup": r["subgroup"], "index": number(r.get("index")), "inflation": number(r.get("inflation")),
                   "index_as_printed": r.get("index"), "inflation_as_printed": r.get("inflation"),
                   "status": r.get("status") or "", "base_year": r.get("baseyear"), "source": key}
            k = (rec["month"], rec["state"], rec["sector"], rec["subgroup"])
            if k in seen:
                a = seen[k]
                if (a["index"], a["inflation"]) != (rec["index"], rec["inflation"]):
                    problems.append(f"{key}: {k} published twice with different values")
                continue  # All India's general index is in both files
            seen[k] = rec
            out.append(rec)
    out.sort(key=lambda r: (r["state"] != "All India", r["state"], r["group"], r["subgroup"], r["sector"], r["month"]))
    return out


def cpialrl(manifest: dict, problems: list[str]) -> list[dict]:
    out = []
    for key, entry, body in load(manifest, "cpialrl/"):
        for r in body["rows"]:
            rec = {"month": ym(r), **{k: v for k, v in r.items() if k not in ("year", "month")}, "source": key}
            for k in ("index_al", "index_rl", "inflation_al", "inflation_rl"):
                rec[k + "_as_printed"] = r.get(k)
                rec[k] = number(r.get(k))
            for who in ("al", "rl"):
                if rec[f"index_{who}"] == 0:  # an index of 0.00 means not compiled (Delhi has no farm labourers' index)
                    rec[f"index_{who}"] = rec[f"inflation_{who}"] = None
                    rec[f"not_compiled_{who}"] = True
            out.append(rec)
    out.sort(key=lambda r: (r.get("indicator", ""), r.get("state", ""), str(r.get("group", "")), r["month"]))
    return out


# ---- household spending -------------------------------------------------------------------------

HCES_MPCE = "Average monthly per capita consumption expenditure (MPCE)"
HCES_CATEGORIES = ("Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days",
                   "Percentage Share of Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days")


def hces(manifest: dict, problems: list[str]) -> list[dict]:
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


# ---- outputs ------------------------------------------------------------------------------------

def fields_of(rows: list[dict], first: list[str]) -> list[str]:
    seen = list(first)
    for r in rows:
        for k in r:
            if k not in seen:
                seen.append(k)
    return [f for f in seen if f != "source"] + ["source"]


ALRL_FIELDS = ["month", "base_year", "state", "index_al", "index_rl", "inflation_al", "inflation_rl"]
# HCES indicators the site shows -> short ids
HCES_SITE = {
    "Average monthly per capita consumption expenditure (MPCE)": "mpce",
    "Average monthly per capita consumption expenditure (MPCE) Over 12 Fractile Classes": "classes",
    "Percentage Share of Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days": "shares",
    "Average Monthly Per Capita Consumption Expenditure (MPCE) across different Household Type": "household_type",
    "Average Monthly Per Capita Consumption Expenditure (MPCE) across different Social Group": "social_group",
    "Gini Coefficient for Per Capita Consumption Expenditure": "gini",
}
HCES_SITE_FIELDS = ["indicator", "year", "state", "sector", "imputation_type", "category", "value"]


def table(fields: list[str], rows: list[list]) -> dict:
    """Compact table: text columns store each distinct value once ('labels'), rows hold its position."""
    text = [i for i, _ in enumerate(fields) if any(isinstance(r[i], str) for r in rows)]
    labels = {fields[i]: sorted({r[i] for r in rows if r[i] is not None}) for i in text}
    pos = {fields[i]: {v: n for n, v in enumerate(labels[fields[i]])} for i in text}
    out = [[pos[fields[i]][v] if i in text and v is not None else v for i, v in enumerate(r)] for r in rows]
    return {"fields": fields, "labels": labels, "rows": out}


def site_json(ds: dict) -> dict:
    """What the site reads: compact arrays, the slices it shows."""
    p = ds["plfs"]
    rate_fields = ["frequency"] + RATE_DIMS + ["lfpr", "wpr", "ur"]
    # Usual status (PS+SS), except broad industry, which MoSPI publishes only in current weekly status (CWS).
    workers = [r for r in p["distribution"] if r["frequency"] == "annual"
               and (r["status"] == "PS+SS" or (r["breakdown"] == "broad_industry_work" and r["status"] == "CWS"))
               and r["category"].lower() != "all"
               and (r["breakdown"] in STATE_BREAKDOWNS or r["state"] == "All India")
               # MoSPI's All-India shares by type of work do not add up (see the checks); states only
               and not (r["breakdown"] == "broad_status_employment" and r["state"] == "All India")]
    wf = ["year", "state", "sector", "gender", "status", "breakdown", "category", "value"]
    cf = ["year", "state", "sector", "gender", "condition", "value"]
    ef = ["year", "state", "sector", "gender", "kind", "value"]
    cpi_all: dict = defaultdict(lambda: defaultdict(list))
    cpi_states: dict = defaultdict(lambda: defaultdict(list))
    for r in ds["cpi"]:
        point = [r["month"], r["index"], r["inflation"]]
        if r["state"] == "All India":
            cpi_all[f"{r['group']}|{r['subgroup']}"][r["sector"]].append(point)
        if r["subgroup"] == "General-Overall":
            cpi_states[r["state"]][r["sector"]].append(point)
    return {
        "description": ds["description"],
        "generated_at": ds["generated_at"],
        "sources": ds["sources"],
        "plfs": {
            "indicators": p["indicators"],
            "rates": table(rate_fields, [[r[f] for f in rate_fields] for r in p["rates"] if not r["left_out"]]),
            "workers": table(wf, [[r[f] for f in wf] for r in workers]),
            "conditions": table(cf, [[r[f] for f in cf] for r in p["conditions"]]),
            "earnings": table(ef, [[r[f] for f in ef] for r in p["earnings"]]),
        },
        "cpi": {"point_fields": ["month", "index", "inflation"], "all_india": cpi_all, "states": cpi_states},
        "cpialrl": table(ALRL_FIELDS, [[r.get(f) for f in ALRL_FIELDS] for r in ds["cpialrl"]
                                       if r.get("indicator") == "General Index"]),
        "hces": table(HCES_SITE_FIELDS, [[HCES_SITE[r["indicator"]]] + [r.get(f) for f in HCES_SITE_FIELDS[1:]]
                                         for r in ds["hces"] if r["indicator"] in HCES_SITE and not r["left_out"]]),
        "source_problems": ds["source_problems"],
    }


def assemble() -> dict:
    """Read every downloaded file into one dataset (all rows, as dicts). Used by the checks."""
    manifest = json.loads(MANIFEST.read_text())
    problems: list[str] = []
    ds: dict = {
        "description": "Jobs (PLFS), consumer prices (CPI, CPI-AL/RL) and household spending (HCES) from MoSPI's official data API.",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {k: {"url": v["url"], "sha256": v["sha256"], "fetched_at": v["fetched_at"], "records": v.get("records")}
                    for k, v in sorted(manifest.items()) if not v.get("empty")},
    }
    ds["plfs"] = plfs(manifest, problems)
    ds["cpi"] = cpi(manifest, problems)
    ds["cpialrl"] = cpialrl(manifest, problems)
    ds["hces"] = hces(manifest, problems)
    ds["source_problems"] = problems
    return ds


def main() -> dict:
    ds = assemble()
    DATA.mkdir(parents=True, exist_ok=True)
    p = ds["plfs"]
    outputs = {
        "plfs_rates.csv": (p["rates"], ["frequency", "year_type"] + RATE_DIMS + ["lfpr", "wpr", "ur", "left_out"]),
        "plfs_workers.csv": (p["distribution"], ["frequency", "year_type", "year", "state", "sector", "gender", "status",
                                                 "breakdown", "category", "value", "value_as_printed", "unit"]),
        "plfs_conditions.csv": (p["conditions"], ["frequency", "year_type", "year", "state", "sector", "gender",
                                                  "condition", "value", "value_as_printed", "unit"]),
        "plfs_earnings.csv": (p["earnings"], ["frequency", "year_type", "year", "period", "state", "sector", "gender",
                                              "kind", "indicator", "value", "value_as_printed", "unit"]),
        "cpi.csv": (ds["cpi"], ["month", "state", "sector", "group", "subgroup", "index", "inflation"]),
        "cpialrl.csv": (ds["cpialrl"], ["month"]),
        "hces.csv": (ds["hces"], ["year", "state", "sector", "indicator"]),
    }
    for name, (rows, first) in outputs.items():
        fields = fields_of(rows, first)
        if name.startswith("plfs_"):  # columns that are blank in every row add nothing
            fields = [f for f in fields if any(r.get(f) not in (None, "") for r in rows)]
        write_csv(name, fields, rows)
        print(f"{name}: {len(rows)} rows")
    write_csv("sources.csv", ["key", "url", "sha256", "fetched_at", "records"],
              [{"key": k, **v} for k, v in ds["sources"].items()])
    (DATA / "jobs_prices.json").write_text(json.dumps(site_json(ds), ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"jobs_prices.json written; {len(ds['source_problems'])} problems")
    return ds


if __name__ == "__main__":
    main()

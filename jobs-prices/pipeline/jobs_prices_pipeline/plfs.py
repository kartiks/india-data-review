"""Periodic Labour Force Survey (PLFS) from MoSPI's data service: rates, workers, job conditions and earnings, and
the combinations the site must not show (flag_rates)."""

from collections import defaultdict

from .common import MONTH_NO, load, number

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


def period(r: dict) -> str:
    """'' for a year, 'Q2' (Apr-Jun) for a quarter, '07' for a month."""
    if r.get("month"):
        return f"{MONTH_NO[r['month']]:02d}"
    if r.get("quarter") and r["quarter"] != "all":
        return f"Q{QUARTERS[r['quarter']]}"
    return ""

def cell_text(dims: dict) -> str:
    return ", ".join(str(dims[k]) for k in ("year", "period", "state", "sector", "gender", "status") if dims.get(k))

def read(manifest: dict, problems: list[str]) -> dict:
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

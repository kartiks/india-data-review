"""Periodic Labour Force Survey (PLFS) from MoSPI's data service: rates, workers, job conditions and earnings, and
the combinations the site must not show (flag_rates)."""

from collections import defaultdict

from pipeline_common.numbers import number

from .common import MONTH_NO, load

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
# Detailed levels of industry and occupation: in the CSV, not on the site.
DETAIL_BREAKDOWNS = {"nco_subdivision", "nco_group", "nic_section", "nic_division", "nic_group", "nic_class"}

# Occupation divisions, as MoSPI's data service named them until November 2026 ('NCO Division 1: ...'); since then
# it prints 'Division 1' with the same figures, so the names are kept.
NCO_DIVISIONS = {
    1: "NCO Division 1: LEGISLATORS, SENIOR OFFICIALS AND MANAGERS", 2: "NCO Division 2: PROFESSIONALS",
    3: "NCO Division 3: TECHNICIANS AND ASSOCIATE PROFESSIONALS", 4: "NCO Division 4: CLERKS",
    5: "NCO Division 5: SERVICE WORKERS AND SHOP & MARKET SALES WORKERS",
    6: "NCO Division 6: SKILLED AGRICULTURAL AND FISHERY WORKERS", 7: "NCO Division 7: CRAFT AND RELATED TRADES WORKERS",
    8: "NCO Division 8: PLANT AND MACHINE OPERATORS AND ASSEMBLERS", 9: "NCO Division 9: ELEMENTARY OCCUPATIONS",
}
# Industry (NIC 2008) in one field, the level shown by the indent: '   A' section, '  01' division, ' 011' group,
# '0111' class.
NIC_LEVELS = {3: "nic_section", 2: "nic_division", 1: "nic_group", 0: "nic_class"}


def plain_year(year: str) -> str:
    """'2022' for 'PLFS 2022': since November 2026 MoSPI's data service names the annual survey years so."""
    return year.removeprefix("PLFS ").strip()


def fill_blanks(dims: dict) -> None:
    """Annual rates in the labels used until November 2026. Since then MoSPI's data service names only the breakdown
    a row belongs to (age, religion, social group or education) and leaves the others blank where it printed 'all'.
    The education rows leave the age blank too; their 'all' row is the figure for 15 years and above, so they are
    for 15 and over (they were labelled 'All ages' before, with the same figures; read() skips that 'all' row). Rows that repeat another
    (religion 'all' and social group 'all' repeat the age rows) then merge, and differing values are reported."""
    for k in ("religion", "social_group", "education"):
        dims[k] = dims[k] or "all"
    dims["age"] = dims["age"] or "15 years and above"


def level(field: str, category: str) -> tuple[str, str]:
    """(breakdown, category) for one row of workers. Since November 2026 MoSPI's data service puts every level of
    occupation (NCO) and industry (NIC) in one field, each level adding up to 100% and a 'total' row; each level
    becomes a breakdown of its own and 'total' becomes 'All'. Other fields are returned as they are. Raises
    ValueError for a category that fits no level."""
    if field not in ("nco_division", "nic_division"):
        return field, category
    c = category.strip()
    if c.lower() == "total":
        return field, "All"
    if field == "nco_division":
        if c.startswith("NCO Division"):  # the names used until November 2026
            return field, c
        if c.startswith("Division") and c.split()[-1].isdigit() and int(c.split()[-1]) in NCO_DIVISIONS:
            return field, NCO_DIVISIONS[int(c.split()[-1])]
        code = c.removeprefix("Sub-division").strip()
        if code.isdigit() and len(code) in (2, 3):
            return ("nco_subdivision" if len(code) == 2 else "nco_group"), code
    else:
        indent = len(category) - len(category.lstrip())
        if indent in NIC_LEVELS and len(c) == 4 - indent and (c.isdigit() or (indent == 3 and c.isalpha())):
            return NIC_LEVELS[indent], c
    raise ValueError(f"{field} category {category!r} fits no level")


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
    crossed: list[str] = []
    labels: dict[int, str] = {}
    kept: list[str] = []
    for key, _entry, body in load(manifest, "plfs/"):
        if body.get("kept"):
            kept.append(f"{key}: {body['kept']['rows']} rows from {body['kept']['file']}")
        freq = key.split("/")[1]
        code = body["query"]["indicator_code"]
        for r in body["rows"]:
            labels[code] = r["indicator"]
            v = number(r.get("value"))
            dims = {ours: r.get(api) or "" for api, ours in PLFS_FIELDS.items()}
            dims["year"] = plain_year(dims["year"])
            dims["period"] = period(r)
            if code in RATES and freq == "annual":
                if not r.get("AgeGroup") and r.get("General_Education") == "all":
                    # The education block's total: a second copy of the 15-and-over figure (equal in all but six
                    # 2025 cells, by up to 0.3 points); the age row is used.
                    continue
                fill_blanks(dims)
            extra = {k: val for k, val in r.items() if k not in PLFS_FIELDS and k not in PLFS_SKIP and val not in (None, "")}
            if code in RATES:
                k = tuple(dims[d] for d in RATE_DIMS)
                rec = rates[freq].setdefault(k, {"year_type": dims["year_type"], "source": []})
                name = RATES[code]
                if name in rec and rec[name] != v:
                    problems.append(f"{key}: {dict(zip(RATE_DIMS, k))} published twice ({rec[name]} and {v})")
                rec[name] = v
                rec[name + "_raw"] = r.get("value")
                if key not in rec["source"]:  # a row repeated in another breakdown's block (fill_blanks)
                    rec["source"].append(key)
                continue
            kind = "earnings" if code in EARNINGS else "distribution" if code == 4 else "conditions"
            if code == 4 and set(extra) == {"employee_contract"}:
                # Since November 2026 the distribution of workers also carries the job conditions of regular
                # employees, by calendar year (indicator 5 has them by July-June year).
                kind = "conditions"
            rec = {"frequency": freq, **{d: dims[d] for d in ("year", "year_type", "period", "state", "sector",
                                                                 "gender", "age", "status")},
                   "value": v, "value_as_printed": r.get("value"), "unit": r.get("unit") or "", "source": key}
            if code in EARNINGS:
                rec["kind"] = EARNINGS[code]
                rec["indicator"] = r["indicator"]
            elif kind == "conditions":
                rec["indicator"] = r["indicator"]
                rec["condition"] = r.get("employee_contract") or ""
            else:
                # One breakdown per row (type of work, broad industry, industry section, employer, occupation).
                if len(extra) > 1:
                    crossed.append(f"{key}: {cell_text(dims)} {' × '.join(sorted(extra.values()))}")
                    continue
                if len(extra) != 1:
                    unlabelled.append(f"{key}: {cell_text(dims)} value {r.get('value')}")
                    continue
                (field, category), = extra.items()
                try:
                    rec["breakdown"], rec["category"] = level(field, category)
                except ValueError as e:
                    problems.append(f"{key}: {cell_text(dims)}: {e}")
                    continue
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
            "unlabelled": unlabelled, "crossed": crossed, "kept": kept}

SMALL_GAP = 0.3  # points: a worker ratio further than this from participation × (1 − unemployment) is wrong
# How MoSPI marks "no figure": NaN, a dash, or ** (too few people in the sample to publish)
MISSING = ("NaN", "nan", "-", "**", None, "")


def identity_gap(r: dict) -> tuple[float, float]:
    """(gap, rounding tolerance) between the published worker ratio and participation × (1 − unemployment)."""
    lf, w, u = r["lfpr"], r["wpr"], r["ur"]
    expected = lf * (1 - u / 100)
    return abs(expected - w), 0.05 + 0.05 * (1 - u / 100) + lf * 0.0005 + 1e-9  # each figure is rounded to 0.1


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

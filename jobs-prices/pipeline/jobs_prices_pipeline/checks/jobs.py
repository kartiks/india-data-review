"""Jobs (PLFS): the three rates tied by their identity, totals between their parts, shares adding up to 100%."""

from collections import defaultdict

from pipeline_common.report import Allowed, Report

from ..plfs import MISSING, RATE_DIMS, SMALL_GAP, identity_gap
from .values import BAD_VALUE, cell


# Shares of workers are printed to one decimal, so each is off by up to SHARE_ROUNDING points.
SHARE_ROUNDING = 0.05
SUBTOTAL_TOL = 0.15  # points: 'all self-employed' against its two parts (three rounded shares)
SHARE_SUM_TOL = 0.25  # points: a breakdown's shares against 100% (or SHARE_ROUNDING per share, if more)

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
MISSING_CATEGORY = (
    "MoSPI's data service has no figure for one or more of this breakdown's categories here (named in each case), "
    "so the shares it has add up to less than 100%."
)


CWS_STATUS_2025 = (
    "For 2025 in current weekly status (CWS), MoSPI's 'all self-employed' share is not the sum of its two parts "
    "(own-account workers and helpers) in most states, and the shares add up to less than 100%. The site uses the "
    "usual status (PS+SS) figures, where they add up."
)


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
    report.add("Jobs: worker ratio = participation × (1 − unemployment rate)", checked, failures, notes, allowed)


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
    categories: dict[tuple, set] = defaultdict(set)  # every category a breakdown has anywhere
    for (freq, b, *_), cats in groups.items():
        categories[(freq, b)] |= set(cats) - {"_bad"}
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
                if abs((own.get("1.") or 0) + (own.get("2.") or 0) - (own.get("3.") or 0)) > SUBTOTAL_TOL:
                    problems.append(f"{where}: all self-employed {own.get('3.')} ≠ {own.get('1.')} + {own.get('2.')}")
                tol = SHARE_SUM_TOL
            else:
                total = sum(vals)
                tol = max(SHARE_SUM_TOL, SHARE_ROUNDING * len(vals))
            if abs(total - 100) > tol:
                missing = sorted(categories[(freq, b)] - set(cats))
                if missing and total < 100 and rule is None:
                    rule = MISSING_CATEGORY
                    problems.append(f"{where}: shares add up to {total:.1f}%; no figure for {'; '.join(missing)}")
                else:
                    problems.append(f"{where}: shares add up to {total:.1f}%")
        for msg in problems:
            if rule:
                allowed.add(rule, msg)
            elif freq != "annual" or (status != "PS+SS" and b != "broad_industry_work"):
                notes.append(f"Not shown on the site: {msg}")
            else:
                failures.append(msg)
    report.add("Jobs: shares of workers add up to 100%", checked, failures, notes, allowed)

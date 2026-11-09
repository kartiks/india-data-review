"""Every value in MoSPI's data service files is a number or marked missing."""

from pipeline_common.report import Allowed, Report

from ..plfs import MISSING


UNLABELLED = (
    "MoSPI's data service returns some 'percentage distribution of workers' rows with no breakdown named (no type "
    "of work, industry or employer), often with several different values for the same cell. They cannot be read "
    "and are left out."
)


CROSSED = (
    "MoSPI's data service returns some 'percentage distribution of workers' rows with two breakdowns at once (type "
    "of work within an industry, All India, since November 2026). The site does not use them; they are not read."
)


WITHDRAWN_KEPT = (
    "MoSPI's data service no longer returns these rows. They are kept from the last download that had them (listed "
    "in sources.WITHDRAWN)."
)


BAD_VALUE = "MoSPI's data service returns characters instead of a number for this figure. It is left out."


def cell(d: dict, keys=("frequency", "year", "period", "state", "sector", "gender", "age", "status")) -> str:
    return ", ".join(str(d[k]) for k in keys if d.get(k) not in (None, "", "all"))


def check_source(ds: dict, report: Report) -> None:
    failures, allowed = list(ds["source_problems"]), Allowed()
    checked = len(failures)

    def value_ok(v, printed, where):
        if v is None and printed not in MISSING:
            allowed.add(BAD_VALUE, f"{where} printed as {printed!r}")

    p = ds["plfs"]
    for r in p["distribution"] + p["conditions"] + p["earnings"]:
        checked += 1
        value_ok(r["value"], r["value_as_printed"], f"{cell(r)} {r.get('category', r.get('condition', r.get('kind', '')))}")
    for r in p["rates"]:
        for k in ("lfpr", "wpr", "ur"):
            checked += 1
            value_ok(r[k], r[k + "_as_printed"], f"{cell(r)} {k}")
    for r in ds["cpi"]:
        for k in ("index", "inflation"):
            checked += 1
            value_ok(r[k], r[k + "_as_printed"], f"CPI {r['month']} {r['state']} {r['sector']} {r['subgroup']} {k}")
    for r in ds["cpialrl"]:
        for k in ("index_al", "index_rl", "inflation_al", "inflation_rl"):
            if k + "_as_printed" in r and not r.get(f"not_compiled_{k[-2:]}"):
                checked += 1
                value_ok(r.get(k), r.get(k + "_as_printed"), f"CPI-AL/RL {r['month']} {r.get('state')} {k}")
    for r in ds["hces"]:
        checked += 1
        value_ok(r["value"], r["value_as_printed"], f"HCES {r.get('year')} {r.get('state')} {r.get('indicator')}")
    for u in p.get("unlabelled", []):
        checked += 1
        allowed.add(UNLABELLED, u)
    for c in p.get("crossed", []):
        checked += 1
        allowed.add(CROSSED, c)
    for k in p.get("kept", []):
        checked += 1
        allowed.add(WITHDRAWN_KEPT, k)
    report.add("Every published value is understood", checked, failures, allowed=allowed, limit=20)

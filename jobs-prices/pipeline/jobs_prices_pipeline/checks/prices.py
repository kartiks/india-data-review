"""Consumer prices from MoSPI's data service (CPI base 2012, CPI-AL/RL): inflation reproduced from the index, the
combined index between rural and urban, no month missing."""

from collections import defaultdict

from pipeline_common.report import Report

INFLATION_TOL = 0.12  # points: indices are published to one decimal, so a recomputed rate can differ this much


def prev_year(month: str) -> str:
    y, m = month.split("-")
    return f"{int(y) - 1}-{m}"


def inflation_check(series: dict[tuple, dict[str, tuple]], label: str) -> tuple[int, list[str]]:
    """series: key -> month -> (index, inflation). Recompute inflation from the index a year earlier."""
    checked, failures = 0, []
    for key, months in sorted(series.items()):
        for m, (idx, infl) in sorted(months.items()):
            before = months.get(prev_year(m))
            if infl is None or idx is None or not before or before[0] is None:
                continue
            checked += 1
            calc = (idx / before[0] - 1) * 100
            if abs(calc - infl) > INFLATION_TOL:
                failures.append(f"{label} {' / '.join(k for k in key if k)} {m}: index {idx} vs {before[0]} a year "
                                f"earlier gives {calc:.2f}%, published {infl}%")
    return checked, failures


def cpi_series(ds: dict) -> dict[tuple, dict[str, tuple]]:
    """(state, sector, subgroup) -> month -> (index, inflation)."""
    series: dict[tuple, dict[str, tuple]] = defaultdict(dict)
    for r in ds["cpi"]:
        series[(r["state"], r["sector"], r["subgroup"])][r["month"]] = (r["index"], r["inflation"])
    return series


def check_cpi_inflation(ds: dict, report: Report) -> None:
    checked, failures = inflation_check(cpi_series(ds), "CPI")
    report.add("Prices (CPI): inflation reproduced from the index a year earlier", checked, failures, [])


def check_cpi_combined(ds: dict, report: Report) -> None:
    series = cpi_series(ds)
    failures, checked = [], 0
    for (state, sector, sub), months in sorted(series.items()):
        if sector != "Combined":
            continue
        rural, urban = series.get((state, "Rural", sub), {}), series.get((state, "Urban", sub), {})
        for m, (idx, _) in months.items():
            a, b = rural.get(m, (None,))[0], urban.get(m, (None,))[0]
            if None in (idx, a, b):
                continue
            checked += 1
            if not (min(a, b) - 0.1 <= idx <= max(a, b) + 0.1):
                failures.append(f"CPI {state} {sub} {m}: combined {idx} outside rural {a} and urban {b}")
    report.add("Prices (CPI): combined index lies between rural and urban", checked, failures, [])


def months_between(first: str, last: str) -> list[str]:
    """Every month from first to last ('2013-01' ...), both included."""
    out = []
    y, m = map(int, first.split("-"))
    while f"{y}-{m:02d}" <= last:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def check_cpi_months(ds: dict, report: Report) -> None:
    """The general index has every month from the first to the last: a gap fails for All India and is a note for a
    state (shown as a gap)."""
    failures, notes, checked = [], [], 0
    months_all = sorted({r["month"] for r in ds["cpi"]})
    if months_all:
        first, last = months_all[0], months_all[-1]
        expected = months_between(first, last)
        for (state, sector, sub), months in sorted(cpi_series(ds).items()):
            if sub != "General-Overall":
                continue
            have = {mm for mm, (idx, _) in months.items() if idx is not None}
            checked += 1
            missing = [mm for mm in expected if mm not in have]
            if missing:
                text = (f"CPI general index, {state}, {sector}: no index for {len(missing)} months "
                        f"({', '.join(missing[:6])}{' …' if len(missing) > 6 else ''})")
                if state == "All India":
                    failures.append(text)
                else:
                    notes.append(f"Gap, shown as a gap: {text}")
        notes.insert(0, f"Months covered: {first} to {last}.")
    report.add("Prices (CPI): no month missing", checked, failures, notes)


def check_cpialrl(ds: dict, report: Report) -> None:
    series: dict[tuple, dict[str, tuple]] = defaultdict(dict)
    for r in ds["cpialrl"]:
        for who in ("al", "rl"):
            if f"index_{who}_as_printed" in r:
                key = (r.get("indicator", ""), f"base {r.get('base_year', '')}", r.get("state", ""), str(r.get("group") or ""), who.upper())
                series[key][r["month"]] = (r.get(f"index_{who}"), r.get(f"inflation_{who}"))
    checked, failures = inflation_check(series, "CPI-AL/RL")
    zero = sorted({f"{r.get('state')} ({who.upper()}, base {r.get('base_year')})" for r in ds["cpialrl"] for who in ("al", "rl")
                   if r.get(f"not_compiled_{who}")})
    notes = [f"Index published as 0.00, treated as not compiled: {', '.join(zero)}."] if zero else []
    report.add("Prices (CPI for farm and rural labourers): inflation reproduced from the index", checked, failures, notes)

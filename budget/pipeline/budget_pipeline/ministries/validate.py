"""Checks: identities inside each statement, against the Budget at a Glance, across budgets and across copies."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from pipeline_common.numbers import blank_or_number
from pipeline_common.report import Allowed, Exceptions

LEVEL_TOL = 0.05  # ₹ crore: values are printed to two decimals; allowed per cell in a sum of many cells


def _close(a: float | None, b: float | None, tol: float = LEVEL_TOL) -> bool:
    return abs((a or 0.0) - (b or 0.0)) <= tol


def _sum(xs) -> float:
    return sum(x or 0.0 for x in xs)


Check = Callable[[str, bool, str], None]  # check(name, ok, message) records one check


def _line_identities(it: dict, parsed: dict, check: Check) -> None:
    """Identities of one line: its two parts add to its total; a department's Revenue and Capital lines add up to
    it; a Demand's sub-lines add up to it and its 'Total:' line repeats it."""
    cols = parsed["columns"]
    a, b = parsed["subcolumns"][:2]
    lines = [("", it["periods"])]
    if "revenue_line" in it:
        lines += [(" (Revenue line)", it["revenue_line"]), (" (Capital line)", it["capital_line"])]
    for cat, per in it.get("subs", {}).items():
        lines.append((f" / {cat}", per))
    for suffix, per in lines:
        for c, col in enumerate(cols):
            v = per[c]
            if v["total"] is None and v[a] is None and v[b] is None:
                continue
            check(f"{a} + {b} = total on every line", _close(_sum([v[a], v[b]]), v["total"]),
                  f"{col.kind} {col.fiscal_year} {it['name']!r}{suffix}: {v[a]} + {v[b]} != {v['total']}")
    if "revenue_line" in it:
        for c, col in enumerate(cols):
            for sub in ("plan", "non_plan", "total"):
                got = _sum([it["revenue_line"][c][sub], it["capital_line"][c][sub]])
                check("Revenue line + Capital line = department line", _close(got, it["periods"][c][sub]),
                      f"{col.kind} {col.fiscal_year} {it['name']!r} {sub}: revenue + capital = {got:.2f}, "
                      f"printed {it['periods'][c][sub]}")
    if it.get("subs") and it["level"] != "grand_total":
        for c, col in enumerate(cols):
            for sub in ("revenue", "capital", "total"):
                got = _sum(per[c][sub] for per in it["subs"].values())
                check("sub-lines add up to the demand", _close(got, it["periods"][c][sub], LEVEL_TOL * len(it["subs"])),
                      f"{col.kind} {col.fiscal_year} {it['name']!r} {sub}: sub-lines {got:.2f}, "
                      f"printed {it['periods'][c][sub]}")
    if "printed_total" in it:
        for c, col in enumerate(cols):
            check("'Total:' line repeats the demand total",
                  _close(it["printed_total"][c]["total"], it["periods"][c]["total"]),
                  f"{col.kind} {col.fiscal_year} {it['name']!r}: Total: line {it['printed_total'][c]['total']} "
                  f"vs {it['periods'][c]['total']}")


def _grand_total_sums(parsed: dict, check: Check) -> None:
    """Departments add up to the grand total, and each spending category across Demands to its grand total line."""
    cols = parsed["columns"]
    grand = [it for it in parsed["items"] if it["level"] == "grand_total"]
    if len(grand) != 1:
        check("departments add up to the grand total", False, f"{len(grand)} grand total lines")
    else:
        g = grand[0]
        leaves = [it for it in parsed["items"] if it["level"] not in ("subtotal", "grand_total")]
        for c, col in enumerate(cols):
            for sub in parsed["subcolumns"]:
                got = _sum(it["periods"][c][sub] for it in leaves)
                check("departments add up to the grand total", _close(got, g["periods"][c][sub], LEVEL_TOL * len(leaves)),
                      f"{col.kind} {col.fiscal_year} {sub}: lines add to {got:.2f}, grand total {g['periods'][c][sub]}")
        if g.get("subs"):
            for cat, per in g["subs"].items():
                for c, col in enumerate(cols):
                    for sub in ("revenue", "capital", "total"):
                        got = _sum(it["subs"].get(cat, [{}] * len(cols))[c].get(sub) for it in leaves if it.get("subs"))
                        check("each spending category adds up across demands", _close(got, per[c][sub], LEVEL_TOL * len(leaves)),
                              f"{col.kind} {col.fiscal_year} {cat} {sub}: demands add to {got:.2f}, "
                              f"grand total line {per[c][sub]}")


def internal_checks(budget: str, parsed: dict) -> tuple[int, list[str], list[str], dict]:
    """Row and table identities for one parsed document.

    Returns (checked, failures, notes, results) where results keys are check names
    with per-check (checked, failures) counts for reporting.
    """
    res: dict[str, list] = defaultdict(lambda: [0, []])

    def check(name: str, ok: bool, msg: str) -> None:
        res[name][0] += 1
        if not ok:
            res[name][1].append(f"Budget {budget}: {msg}")

    for it in parsed["items"]:
        _line_identities(it, parsed, check)
    _grand_total_sums(parsed, check)
    checked = sum(v[0] for v in res.values())
    failures = [f for v in res.values() for f in v[1]]
    return checked, failures, [], dict(res)


# --------------------------------------------------------------------------- reviewed exceptions, all checks

UT_CAPITAL_LINE = (
    "The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised "
    "Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply "
    "-55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to "
    "2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up."
)
GRAND_2023_CSS = (
    "Budget 2023-24's grand-total block prints Central Sector Schemes revenue for 2021-22 as 74188.47; "
    "the demands add to 741,888.47 and its own total minus capital (12,09,949.59 - 4,68,061.12) is "
    "741,888.47 (confirmed on the page image). A dropped digit in the source."
)
GRAND_2023_OTHER = (
    "Budget 2023-24's grand-total block prints Other Transfers revenue for RE 2022-23 as 192262.62; "
    "the demands add to 1,92,226.62 and total minus capital (2,79,138.04 - 86,911.42) is 1,92,226.62. "
    "Two digits transposed in the source."
)
ACTUAL_1998_99 = (
    "Budget 2000-01's 1998-99 Actuals: the departments' Plan figures add to 53.45 crore more than the "
    "printed Central Ministries total (37,107.43, confirmed on the page image), while the printed "
    "totals agree with each other and with the Budget at a Glance. Revenue/capital split of the grand "
    "total also differs from the Budget at a Glance by 932.79 crore (totals agree). 1998-99 is before "
    "the published range (2000-01 onwards)."
)

# ((budget, check title), message fragment) -> reason. A failure is allowed only if its message contains the
# fragment (the longest matching fragment wins).
KNOWN_EXCEPTIONS: dict[tuple[tuple[str, str], str], str] = {
    **{((b, "Revenue line + Capital line = department line"), "'III. UNION TERRITORIES (A + B)'"): UT_CAPITAL_LINE
       for b in ("2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17")},
    (("2023-24", "revenue + capital = total on every line"), "'Grand Total' / central_sector_schemes"): GRAND_2023_CSS,
    (("2023-24", "each spending category adds up across demands"), "central_sector_schemes revenue"): GRAND_2023_CSS,
    (("2023-24", "revenue + capital = total on every line"), "'Grand Total' / other_transfers"): GRAND_2023_OTHER,
    (("2023-24", "each spending category adds up across demands"), "other_transfers revenue"): GRAND_2023_OTHER,
    (("2000-01", "departments add up to the grand total"), "Actual 1998-99"): ACTUAL_1998_99,
    (("2000-01", "grand total = Budget at a Glance"), "Actual 1998-99"): ACTUAL_1998_99,
}

# Same table in another format (Excel) that disagrees with the PDF: (budget, ext) -> reason.
KNOWN_FORMAT_ISSUES: dict[tuple[str, str], str] = {}

# Grand Total category lines present in only one copy, explained: (budget, ext) -> reason.
ONE_COPY_ONLY: dict[tuple[str, str], str] = {
    ("2017-18", "xlsx"): "The Excel copy mislabels the six category lines under Grand Total (all read "
                         "\"Centre's expenditure\" / \"Transfers to ...\"), so they cannot be matched; the PDF labels "
                         "them correctly.",
    ("2025-26", "xlsx"): "The PDF has no category lines under Grand Total; the Excel copy adds them.",
}

# Every known exception: KNOWN_EXCEPTIONS by fragment; the other copies' differences ("format") and Grand Total
# lines in only one copy ("one copy") by the start of their message.
EXCEPTIONS = Exceptions(
    known={
        **{("format", f"Budget {budget}: {ext.upper()} differs"): reason
           for (budget, ext), reason in KNOWN_FORMAT_ISSUES.items()},
        **{("one copy", f"Budget {budget}: {ext.upper()} "): reason for (budget, ext), reason in ONE_COPY_ONLY.items()},
    },
    contains=KNOWN_EXCEPTIONS,
)

# Budget 2017-18 abolished the Plan/Non-plan split. Its Statement 3A restates 2016-17 under the new
# structure: central assistance for State Plans is folded into the department it was routed through,
# and Police, Cabinet, Pensions, Direct/Indirect Taxes and others become separate demands. Lines of
# Budget 2016-17 and Budget 2017-18 are therefore not like-for-like; only the grand total must agree.
STRUCTURE_BREAK = ("2016-17", "2017-18")


def _cmp_formats(primary: dict, other: dict) -> list[str]:
    """Differences between two parses of the same table (None and 0 count as equal)."""
    def index(p):
        out = {}
        for it in p["items"]:
            for c, col in enumerate(p["columns"]):
                for sub, v in it["periods"][c].items():
                    out[(it["item_id"], col.kind, col.fiscal_year, sub)] = v
                for cat, per in it.get("subs", {}).items():
                    out[(it["item_id"] + "/" + cat, col.kind, col.fiscal_year, "total")] = per[c]["total"]
        return out
    a, b = index(primary), index(other)
    diffs = []
    for k in sorted(set(a) | set(b)):
        if k not in a or k not in b:
            diffs.append(f"{k}: only in one copy")
        elif abs((a[k] or 0) - (b[k] or 0)) > 0.011:
            diffs.append(f"{k}: {a[k]} vs {b[k]}")
    return diffs


Sections = dict[str, list]  # title -> [checked, failures, notes, allowed exceptions]


def _record(sections: Sections, title: str, budget: str, checked: int, failures: list[str]) -> None:
    """Add a group's counts and failures, filing each listed exception under its reason."""
    sec = sections[title]
    sec[0] += checked
    sec[1].extend(sec[3].sort_out((budget, title), failures))


def _identities(all_parsed: dict, sections: Sections) -> None:
    """(a)-(c) Identities inside each primary document."""
    for budget, b in all_parsed.items():
        _, _, _, res = internal_checks(budget, b["parsed"][b["primary"]])
        for title, (n, fails) in res.items():
            _record(sections, title, budget, n, fails)


def _against_summary(all_parsed: dict, summary_observations: list[dict], sections: Sections) -> None:
    """(d) Grand total vs the Budget at a Glance summary table, same budget and column."""
    summ: dict[tuple, dict] = defaultdict(dict)
    for r in summary_observations:
        v = blank_or_number(r.get("value_crore"))
        if v is not None:
            summ[(r["source_budget"], r["fiscal_year"], r["kind"])][r["field"]] = v
    title = "grand total = Budget at a Glance"
    for budget, b in all_parsed.items():
        p = b["parsed"][b["primary"]]
        g = next(it for it in p["items"] if it["level"] == "grand_total")
        fails, n = [], 0
        for c, col in enumerate(p["columns"]):
            s = summ.get((budget, col.fiscal_year, col.kind), {})
            rev = g["revenue_line"][c]["total"] if "revenue_line" in g else g["periods"][c]["revenue"]
            cap = g["capital_line"][c]["total"] if "capital_line" in g else g["periods"][c]["capital"]
            for name, ours, field in (("total", g["periods"][c]["total"], "total_expenditure"),
                                      ("revenue", rev, "revenue_expenditure"), ("capital", cap, "capital_expenditure")):
                if field not in s:
                    fails.append(f"Budget {budget}: {col.kind} {col.fiscal_year} {field} missing from summary table")
                    continue
                n += 1
                if abs((ours or 0) - s[field]) > 1.0:  # summary is in whole crore
                    fails.append(f"Budget {budget}: {col.kind} {col.fiscal_year} {name}: ministries grand total "
                                 f"{ours:,.2f} vs Budget at a Glance {field} {s[field]:,.0f}")
        _record(sections, title, budget, n, fails)


def _across_budgets(all_parsed: dict, sections: Sections) -> None:
    """(e) The same line, year and estimate printed in two budgets. Restatements happen (lines move between
    departments), so a line difference is accepted when the grand total agrees and either the ministry's total
    agrees (a move inside the ministry) or the budgets straddle the 2017-18 restructuring."""
    title = "same line agrees in both budgets that print it"
    per_pair: dict[tuple, dict] = defaultdict(lambda: defaultdict(dict))
    for budget, b in all_parsed.items():
        p = b["parsed"][b["primary"]]
        for it in p["items"]:
            if it["level"] == "subtotal":
                continue
            for c, col in enumerate(p["columns"]):
                per_pair[(col.fiscal_year, col.kind)][budget][it["item_id"]] = (it.get("ministry_id"), it["periods"][c]["total"])
    n, notes, fails = 0, [], []
    for (year, kind), by_budget in sorted(per_pair.items()):
        budgets = sorted(by_budget)
        if len(budgets) < 2:
            continue
        b1, b2 = budgets[:2]
        x, y = by_budget[b1], by_budget[b2]
        n += 1
        g1, g2 = (x.get("grand_total") or (None, None))[1], (y.get("grand_total") or (None, None))[1]
        if abs((g1 or 0) - (g2 or 0)) > 1.0:
            fails.append(f"{kind} {year}: grand total {g1} in Budget {b1} vs {g2} in Budget {b2}")
        def ministry_totals(d):
            out = defaultdict(float)
            for item, (mid, v) in d.items():
                if item != "grand_total":
                    out[mid] += v or 0
            return out
        m1, m2 = ministry_totals(x), ministry_totals(y)
        for item in sorted(set(x) | set(y)):
            if item == "grand_total":
                continue
            n += 1
            mid, v1 = x.get(item, (None, None))
            mid2, v2 = y.get(item, (None, None))
            mid = mid or mid2
            if abs((v1 or 0) - (v2 or 0)) <= 0.011:
                continue
            msg = f"{kind} {year} {item}: {v1} in Budget {b1} vs {v2} in Budget {b2}"
            if (b1, b2) == STRUCTURE_BREAK:
                notes.append(f"{msg} (restated under the 2017-18 structure; grand totals agree)")
            elif abs(m1[mid] - m2[mid]) <= 1.0:
                notes.append(f"{msg} (moved within {mid}: the ministry total is the same in both)")
            else:
                fails.append(f"{msg}; ministry {mid} total {m1[mid]:.2f} vs {m2[mid]:.2f}")
    sections[title][0] += n
    sections[title][1].extend(fails)
    sections[title][2].extend(f"Restated: {m}" for m in notes)


def _other_copies(all_parsed: dict, sections: Sections) -> None:
    """(f) Other formats agree with the PDF."""
    title = "Excel copies agree with the PDF"
    for budget, b in all_parsed.items():
        prim = b["parsed"][b["primary"]]
        for ext, p in b["parsed"].items():
            if ext == b["primary"]:
                continue
            sections[title][0] += 1
            diffs = _cmp_formats(prim, p)
            only = [d for d in diffs if d.endswith("only in one copy")]
            diffs = [d for d in diffs if not d.endswith("only in one copy")]
            grand_only = [d for d in only if d.startswith("('grand_total/")]
            line_only = [d for d in only if d not in grand_only]
            ok = sections[title][3]
            if grand_only and not ok.file("one copy", f"Budget {budget}: {ext.upper()} vs {b['primary'].upper()}: "
                                                      f"{len(grand_only)} values of the Grand Total's category lines "
                                                      "are in only one of the two copies"):
                line_only += grand_only
            diffs += line_only
            msg = f"Budget {budget}: {ext.upper()} differs from {b['primary'].upper()} in {len(diffs)} values"
            if not diffs:
                sections[title][2].append(f"Budget {budget}: {ext.upper()} matches {b['primary'].upper()} exactly.")
            elif not ok.file("format", msg):
                sections[title][1].append(f"{msg}: " + "; ".join(diffs[:4]))
        for ext, err in b["errors"].items():
            sections[title][1].append(f"Budget {budget}: {ext.upper()} copy could not be read: {err}")


def checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple]:
    """All ministry checks. Returns [(title, checked, failures, notes, allowed exceptions)]."""
    EXCEPTIONS.reset()
    sections: Sections = defaultdict(lambda: [0, [], [], Allowed(EXCEPTIONS, more_hint="")])
    _identities(all_parsed, sections)
    _against_summary(all_parsed, summary_observations, sections)
    _across_budgets(all_parsed, sections)
    _other_copies(all_parsed, sections)
    order = [
        "plan + non_plan = total on every line", "revenue + capital = total on every line",
        "Revenue line + Capital line = department line", "sub-lines add up to the demand",
        "'Total:' line repeats the demand total", "departments add up to the grand total",
        "each spending category adds up across demands", "grand total = Budget at a Glance",
        "same line agrees in both budgets that print it", "Excel copies agree with the PDF",
    ]
    return [(f"Ministries: {t}", *sections[t]) for t in order if t in sections]

"""Checks that every published number is internally consistent and traceable.

1. Accounting rules, applied to every column of every source document
   (e.g. revenue deficit = revenue expenditure - revenue receipts).
2. Cross-document agreement: a Budget Estimate printed in its own budget and
   again in the next year's budget should match (differences are listed).
3. % of GDP: the printed percentages must agree with each other, and with the
   GDP the budget states, within rounding.
4. Completeness: every year 2000-01 onwards has the figures it should have.
5. The RBI Handbook of Statistics series (an independent compilation of the
   same accounts) must match, apart from documented differences.
6. Other copies of each table (Excel/HTML) must agree with the PDF used.
7. Text: no '<', '>' or control characters in any key or value of the data files
   (pipeline_common.data_text).

Exceptions are allowed only through EXCEPTIONS below (built from the reviewed lists in annotations.py), each
with a reason; the report lists every allowed case under its reason and the summary counts them. The taxes,
ministries and schemes checks keep their own lists the same way. Writes budget/data/validation_report.md and
validation_summary.json; exits non-zero on any failure.

Run: uv run python -m budget_pipeline.checks
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from pipeline_common import log as pipeline_log
from pipeline_common.data_text import check_data_text
from pipeline_common.numbers import blank_or_number
from pipeline_common.report import Allowed, Exceptions, Report
from pipeline_common.text import fy

from .annotations import FINAL_ACCOUNTS, KNOWN_EXCEPTIONS, KNOWN_FORMAT_ISSUES, KNOWN_REFERENCE_DIFFS
from .reference import load_rbi
from .sources import FIRST_BUDGET, LATEST_BUDGET

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

INTRO = "Headline figures, taxes, ministries and schemes. Every allowed exception lists its reason."

# Rounding: documents say items "may not sum up to the totals due to rounding off".
LEVEL_TOL = 5  # ₹ crore: amounts are printed to the crore, so sums of rounded items can be a few crore off
PCT_ROUNDING = 0.05  # points: % of GDP is printed to one decimal, so each figure is off by up to this
PCT_TOL = 0.051  # points: PCT_ROUNDING, plus a little for the rounding of the amounts themselves
# A BE restated in the next budget by more than both of these is a failure for a person to look at; smaller
# restatements (reclassifications) are listed.
RESTATED_SHARE = 0.02
RESTATED_CRORE = 500
# Our figures against the RBI Handbook series: a difference up to the smaller of these is a provisional figure
# against an audited one (FINAL_ACCOUNTS); anything larger fails unless KNOWN_REFERENCE_DIFFS gives its reason.
# Those seen so far are at most Rs 143 crore and 0.1% (2001-02 actuals).
RBI_SHARE_TOL = 0.001  # 0.1%
RBI_CRORE_TOL = 500  # ₹ crore, so the share does not allow thousands of crore on today's totals
JUMP_SHARE = 0.35  # a year-on-year change in actuals larger than this is listed for review

# Every known exception to the headline checks, as (check, start of its message) -> reason. Besides
# KNOWN_EXCEPTIONS: "format" (another copy of the table differs from the PDF) and "rbi" (a difference from the RBI
# Handbook series larger than RBI_SHARE_TOL or RBI_CRORE_TOL).
EXCEPTIONS = Exceptions({
    **KNOWN_EXCEPTIONS,
    **{("format", f"Budget {budget}: {ext.upper()} differs"): reason
       for (budget, ext), reason in KNOWN_FORMAT_ISSUES.items()},
    **{("rbi", f"{'Actual' if kind == 'actual' else kind.upper()} {year} {field}: ours {ours:,.0f} vs RBI {rbi:,.0f} ("):
       reason for (year, field, kind, ours, rbi), reason in KNOWN_REFERENCE_DIFFS.items()},
})


def allowed() -> Allowed:
    """A section's allowed exceptions, looked up in EXCEPTIONS (no CSV lists the cases left out of the report)."""
    return Allowed(EXCEPTIONS, more_hint="")


RULES = [
    ("revenue receipts = tax + non-tax", "revenue_receipts", ["tax_revenue_net", "non_tax_revenue"], []),
    ("capital receipts = loan recoveries + other receipts + borrowings", "capital_receipts",
     ["recoveries_of_loans", "other_receipts", "borrowings"], []),
    ("total receipts = revenue receipts + capital receipts", "total_receipts", ["revenue_receipts", "capital_receipts"], []),
    ("total expenditure = total receipts", "total_expenditure", ["total_receipts"], []),
    ("total expenditure = revenue + capital expenditure", "total_expenditure",
     ["revenue_expenditure", "capital_expenditure"], []),
    ("revenue deficit = revenue expenditure - revenue receipts", "revenue_deficit",
     ["revenue_expenditure"], ["revenue_receipts"]),
    ("fiscal deficit = expenditure - revenue receipts - loan recoveries - other receipts", "fiscal_deficit",
     ["total_expenditure"], ["revenue_receipts", "recoveries_of_loans", "other_receipts"]),
    ("fiscal deficit = borrowings", "fiscal_deficit", ["borrowings"], []),
    ("primary deficit = fiscal deficit - interest", "primary_deficit", ["fiscal_deficit"], ["interest_payments"]),
    ("effective revenue deficit = revenue deficit - capital grants", "effective_revenue_deficit",
     ["revenue_deficit"], ["grants_capital_assets"]),
    ("effective capital expenditure = capital expenditure + capital grants", "effective_capital_expenditure",
     ["capital_expenditure", "grants_capital_assets"], []),
]
DEFICITS = ["revenue_deficit", "effective_revenue_deficit", "fiscal_deficit", "primary_deficit"]


def load_observations() -> list[dict]:
    with (DATA / "observations.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["value_crore"] = blank_or_number(r["value_crore"])
        r["pct_gdp"] = blank_or_number(r["pct_gdp"])
    return rows


def check_identities(rows: list[dict], report: Report) -> None:
    cols: dict[tuple[str, str, str], dict[str, float | None]] = defaultdict(dict)
    for r in rows:
        cols[(r["source_budget"], r["fiscal_year"], r["kind"])][r["field"]] = r["value_crore"]
    failures, ok, checked = [], allowed(), 0
    for (doc, year, kind), v in sorted(cols.items()):
        for name, lhs, plus, minus in RULES:
            needed = [lhs, *plus, *minus]
            if any(v.get(f) is None for f in needed):
                if lhs in ("other_receipts",) or any(v.get(f) is None for f in plus + minus if f != "other_receipts"):
                    continue
            vals = {f: (v.get(f) or 0.0) for f in needed}
            if v.get(lhs) is None:
                continue
            if any(v.get(f) is None for f in needed if f not in ("other_receipts",)):
                continue
            expected = sum(vals[f] for f in plus) - sum(vals[f] for f in minus)
            diff = vals[lhs] - expected
            checked += 1
            if abs(diff) > LEVEL_TOL:
                msg = (f"Budget {doc}, {kind} {year}: {name} — printed {vals[lhs]:,.0f}, "
                       f"components give {expected:,.0f} (off by {diff:,.0f})")
                if not ok.file("identity", msg):
                    failures.append(msg)
    report.add("Accounting rules hold in every source column", checked, failures, allowed=ok)


def check_cross_document(rows: list[dict], report: Report) -> None:
    by_key = defaultdict(list)
    for r in rows:
        if r["value_crore"] is not None:
            by_key[(r["fiscal_year"], r["kind"], r["field"])].append(r)
    notes, failures, checked, ok = [], [], 0, allowed()
    for (year, kind, field), rs in sorted(by_key.items()):
        if len(rs) < 2:
            continue
        checked += 1
        values = {r["source_budget"]: r["value_crore"] for r in rs}
        if len(set(values.values())) > 1:
            a, b = sorted(values.items())[:2]
            diff = b[1] - a[1]
            rel = abs(diff) / max(abs(a[1]), 1)
            msg = (f"{kind} {year} {field}: {a[1]:,.0f} in budget {a[0]} vs {b[1]:,.0f} in budget {b[0]} "
                   f"({diff:+,.0f}, {rel:.1%})")
            # Restatements happen (reclassification); only large ones need a person to look.
            if ok.file("cross", msg):
                continue
            if rel > RESTATED_SHARE and abs(diff) > RESTATED_CRORE:
                failures.append(msg)
            else:
                notes.append(msg)
    report.add("Same figure agrees across documents (BE restated in the next budget)", checked, failures,
               [f"Restated: {n}" for n in notes], ok)


def check_pct_gdp(rows: list[dict], gdp: dict, report: Report) -> None:
    cols: dict[tuple[str, str, str], dict[str, tuple[float | None, float | None]]] = defaultdict(dict)
    for r in rows:
        cols[(r["source_budget"], r["fiscal_year"], r["kind"])][r["field"]] = (r["value_crore"], r["pct_gdp"])
    failures, checked, ok = [], 0, allowed()
    for (doc, year, kind), v in sorted(cols.items()):
        fd, fd_pct = v.get("fiscal_deficit", (None, None))
        stated = gdp.get(doc)
        if kind == "BE" and year == doc and stated:
            base, base_name = stated["value"], f"stated GDP {stated['value']:,.0f}"
            tol = PCT_TOL
        elif fd and fd_pct:
            base, base_name = fd * 100 / fd_pct, "GDP implied by fiscal deficit %"
            tol = PCT_TOL + PCT_ROUNDING * 100 / fd_pct * PCT_ROUNDING  # rounding of the fiscal deficit % itself
        else:
            # No GDP to check against (no stated GDP, no fiscal deficit %). Fine if the column prints no % of GDP.
            printed = [f for f in DEFICITS if v.get(f, (None, None))[1] is not None]
            if printed:
                checked += 1
                failures.append(f"Budget {doc}, {kind} {year}: {', '.join(printed)} printed as % of GDP, but there is "
                                "no GDP to check them against (no stated GDP or fiscal deficit %)")
            continue
        for field in DEFICITS:
            amount, pct = v.get(field, (None, None))
            if amount is None or pct is None:
                continue
            checked += 1
            calc = amount * 100 / base
            if abs(calc - pct) > tol:
                msg = (f"Budget {doc}, {kind} {year}: {field} printed {pct}% of GDP, "
                       f"but {amount:,.0f} / {base_name} = {calc:.2f}%")
                if not ok.file("pct", msg):
                    failures.append(msg)
    report.add("% of GDP figures agree with the amounts", checked, failures, allowed=ok)


def check_formats(report: Report) -> None:
    comparisons = json.loads((DATA / "format_comparison.json").read_text())
    failures, notes, checked, ok = [], [], 0, allowed()
    for c in comparisons:
        budget, primary = c["budget"], c["primary"]
        for ext, o in c["others"].items():
            checked += 1
            n = len(o["differences"])
            if n == 0:
                notes.append(f"Budget {budget}: {primary.upper()} and {ext.upper()} agree on all {o['compared']} values.")
                continue
            msg = f"Budget {budget}: {ext.upper()} differs from {primary.upper()} in {n} values"
            if not ok.file("format", msg):
                sample = "; ".join(f"{d['item']}: {d[primary]} vs {d[ext]}" for d in o["differences"][:3])
                failures.append(f"{msg} ({sample})")
        for ext, err in c["unparseable"].items():
            notes.append(f"Budget {budget}: {ext.upper()} copy could not be read ({err}).")
    report.add("Other copies of the same table (Excel/HTML) agree with the primary file", checked, failures, notes,
               ok)


def check_completeness(dataset: dict, report: Report) -> None:
    core = ["revenue_receipts", "tax_revenue_net", "non_tax_revenue", "capital_receipts", "recoveries_of_loans",
            "borrowings", "total_receipts", "total_expenditure", "revenue_expenditure", "interest_payments",
            "capital_expenditure", "revenue_deficit", "fiscal_deficit", "primary_deficit"]
    failures, checked, notes = [], 0, []
    latest = LATEST_BUDGET
    for start in range(FIRST_BUDGET, LATEST_BUDGET + 1):
        year = fy(start)
        entry = dataset["years"].get(year, {})
        need = ["be"] + (["re"] if start <= latest - 1 else []) + (["actual"] if start <= latest - 2 else [])
        for field in core:
            for kind in need:
                checked += 1
                if kind not in entry.get(field, {}):
                    failures.append(f"{year}: missing {kind.upper()} for {field}")
    notes.append(f"Not yet published: RE for {fy(latest)} (Budget {fy(latest + 1)}), "
                 f"Actuals for {fy(latest - 1)} and {fy(latest)}.")
    report.add("Every year has the figures it should", checked, failures, notes)


def check_reference(dataset: dict, report: Report) -> None:
    """Compare with the RBI Handbook series, an independent compilation of the same accounts."""
    rbi = load_rbi()
    failures, notes, checked, exact, ok = [], [], 0, 0, allowed()
    for (year, field, kind), ref in sorted(rbi.items()):
        if year < fy(FIRST_BUDGET):
            continue
        checked += 1
        ours = dataset["years"].get(year, {}).get(field, {}).get(kind)
        label = f"{kind.upper() if kind != 'actual' else 'Actual'} {year} {field}"
        if ours is None:
            failures.append(f"{label}: missing from our data (RBI: {ref['value']:,.0f})")
            continue
        diff = ours["value"] - ref["value"]
        if abs(diff) <= LEVEL_TOL:
            exact += 1
            continue
        rel = abs(diff) / max(abs(ref["value"]), 1)
        msg = f"{label}: ours {ours['value']:,.0f} vs RBI {ref['value']:,.0f} ({diff:+,.0f}, {rel:.2%})"
        if ok.file("rbi", msg):
            continue
        if rel <= RBI_SHARE_TOL and abs(diff) <= RBI_CRORE_TOL:
            ok.add(FINAL_ACCOUNTS, msg)
        else:
            failures.append(msg)
    notes.insert(0, f"{exact} of {checked} figures match the RBI series exactly (within Rs {LEVEL_TOL} crore).")
    report.add("Matches the RBI Handbook of Statistics (independent series)", checked, failures, notes, ok)


def check_jumps(dataset: dict, report: Report) -> None:
    """Flag very large year-on-year changes in actuals for a person to look at (not failures)."""
    notes = []
    years = sorted(dataset["years"])
    for field in ["revenue_receipts", "total_expenditure", "capital_expenditure", "interest_payments", "fiscal_deficit"]:
        prev = None
        for y in years:
            item = dataset["years"][y].get(field, {})
            val = (item.get("actual") or item.get("re") or item.get("be") or {}).get("value")
            if prev and val and abs(val / prev[1] - 1) > JUMP_SHARE:
                notes.append(f"{field}: {prev[0]} → {y} changed {val / prev[1] - 1:+.0%} ({prev[1]:,.0f} → {val:,.0f})")
            prev = (y, val) if val else prev
    report.add("Large year-on-year changes (for review, not failures)", 0, [], notes)


def area_exceptions() -> dict[str, Exceptions]:
    """Every list of known exceptions in the budget area, by the checks that use it."""
    from . import datasets, ministries, schemes, taxes

    return {"headline": EXCEPTIONS, "taxes": taxes.EXCEPTIONS, "ministries": ministries.EXCEPTIONS,
            "schemes": schemes.EXCEPTIONS, "schemes vs ministries": datasets.CROSSCHECK_EXCEPTIONS}


def check_unused_exceptions(report: Report, exceptions: dict[str, Exceptions] | None = None) -> None:
    """Known exceptions no message matched in this run (the source was corrected, or the message changed), for
    review, as in the gdp area. Run after every check: each group of checks resets its own list when it starts."""
    def show(check) -> str:
        return " / ".join(map(str, check)) if isinstance(check, tuple) else str(check)

    unused = [f"{name}: {show(c)}: {k}" for name, exc in (exceptions or area_exceptions()).items()
              for c, k in exc.unused()]
    if unused:
        report.add("Known exceptions no longer needed (for review: remove them)", 0, [], unused)


def main(detailed_sections: list[tuple] | None = None) -> int:
    """Run every check and write the report.

    detailed_sections: check results for the tax, ministry and scheme tables,
    as returned by datasets.build_all(): (title, checked, failures, notes,
    allowed or None). If not given, those tables are rebuilt here (slower) so
    the report is always complete.
    """
    if detailed_sections is None:
        from .datasets import build_all

        detailed_sections = build_all()
    rows = load_observations()
    dataset = json.loads((DATA / "fiscal.json").read_text())
    report = Report(INTRO)
    EXCEPTIONS.reset()
    check_identities(rows, report)
    check_cross_document(rows, report)
    check_pct_gdp(rows, dataset["gdp_stated_in_budget"], report)
    check_formats(report)
    check_completeness(dataset, report)
    check_reference(dataset, report)
    check_jumps(dataset, report)
    for title, checked, failures, notes, ok in detailed_sections:
        report.add(title, checked, failures, notes, ok)
    check_unused_exceptions(report)
    check_data_text(DATA, report)
    return report.write(DATA)


if __name__ == "__main__":
    pipeline_log.setup(__package__)
    sys.exit(main())

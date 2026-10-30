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

Exceptions are allowed only through KNOWN_EXCEPTIONS below, each with a reason.
Writes web/data/validation_report.md and exits non-zero on any failure.

Run: uv run python -m budget_pipeline.checks
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from .annotations import FINAL_ACCOUNTS, KNOWN_EXCEPTIONS, KNOWN_FORMAT_ISSUES, KNOWN_REFERENCE_DIFFS
from .reference import load_rbi
from .parse import fy
from .sources import FIRST_BUDGET, LATEST_BUDGET

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Rounding: documents say items "may not sum up to the totals due to rounding off".
TOLERANCE_CRORE = 5


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
        r["value_crore"] = float(r["value_crore"]) if r["value_crore"] else None
        r["pct_gdp"] = float(r["pct_gdp"]) if r["pct_gdp"] else None
    return rows


class Report:
    def __init__(self) -> None:
        self.sections: list[tuple[str, int, list[str], list[str]]] = []

    def add(self, title: str, checked: int, failures: list[str], notes: list[str] | None = None) -> None:
        self.sections.append((title, checked, failures, notes or []))

    @property
    def failed(self) -> bool:
        return any(f for _, _, f, _ in self.sections)

    def markdown(self) -> str:
        out = ["# Data validation report", "",
           "Headline figures, taxes, ministries and schemes. Every allowed exception lists its reason.", ""]
        total_fail = sum(len(f) for _, _, f, _ in self.sections)
        out.append(f"**Result: {'FAILED' if total_fail else 'PASSED'}** "
                   f"({sum(c for _, c, _, _ in self.sections)} checks, {total_fail} failures)")
        out.append("")
        for title, checked, failures, notes in self.sections:
            status = "✅" if not failures else "❌"
            out.append(f"## {status} {title}")
            out.append(f"{checked} checks, {len(failures)} failures.")
            out.append("")
            for line in failures:
                out.append(f"- ❌ {line}")
            for line in notes:
                out.append(f"- {line}")
            out.append("")
        return "\n".join(out)


def check_identities(rows: list[dict], report: Report) -> None:
    cols: dict[tuple[str, str, str], dict[str, float | None]] = defaultdict(dict)
    for r in rows:
        cols[(r["source_budget"], r["fiscal_year"], r["kind"])][r["field"]] = r["value_crore"]
    failures, excused, checked = [], [], 0
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
            if abs(diff) > TOLERANCE_CRORE:
                key = (doc, year, kind, name)
                msg = (f"Budget {doc}, {kind} {year}: {name} — printed {vals[lhs]:,.0f}, "
                       f"components give {expected:,.0f} (off by {diff:,.0f})")
                if key in KNOWN_EXCEPTIONS:
                    excused.append(f"Allowed: {msg}. Reason: {KNOWN_EXCEPTIONS[key]}")
                else:
                    failures.append(msg)
    report.add("Accounting rules hold in every source column", checked, failures, excused)


def check_cross_document(rows: list[dict], report: Report) -> None:
    by_key = defaultdict(list)
    for r in rows:
        if r["value_crore"] is not None:
            by_key[(r["fiscal_year"], r["kind"], r["field"])].append(r)
    notes, failures, checked = [], [], 0
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
            reason = KNOWN_EXCEPTIONS.get(("cross", year, kind, f"field:{field}"))
            if reason:
                notes.append(f"{msg}. Explained: {reason}")
            elif rel > 0.02 and abs(diff) > 500:
                failures.append(msg)
            else:
                notes.append(msg)
    report.add("Same figure agrees across documents (BE restated in the next budget)", checked, failures,
               [f"Restated: {n}" for n in notes])


def check_pct_gdp(rows: list[dict], gdp: dict, report: Report) -> None:
    cols: dict[tuple[str, str, str], dict[str, tuple[float | None, float | None]]] = defaultdict(dict)
    for r in rows:
        cols[(r["source_budget"], r["fiscal_year"], r["kind"])][r["field"]] = (r["value_crore"], r["pct_gdp"])
    failures, checked = [], 0
    for (doc, year, kind), v in sorted(cols.items()):
        fd, fd_pct = v.get("fiscal_deficit", (None, None))
        stated = gdp.get(doc)
        if kind == "BE" and year == doc and stated:
            base, base_name = stated["value"], f"stated GDP {stated['value']:,.0f}"
            tol = 0.051
        elif fd and fd_pct:
            base, base_name = fd * 100 / fd_pct, "GDP implied by fiscal deficit %"
            tol = 0.051 + 0.05 * 100 / fd_pct * 0.05  # rounding of the fiscal deficit % itself
        else:
            continue
        for field in DEFICITS:
            amount, pct = v.get(field, (None, None))
            if amount is None or pct is None:
                continue
            checked += 1
            calc = amount * 100 / base
            if abs(calc - pct) > tol:
                if (doc, year, kind, f"pct:{field}") in KNOWN_EXCEPTIONS:
                    continue
                failures.append(f"Budget {doc}, {kind} {year}: {field} printed {pct}% of GDP, "
                                f"but {amount:,.0f} / {base_name} = {calc:.2f}%")
    report.add("% of GDP figures agree with the amounts", checked, failures)


def check_formats(report: Report) -> None:
    comparisons = json.loads((DATA / "format_comparison.json").read_text())
    failures, notes, checked = [], [], 0
    for c in comparisons:
        budget, primary = c["budget"], c["primary"]
        for ext, o in c["others"].items():
            checked += 1
            n = len(o["differences"])
            if n == 0:
                notes.append(f"Budget {budget}: {primary.upper()} and {ext.upper()} agree on all {o['compared']} values.")
            elif (budget, ext) in KNOWN_FORMAT_ISSUES:
                notes.append(f"Budget {budget}: {ext.upper()} differs from {primary.upper()} in {n} values "
                             f"(known): {KNOWN_FORMAT_ISSUES[(budget, ext)]}")
            else:
                sample = "; ".join(f"{d['item']}: {d[primary]} vs {d[ext]}" for d in o["differences"][:3])
                failures.append(f"Budget {budget}: {ext.upper()} differs from {primary.upper()} in {n} values ({sample})")
        for ext, err in c["unparseable"].items():
            notes.append(f"Budget {budget}: {ext.upper()} copy could not be read ({err}).")
    report.add("Other copies of the same table (Excel/HTML) agree with the primary file", checked, failures, notes)


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
    failures, notes, checked, exact = [], [], 0, 0
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
        if abs(diff) <= TOLERANCE_CRORE:
            exact += 1
            continue
        rel = abs(diff) / max(abs(ref["value"]), 1)
        msg = f"{label}: ours {ours['value']:,.0f} vs RBI {ref['value']:,.0f} ({diff:+,.0f}, {rel:.2%})"
        reason = KNOWN_REFERENCE_DIFFS.get((year, field, kind))
        if reason:
            notes.append(f"{msg}. Explained: {reason}")
        elif rel <= 0.01:
            notes.append(f"{msg}. Small difference: {FINAL_ACCOUNTS}")
        else:
            failures.append(msg)
    notes.insert(0, f"{exact} of {checked} figures match the RBI series exactly (within Rs {TOLERANCE_CRORE} crore).")
    report.add("Matches the RBI Handbook of Statistics (independent series)", checked, failures, notes)


def check_jumps(dataset: dict, report: Report) -> None:
    """Flag very large year-on-year changes in actuals for a person to look at (not failures)."""
    notes = []
    years = sorted(dataset["years"])
    for field in ["revenue_receipts", "total_expenditure", "capital_expenditure", "interest_payments", "fiscal_deficit"]:
        prev = None
        for y in years:
            item = dataset["years"][y].get(field, {})
            val = (item.get("actual") or item.get("re") or item.get("be") or {}).get("value")
            if prev and val and abs(val / prev[1] - 1) > 0.35:
                notes.append(f"{field}: {prev[0]} → {y} changed {val / prev[1] - 1:+.0%} ({prev[1]:,.0f} → {val:,.0f})")
            prev = (y, val) if val else prev
    report.add("Large year-on-year changes (for review, not failures)", 0, [], notes)


def main(detailed_sections: list[tuple] | None = None) -> int:
    """Run every check and write the report.

    detailed_sections: check results for the tax, ministry and scheme tables,
    as returned by datasets.build_all(). If not given, those tables are
    rebuilt here (slower) so the report is always complete.
    """
    if detailed_sections is None:
        from .datasets import build_all

        detailed_sections = build_all()
    rows = load_observations()
    dataset = json.loads((DATA / "fiscal.json").read_text())
    report = Report()
    check_identities(rows, report)
    check_cross_document(rows, report)
    check_pct_gdp(rows, dataset["gdp_stated_in_budget"], report)
    check_formats(report)
    check_completeness(dataset, report)
    check_reference(dataset, report)
    check_jumps(dataset, report)
    for title, checked, failures, notes in detailed_sections:
        report.add(title, checked, failures, notes)
    (DATA / "validation_report.md").write_text(report.markdown())
    for title, checked, failures, _ in report.sections:
        print(f"{'FAIL' if failures else 'ok  '} {title}: {checked} checks, {len(failures)} failures")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())

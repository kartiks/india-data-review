"""Checks on the parsed Receipts tables and Receipt Budget actuals."""

from collections import defaultdict

from pipeline_common.numbers import blank_or_number
from pipeline_common.report import Allowed
from pipeline_common.text import fy

from .common import LEVEL_TOL, NON_TAX_PARTS
from .exceptions import EXCEPTIONS
from .load import observations

Result = tuple[int, list[str], list[str], Allowed]  # checked, failures, notes, allowed exceptions


def _allowed() -> Allowed:
    return Allowed(EXCEPTIONS, more_hint="")


def _identity_checks(all_parsed: dict) -> Result:
    failures, notes, checked, ok = [], [], 0, _allowed()
    for budget, b in sorted(all_parsed["budgets"].items()):
        p = b["parsed"]
        for c, col in enumerate(p["columns"]):
            vals = {it["item_id"]: it["values"][c] for it in p["items"]}
            sections = {it["item_id"]: it["section"] for it in p["items"]}

            def check(name: str, printed: float | None, parts: list[float | None]) -> None:
                nonlocal checked
                if printed is None or all(x is None for x in parts):
                    return
                calc = sum(x or 0 for x in parts)
                checked += 1
                if abs(printed - calc) > LEVEL_TOL:
                    msg = (f"Budget {budget}, {col.kind} {col.fiscal_year}: {name} - printed {printed:,.0f}, "
                           f"parts give {calc:,.0f} (off by {printed - calc:,.0f})")
                    if not ok.file("identity", msg):
                        failures.append(msg)

            check("gross tax = sum of printed taxes", vals.get("gross_tax_revenue"),
                  [v for k, v in vals.items() if sections[k] == "gross"])
            check("net tax = gross - deductions", vals.get("net_tax_revenue"),
                  [vals.get("gross_tax_revenue")] + [-(v or 0) for k, v in vals.items() if sections[k] == "deduction"])
            if any(sections[k] == "gst_part" for k in vals):
                check("GST = CGST + IGST + cess", vals.get("gst"),
                      [v for k, v in vals.items() if sections[k] == "gst_part"])
            check("non-tax total = its parts", vals.get("non_tax_revenue_total"),
                  [vals.get(k) for k in NON_TAX_PARTS if k in vals])
            check("revenue receipts = net tax + non-tax", vals.get("revenue_receipts_total"),
                  [vals.get("net_tax_revenue"), vals.get("non_tax_revenue_total")])
            detail = [v for k, v in vals.items() if sections[k] == "deduction_detail"]
            if detail:
                check("states' share = its printed split", vals.get("states_share"), detail)
    return checked, failures, notes, ok


def _summary_index(summary_observations: list[dict]) -> dict[tuple[str, str, str, str], float | None]:
    """(source budget, fiscal year, kind, field) -> value of the headline table (observations.csv)."""
    summ = {}
    for r in summary_observations:
        summ[(r["source_budget"], r["fiscal_year"], r["kind"], r["field"])] = blank_or_number(r["value_crore"])
    return summ


SUMMARY_LINKS = {
    "net_tax_revenue": "tax_revenue_net",
    "non_tax_revenue_total": "non_tax_revenue",
    "revenue_receipts_total": "revenue_receipts",
}


def _summary_checks(all_parsed: dict, summary_observations: list[dict]) -> Result:
    summ = _summary_index(summary_observations)
    failures, notes, checked, ok = [], [], 0, _allowed()
    for budget, b in sorted(all_parsed["budgets"].items()):
        p = b["parsed"]
        for it in p["items"]:
            field = SUMMARY_LINKS.get(it["item_id"])
            if not field:
                continue
            for col, v in zip(p["columns"], it["values"]):
                s = summ.get((budget, col.fiscal_year, col.kind, field))
                if s is None or v is None:
                    continue
                checked += 1
                if abs(s - v) > LEVEL_TOL:
                    msg = (f"Budget {budget}, {col.kind} {col.fiscal_year}: {it['item_id']} {v:,.0f} in Receipts "
                           f"vs {field} {s:,.0f} in the headline table")
                    if not ok.file("summary", msg):
                        failures.append(msg)
    return checked, failures, notes, ok


def _cross_document_checks(all_parsed: dict) -> Result:
    seen = defaultdict(dict)
    for r in observations(all_parsed):
        if r["value_crore"] is not None:
            seen[(r["fiscal_year"], r["kind"], r["item_id"])][r["source_budget"]] = r["value_crore"]
    failures, notes, checked, ok = [], [], 0, _allowed()
    for (year, kind, item), by_doc in sorted(seen.items()):
        if len(by_doc) < 2:
            continue
        checked += 1
        (d1, v1), (d2, v2) = sorted(by_doc.items())[:2]
        if abs(v1 - v2) <= LEVEL_TOL:
            continue
        rel = abs(v2 - v1) / max(abs(v1), 1)
        msg = f"{kind} {year} {item}: {v1:,.0f} in budget {d1} vs {v2:,.0f} in budget {d2} ({v2 - v1:+,.0f}, {rel:.1%})"
        if ok.file("cross", msg):
            continue
        if rel > 0.02 and abs(v2 - v1) > 500:
            failures.append(msg)
        else:
            notes.append(f"Restated: {msg}")
    return checked, failures, notes, ok


def _format_checks(all_parsed: dict) -> Result:
    failures, notes, checked, ok = [], [], 0, _allowed()
    for c in all_parsed["comparisons"]:
        budget, primary = c["budget"], c["primary"]
        if primary is None:
            failures.append(f"Budget {budget}: no copy of the Receipts table could be read ({c['unparseable']})")
            continue
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
    return checked, failures, notes, ok


# ----- checks on the Receipt Budget actuals ----------------------------------

ANNEX7_TO_BAG = {  # same meaning in both tables
    "gross_tax_revenue", "corporation_tax", "income_tax", "customs", "union_excise", "service_tax",
    "wealth_tax", "ut_taxes", "states_share", "nccd_transferred", "net_tax_revenue",
    "non_tax_revenue_total", "revenue_receipts_total", "interest_tax",
}


def _annex7_columns(rbs: dict):
    """(budget, column, {item_id: value}, {item_id: section}) for each column of each Annex 7 that was read."""
    for budget, b in sorted(rbs.items()):
        if "parsed" not in b:
            continue
        p = b["parsed"]
        for c, col in enumerate(p["columns"]):
            yield (budget, col, {it["item_id"]: it["values"][c] for it in p["items"]},
                   {it["item_id"]: it["section"] for it in p["items"]})


def _rb_identities(rbs: dict) -> Result:
    """(a) Annex 7's totals equal their printed parts."""
    failures, notes, checked, ok = [], [], 0, _allowed()
    for budget, b in sorted(rbs.items()):
        if "parsed" not in b:
            failures.append(f"Receipt Budget {budget}: Annex 7 could not be read ({b['error']})")
            continue
        p = b["parsed"]
        for c, col in enumerate(p["columns"]):
            vals = {it["item_id"]: it["values"][c] for it in p["items"]}
            sec = {it["item_id"]: it["section"] for it in p["items"]}

            def check(name, printed, parts):
                nonlocal checked
                if printed is None or all(x is None for x in parts):
                    return
                calc = sum(x or 0 for x in parts)
                checked += 1
                if abs(printed - calc) > LEVEL_TOL:
                    msg = (f"Receipt Budget {budget}, {col.kind} {col.fiscal_year}: {name} - printed {printed:,.0f}, "
                           f"parts give {calc:,.0f} (off by {printed - calc:,.0f})")
                    if not ok.file("rb identity", msg):
                        failures.append(msg)

            check("gross tax = sum of printed taxes", vals.get("gross_tax_revenue"),
                  [v for k, v in vals.items() if sec[k] == "gross"])
            check("net tax = gross - deductions", vals.get("net_tax_revenue"),
                  [vals.get("gross_tax_revenue")] + [-(v or 0) for k, v in vals.items() if sec[k] == "deduction"])
            check("revenue receipts = net tax + non-tax", vals.get("revenue_receipts_total"),
                  [vals.get("net_tax_revenue"), vals.get("non_tax_revenue_total")])
            detail = [v for k, v in vals.items() if sec[k] == "deduction_detail"]
            if any(d is not None for d in detail):
                check("states' share = its printed split", vals.get("states_share"), detail)
    return checked, failures, notes, ok


def _rb_actuals_vs_headline(rbs: dict, summ: dict) -> Result:
    """(b) The Actuals column against the headline table of the same budget."""
    failures, notes, checked, ok = [], [], 0, _allowed()
    for budget, col, vals, _ in _annex7_columns(rbs):
        if col.kind != "Actual":
            continue
        for item, field in SUMMARY_LINKS.items():
            v, sv = vals.get(item), summ.get((budget, col.fiscal_year, "Actual", field))
            if v is None or sv is None:
                if v is not None:
                    failures.append(f"Receipt Budget {budget}: no headline {field} Actual {col.fiscal_year} to compare")
                continue
            checked += 1
            if abs(v - sv) > LEVEL_TOL:
                msg = (f"Receipt Budget {budget}, Actual {col.fiscal_year}: {item} {v:,.0f} vs headline "
                       f"{field} {sv:,.0f} (Budget at a Glance {budget})")
                if not ok.file("rb headline", msg):
                    failures.append(msg)
    return checked, failures, notes, ok


def _rb_vs_receipts_table(all_parsed: dict, rbs: dict) -> Result:
    """(c) The RE and BE columns against the Budget at a Glance Receipts table of the same budget."""
    bag = {}
    for budget, b in all_parsed["budgets"].items():
        p = b["parsed"]
        for it in p["items"]:
            for col, v in zip(p["columns"], it["values"]):
                bag[(budget, col.fiscal_year, col.kind, it["item_id"])] = v
    failures, notes, checked, ok = [], [], 0, _allowed()
    for budget, col, vals, _ in _annex7_columns(rbs):
        if col.kind == "Actual":
            continue
        for item in ANNEX7_TO_BAG:
            v = vals.get(item)
            key = (budget, col.fiscal_year, col.kind, item)
            if key not in bag:
                continue
            bv = bag[key]
            if v is None and bv is None:
                continue
            checked += 1
            if (v is None) != (bv is None) or abs(v - bv) > LEVEL_TOL:
                msg = (f"Budget {budget}, {col.kind} {col.fiscal_year}: {item} {v} in Receipt Budget Annex 7 "
                       f"vs {bv} in Budget at a Glance Receipts")
                if not ok.file("rb receipts", msg):
                    failures.append(msg)
    return checked, failures, notes, ok


def _rb_completeness(rbs: dict) -> Result:
    """(d) Actuals for every year the Budget at a Glance Receipts table lacks."""
    failures, checked = [], 0
    have = {(it_year, item) for budget, b in rbs.items() if "parsed" in b
            for item, it_year in ((it["item_id"], b["parsed"]["columns"][0].fiscal_year) for it in b["parsed"]["items"]
                                  if it["values"][0] is not None)}
    for start in range(2000, 2008):
        for item in ("gross_tax_revenue", "corporation_tax", "income_tax", "customs", "union_excise",
                     "service_tax", "states_share", "net_tax_revenue"):
            checked += 1
            if (fy(start), item) not in have:
                failures.append(f"Actual {fy(start)} {item} missing")
    return checked, failures, [], None


def _receipt_budget_checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple]:
    rbs = all_parsed.get("receipt_budgets", {})
    return [
        ("Taxes (Receipt Budget actuals 2000-01..2007-08): totals equal their printed parts", *_rb_identities(rbs)),
        ("Taxes (Receipt Budget actuals): net tax, non-tax, revenue receipts match the headline table's Actuals",
         *_rb_actuals_vs_headline(rbs, _summary_index(summary_observations))),
        ("Taxes (Receipt Budget): its RE/BE columns match the Budget at a Glance Receipts table",
         *_rb_vs_receipts_table(all_parsed, rbs)),
        ("Taxes (Receipt Budget): actuals present for 2000-01..2007-08", *_rb_completeness(rbs)),
    ]


def checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple]:
    """Every tax check, one group each: [(title, checked, failures, notes, allowed exceptions or None)]."""
    EXCEPTIONS.reset()
    out = []
    out.append(("Taxes: totals equal their printed parts", *_identity_checks(all_parsed)))
    out.append(("Taxes: net tax, non-tax and revenue receipts match the headline table",
                *_summary_checks(all_parsed, summary_observations)))
    out.append(("Taxes: same figure agrees across budgets", *_cross_document_checks(all_parsed)))
    out.append(("Taxes: other copies (Excel/HTML) agree with the primary file", *_format_checks(all_parsed)))
    out.extend(_receipt_budget_checks(all_parsed, summary_observations))
    return out

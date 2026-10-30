"""Parse every downloaded document and write the dataset.

Outputs (in budget/data/):
- observations.csv : every number read from every document, with its source.
                     Most figures appear in two documents; both are kept.
- fiscal.json      : one value per (year, line item, estimate type), chosen by
                     the rules below, each with its source.

Which document a figure is taken from:
- BE (Budget Estimate) for year Y: the budget presented for Y (what was announced).
- RE (Revised Estimate) for Y: the budget for Y+1 (the only place it appears).
- Actual for Y: the budget for Y+2 (latest published figure).
The BE as restated in the next year's budget is kept as `be_restated` when it
differs, since it is the like-for-like comparison with RE.

Run: uv run python -m budget_pipeline.build
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .annotations import HEADER_FIXES, SOURCE_NOTES
from .parse import FIELD_PATTERNS, ParseError, fy, parse_document
from .readers import read_any
from .sources import FIRST_BUDGET, FORMAT_PRIORITY, LATEST_BUDGET

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "manifest.json"

FIELD_LABELS = {
    "revenue_receipts": "Revenue receipts",
    "tax_revenue_net": "Tax revenue (net to Centre)",
    "non_tax_revenue": "Non-tax revenue",
    "capital_receipts": "Capital receipts",
    "recoveries_of_loans": "Recoveries of loans",
    "other_receipts": "Other receipts (mainly disinvestment)",
    "borrowings": "Borrowings and other liabilities",
    "total_receipts": "Total receipts",
    "total_expenditure": "Total expenditure",
    "revenue_expenditure": "Revenue expenditure",
    "interest_payments": "Interest payments",
    "grants_capital_assets": "Grants for creation of capital assets",
    "capital_expenditure": "Capital expenditure",
    "effective_capital_expenditure": "Effective capital expenditure",
    "revenue_deficit": "Revenue deficit",
    "effective_revenue_deficit": "Effective revenue deficit",
    "fiscal_deficit": "Fiscal deficit",
    "primary_deficit": "Primary deficit",
}
assert set(FIELD_LABELS) == {f for f, _ in FIELD_PATTERNS}


def parse_all() -> tuple[list[dict], dict, list[dict]]:
    """Parse every file. Returns (observations from each year's primary file, GDP notes, format comparisons)."""
    manifest = json.loads(MANIFEST.read_text())
    rows: list[dict] = []
    gdp: dict[str, dict] = {}
    comparisons: list[dict] = []
    for doc_year, entry in manifest.items():
        start = int(doc_year[:4])
        parsed_by_format: dict[str, dict] = {}
        errors: dict[str, str] = {}
        for ext in FORMAT_PRIORITY:
            f = entry["summary"]["files"].get(ext)
            if not f:
                continue
            try:
                rows_in = read_any(ROOT / f["file"])
                for printed, corrected in HEADER_FIXES.get((doc_year, ext), []):
                    rows_in = [[c.replace(printed, corrected) for c in r] for r in rows_in]
                parsed_by_format[ext] = parse_document(rows_in, start, ext != "pdf")
            except ParseError as exc:
                errors[ext] = str(exc)
        if not parsed_by_format:
            raise ParseError(f"{doc_year}: no file could be parsed: {errors}")
        primary = next(ext for ext in FORMAT_PRIORITY if ext in parsed_by_format)
        parsed = parsed_by_format[primary]
        src = entry["summary"]["files"][primary]
        comparisons.append(compare_formats(doc_year, primary, parsed_by_format, errors))
        for o in parsed["observations"]:
            rows.append(
                {
                    "fiscal_year": o.fiscal_year,
                    "kind": o.kind,
                    "field": o.field,
                    "value_crore": o.value,
                    "pct_gdp": o.pct_gdp,
                    "source_budget": doc_year,
                    "label_as_printed": o.label_as_printed,
                    "source_url": src["url"],
                    "source_sha256": src["sha256"],
                }
            )
        if parsed["gdp"]:
            gdp[doc_year] = {**parsed["gdp"], "source_budget": doc_year, "source_url": src["url"]}
    return rows, gdp, comparisons


def compare_formats(doc_year: str, primary: str, parsed: dict[str, dict], errors: dict[str, str]) -> dict:
    """Compare the primary file's numbers with the same table in other formats."""
    base = {(o.field, o.fiscal_year, o.kind): o for o in parsed[primary]["observations"]}
    result = {"budget": doc_year, "primary": primary, "others": {}, "unparseable": errors}
    for ext, p in parsed.items():
        if ext == primary:
            continue
        diffs = []
        other = {(o.field, o.fiscal_year, o.kind): o for o in p["observations"]}
        for key in sorted(set(base) | set(other)):
            a, b = base.get(key), other.get(key)
            av = a.value if a else None
            bv = b.value if b else None
            ap = a.pct_gdp if a else None
            bp = b.pct_gdp if b else None
            if (av is None) != (bv is None) or (av is not None and abs(av - bv) > 1):
                diffs.append({"item": key, primary: av, ext: bv})
            elif ap is not None and bp is not None and abs(ap - bp) > 0.05:
                diffs.append({"item": key + ("% of GDP",), primary: ap, ext: bp})
        result["others"][ext] = {"compared": len(set(base) | set(other)), "differences": diffs}
    return result


def choose(rows: list[dict]) -> dict:
    """Pick one value per (year, field, kind) following the rules in the module docstring."""
    idx = {(r["fiscal_year"], r["field"], r["kind"], r["source_budget"]): r for r in rows}
    years = [fy(y) for y in range(FIRST_BUDGET, LATEST_BUDGET + 1)]
    out: dict = {}
    for i, year in enumerate(years):
        start = FIRST_BUDGET + i
        entry: dict = {}
        for field in FIELD_LABELS:
            item: dict = {}
            be = idx.get((year, field, "BE", fy(start)))
            restated = idx.get((year, field, "BE", fy(start + 1)))
            re_ = idx.get((year, field, "RE", fy(start + 1)))
            actual = idx.get((year, field, "Actual", fy(start + 2)))
            for key, r in (("be", be), ("re", re_), ("actual", actual)):
                if r is not None and r["value_crore"] is not None:
                    item[key] = {
                        "value": r["value_crore"],
                        "pct_gdp": r["pct_gdp"],
                        "source_budget": r["source_budget"],
                        "label_as_printed": r["label_as_printed"],
                    }
                    note = SOURCE_NOTES.get((r["source_budget"], year, r["kind"], field))
                    if note:
                        item[key]["note"] = note
            if be and restated and restated["value_crore"] is not None and restated["value_crore"] != be["value_crore"]:
                item["be_restated"] = {
                    "value": restated["value_crore"],
                    "pct_gdp": restated["pct_gdp"],
                    "source_budget": restated["source_budget"],
                }
                note = SOURCE_NOTES.get((restated["source_budget"], year, "BE", field))
                if note:
                    item["be_restated"]["note"] = note
            if item:
                entry[field] = item
        out[year] = entry
    return out


def main() -> None:
    rows, gdp, comparisons = parse_all()
    DATA.mkdir(exist_ok=True)
    with (DATA / "observations.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["fiscal_year"], r["field"], r["source_budget"], r["kind"])))
    manifest = json.loads(MANIFEST.read_text())
    dataset = {
        "description": "Union Government of India: headline budget figures (Budget at a Glance), in Rs crore.",
        "units": "Rs crore; pct_gdp is the percentage of GDP as printed in the source",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fields": FIELD_LABELS,
        "sources": {k: v["summary"]["files"] for k, v in manifest.items()},
        "reference_sources": json.loads((ROOT / "sources" / "reference" / "manifest.json").read_text()),
        "gdp_stated_in_budget": gdp,
        "years": choose(rows),
    }
    (DATA / "format_comparison.json").write_text(json.dumps(comparisons, indent=1, default=list) + "\n")
    (DATA / "fiscal.json").write_text(json.dumps(dataset, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} observations and {len(dataset['years'])} years")


if __name__ == "__main__":
    main()

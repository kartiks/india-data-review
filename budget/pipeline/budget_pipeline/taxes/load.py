"""Parsing every copy of every year's Receipts table, the long-format observations, and the headline figures the
checks compare with."""

import csv
import json
from pathlib import Path

from pipeline_common.text import fy_start

from ..parse import ParseError
from ..readers import read_any
from ..sources import FORMAT_PRIORITY, documents
from .annex7 import load_receipt_budgets
from .common import DATA, MANIFEST, ROOT
from .exceptions import HEADER_FIXES
from .receipts import parse_receipts


def load_all() -> dict:
    """Parse every copy of every year's Receipts table.

    Returns {"budgets": {budget: {"primary": ext, "url", "sha256", "parsed": {...}}},
             "comparisons": [{"budget", "primary", "others": {ext: {...}}, "unparseable": {...}}]}
    """
    manifest = documents(json.loads(MANIFEST.read_text()))
    budgets: dict[str, dict] = {}
    comparisons: list[dict] = []
    for budget, entry in manifest.items():
        files = entry.get("receipts", {})
        start = fy_start(budget)
        parsed: dict[str, dict] = {}
        errors: dict[str, str] = {}
        for ext in FORMAT_PRIORITY:
            if ext not in files:
                continue
            try:
                rows = read_any(ROOT / files[ext]["file"])
                for printed, corrected in HEADER_FIXES.get((budget, ext), []):
                    rows = [[c.replace(printed, corrected) for c in r] for r in rows]
                parsed[ext] = parse_receipts(rows, start, ext != "pdf")
            except ParseError as exc:
                errors[ext] = str(exc)
        if not parsed:
            comparisons.append({"budget": budget, "primary": None, "others": {}, "unparseable": errors})
            continue
        primary = next(e for e in FORMAT_PRIORITY if e in parsed)
        budgets[budget] = {
            "primary": primary,
            "url": files[primary]["url"],
            "sha256": files[primary]["sha256"],
            "parsed": parsed[primary],
        }
        comparisons.append(_compare(budget, primary, parsed, errors))
    return {"budgets": budgets, "comparisons": comparisons, "receipt_budgets": load_receipt_budgets()}


def _flatten(parsed: dict) -> dict[tuple[str, str, str], float | None]:
    out = {}
    for it in parsed["items"]:
        for col, v in zip(parsed["columns"], it["values"]):
            out[(it["item_id"], col.fiscal_year, col.kind)] = v
    return out


def _compare(budget: str, primary: str, parsed: dict[str, dict], errors: dict[str, str]) -> dict:
    base = _flatten(parsed[primary])
    result = {"budget": budget, "primary": primary, "others": {}, "unparseable": errors}
    for ext, p in parsed.items():
        if ext == primary:
            continue
        other = _flatten(p)
        diffs = []
        for key in sorted(set(base) | set(other)):
            a, b = base.get(key), other.get(key)
            if (a is None) != (b is None) or (a is not None and abs(a - b) > 1):
                diffs.append({"item": list(key), primary: a, ext: b})
        result["others"][ext] = {"compared": len(set(base) | set(other)), "differences": diffs}
    return result


def observations(all_parsed: dict) -> list[dict]:
    """Long-format rows (like observations.csv) for every value in every primary table,
    plus the 2000-01..2007-08 actuals from the Receipt Budget (document="receipt_budget")."""
    rows = []
    for budget, b in sorted(all_parsed["budgets"].items()):
        p = b["parsed"]
        for it in p["items"]:
            for col, v in zip(p["columns"], it["values"]):
                rows.append(
                    {
                        "fiscal_year": col.fiscal_year,
                        "kind": col.kind,
                        "item_id": it["item_id"],
                        "section": it["section"],
                        "value_crore": v,
                        "source_budget": budget,
                        "document": "receipts",
                        "label_as_printed": it["label_as_printed"],
                        "source_url": b["url"],
                        "source_sha256": b["sha256"],
                    }
                )
    for budget, b in sorted(all_parsed.get("receipt_budgets", {}).items()):
        if "parsed" not in b:
            continue
        p = b["parsed"]
        for it in p["items"]:
            col, v = p["columns"][0], it["values"][0]  # the Actuals column only
            rows.append(
                {
                    "fiscal_year": col.fiscal_year,
                    "kind": col.kind,
                    "item_id": it["item_id"],
                    "section": it["section"],
                    "value_crore": v,
                    "source_budget": budget,
                    "document": "receipt_budget",
                    "label_as_printed": it["label_as_printed"],
                    "source_url": b["url"],
                    "source_sha256": b["sha256"],
                }
            )
    return rows


def load_summary_observations(path: Path | None = None) -> list[dict]:
    with (path or DATA / "observations.csv").open() as f:
        return list(csv.DictReader(f))

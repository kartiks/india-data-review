"""Parsing every budget's statement in every format, and the long-format observations."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline_common.text import fy_start

from ..parse import ParseError
from ..readers import read_any
from ..sources import FORMAT_PRIORITY, documents
from .common import MANIFEST, ROOT
from .ids import assign_ids, load_name_map
from .read import read_pdf_lines
from .table import parse_ministries


def parse_file(path: Path, start: int, ext: str) -> dict:
    if ext == "pdf":
        return parse_ministries(None, start, False, lines=read_pdf_lines(path))
    return parse_ministries(read_any(path), start, True)


def load_all() -> dict:
    """Parse every budget's ministries table in every format.

    Returns {budget: {"primary": ext, "parsed": {ext: parsed}, "errors": {ext: msg},
    "sources": {ext: manifest entry}}}. The primary file is the first parseable one in
    sources.FORMAT_PRIORITY (the PDF, wherever it exists).
    """
    manifest = documents(json.loads(MANIFEST.read_text()))
    name_map = load_name_map()
    out = {}
    for budget, entry in manifest.items():
        files = entry.get("ministries", {})
        start = fy_start(budget)
        parsed, errors = {}, {}
        for ext in FORMAT_PRIORITY:
            if ext not in files:
                continue
            try:
                p = parse_file(ROOT / files[ext]["file"], start, ext)
                assign_ids(budget, p, name_map)
                parsed[ext] = p
            except (ParseError, KeyError) as exc:
                errors[ext] = str(exc)
        primary = next((e for e in FORMAT_PRIORITY if e in parsed), None)
        if primary is None:
            raise ParseError(f"Budget {budget}: no ministries file could be parsed: {errors}")
        out[budget] = {"primary": primary, "parsed": parsed, "errors": errors, "sources": files}
    return out


def observations(all_parsed: dict) -> list[dict]:
    """Flatten the primary file of each budget into one row per line x column."""
    rows = []
    for budget, b in all_parsed.items():
        p = b["parsed"][b["primary"]]
        src = b["sources"][b["primary"]]
        for it in p["items"]:
            for c, col in enumerate(p["columns"]):
                v = it["periods"][c]
                row = {
                    "source_budget": budget,
                    "fiscal_year": col.fiscal_year,
                    "kind": col.kind,
                    "item_id": it["item_id"],
                    "level": it["level"],
                    "section": it.get("section"),
                    "department_name": it.get("department_name"),
                    "ministry_id": it.get("ministry_id"),
                    "ministry_name": it.get("ministry_name"),
                    "demand_no": it.get("demand_no"),
                    "label_as_printed": it["label_as_printed"],
                    "total_crore": v["total"],
                    "plan_crore": v.get("plan"),
                    "non_plan_crore": v.get("non_plan"),
                    "revenue_crore": v.get("revenue"),
                    "capital_crore": v.get("capital"),
                    "source_url": src["url"],
                    "source_sha256": src["sha256"],
                }
                if "revenue_line" in it:  # Plan-era tables: revenue/capital come from the sub-lines
                    row["revenue_crore"] = it["revenue_line"][c]["total"]
                    row["capital_crore"] = it["capital_line"][c]["total"]
                for cat, per in it.get("subs", {}).items():
                    row[f"{cat}_crore"] = per[c]["total"]
                rows.append(row)
    return rows

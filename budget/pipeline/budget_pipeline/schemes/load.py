"""Parsing every copy of both statements for every budget, and comparing the copies."""

import json
from pathlib import Path

from pipeline_common.text import fy

from ..parse import ParseError
from ..sources import FIRST_SCHEME_BUDGET, FORMAT_PRIORITY, LATEST_BUDGET, documents
from .common import LEVEL_TOL, MANIFEST, PARTS, ROOT, SCHEME_TYPES
from .items import parse_schemes


def parse_file(path: Path, start: int, scheme_type: str) -> dict:
    return parse_schemes(path, start, path.suffix.lower() != ".pdf", scheme_type)


def _key(i: dict) -> tuple:
    if i["level"] == "component":
        return ("component", i["parent"], i["number"])
    return (i["level"], i["number"] if i["level"] != "grand_total" else "")


def compare(primary: dict, other: dict) -> list[dict]:
    """Differences between two copies of the same statement (only periods both have)."""
    a = {_key(i): i for i in primary["items"]}
    b = {_key(i): i for i in other["items"]}
    diffs = []
    shared_periods = [p for p in other["periods_present"] if p in primary["periods_present"]]
    period_keys = [(primary["columns"][p].fiscal_year, primary["columns"][p].kind) for p in shared_periods]
    for k in sorted(set(a) | set(b), key=str):
        ia, ib = a.get(k), b.get(k)
        if ia is None or ib is None:
            # A spreadsheet that only has the new BE leaves out schemes with no BE; that's fine.
            src = ia or ib
            if ib is None and len(shared_periods) < 4:
                if all((src["values"][pk]["total"] or 0) == 0 for pk in period_keys):
                    continue
            diffs.append({"item": k, "label": src["label_as_printed"], "issue": "only in " + ("primary" if ib is None else "other")})
            continue
        for pk in period_keys:
            for part in PARTS:
                va = ia["values"][pk][part] or 0.0
                vb = ib["values"][pk][part] or 0.0
                if abs(va - vb) > LEVEL_TOL:
                    diffs.append({"item": k, "label": ia["label_as_printed"], "period": pk, "part": part,
                                  "primary": va, "other": vb})
    return diffs


def load_all() -> dict:
    """Parse every copy of both statements for every budget from 2017-18.

    Returns {"budgets": {year: {scheme_type: {"primary": ext, "parsed": result,
    "differences": {ext: [...]}, "errors": {ext: msg}, "source": manifest entry}}}}.
    """
    manifest = documents(json.loads(MANIFEST.read_text()))
    out: dict = {"budgets": {}}
    for start in range(FIRST_SCHEME_BUDGET, LATEST_BUDGET + 1):
        year = fy(start)
        for t in SCHEME_TYPES:
            files = manifest.get(year, {}).get(t, {})
            parsed, errors = {}, {}
            for ext in FORMAT_PRIORITY:
                if ext not in files:
                    continue
                try:
                    parsed[ext] = parse_file(ROOT / files[ext]["file"], start, t)
                except ParseError as exc:
                    errors[ext] = str(exc)
            entry = {"primary": None, "parsed": None, "differences": {}, "errors": errors,
                     "source": files}
            if parsed:
                primary = next(e for e in FORMAT_PRIORITY if e in parsed)
                entry["primary"] = primary
                entry["parsed"] = parsed[primary]
                for ext, p in parsed.items():
                    if ext != primary:
                        entry["differences"][ext] = compare(parsed[primary], p)
            out["budgets"].setdefault(year, {})[t] = entry
    return out

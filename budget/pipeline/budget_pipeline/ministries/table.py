"""Parsing one statement's lines: header, columns, and the lines of each department or Demand."""

from __future__ import annotations

import re
from collections import defaultdict

from ..parse import Column, ParseError, fy
from .common import CATEGORIES, FURNITURE, NA, YEAR_RE, Line
from .read import _cell_lines


def detect_header(lines: list[Line], start: int) -> tuple[list[Column], list[str]]:
    """Columns (periods) and the sub-columns within each period."""
    text = " ".join(line.label + " " + " ".join(t for t, _ in line.values) for line in lines[:40])
    low = text.lower()
    if re.search(r"plan\s+non-?\s*plan\s+total", low):
        subs = ["plan", "non_plan", "total"]
    elif re.search(r"revenue\s+capital\s+total", low):
        subs = ["revenue", "capital", "total"]
    else:
        raise ParseError(f"{fy(start)} ministries: sub-columns not recognised")
    years = [int(m.group(1)) for m in YEAR_RE.finditer(text)]
    kinds = re.findall(r"actuals|budget|revised", low)
    three = ([start - 2, start - 1, start], ["Actual", "RE", "BE"])
    four = ([start - 2, start - 1, start - 1, start], ["Actual", "BE", "RE", "BE"])

    def contains(seq, sub):
        return any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))

    want_kinds = {"Actual": "actuals", "BE": "budget", "RE": "revised"}
    for ys, ks in (four, three):
        if contains(years, ys) and contains(kinds, [want_kinds[k] for k in ks]):
            return [Column(fy(y), k) for y, k in zip(ys, ks)], subs
    raise ParseError(f"{fy(start)} ministries: unexpected header years {years[:12]} kinds {kinds[:8]}")


# --------------------------------------------------------------------------- values


def _anchors(lines: list[Line], ncols: int) -> dict[int, list[float]]:
    """Right edges of the value columns, per page, from lines that fill every column."""
    per_page: dict[int, list[list[float]]] = defaultdict(list)
    for line in lines:
        if len(line.values) == ncols and all(t not in NA for t, _ in line.values):
            per_page[line.page].append([x for _, x in line.values])
    out = {}
    for page, rows in per_page.items():
        out[page] = [sorted(col)[len(col) // 2] for col in zip(*rows)]
    if not out:
        raise ParseError("no line fills all value columns; cannot place numbers")
    fallback = next(iter(out.values()))
    for line in lines:
        out.setdefault(line.page, fallback)
    return out


def _place(line: Line, anchors: list[float], ncols: int, where: str) -> list[float | None]:
    """Put each number under the nearest column; columns with no number stay empty (None)."""
    spacing = min(b - a for a, b in zip(anchors, anchors[1:])) if ncols > 1 else 50
    out: list[float | None] = [None] * ncols
    taken: set[int] = set()
    for tok, x in line.values:
        col = min(range(ncols), key=lambda c: abs(anchors[c] - x))
        if abs(anchors[col] - x) > spacing * 0.45:
            raise ParseError(f"{where}: value {tok} in line {line.label!r} is not under any column")
        if col in taken:
            raise ParseError(f"{where}: two values under column {col + 1} in line {line.label!r}")
        taken.add(col)
        out[col] = None if tok in NA or tok == "" else float(tok.replace(",", ""))
    return out


# --------------------------------------------------------------------------- parsing


def _norm(label: str) -> str:
    s = label.strip()
    s = re.sub(r"^(demand\s*no\.?\s*\d+|\(?\d{1,3}\)?\s*[.)]?)\s+", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .*#@$")


def _category(label: str) -> str | None:
    key = _norm(label).lower()
    for cat, pat in CATEGORIES:
        if re.search(pat, key):
            return cat
    return None


def _demand_no(label: str) -> int | None:
    m = re.match(r"^\s*(?:demand\s*no\.?\s*)?(\d{1,3})\s*\.?\s", label + " ", re.I)
    return int(m.group(1)) if m else None


def parse_ministries(rows, start: int, cell_based: bool, *, lines: list[Line] | None = None) -> dict:
    """Parse one Statement 2 / 3 / 3A. `rows` are cell rows (spreadsheets) or ignored if `lines` given."""
    if lines is None:
        if not cell_based:
            raise ParseError("PDFs need this module's reader: pass lines=read_pdf_lines(path) or use parse_file()")
        lines = _cell_lines(rows)
    columns, subs = detect_header(lines, start)
    ncols = len(columns) * 3
    where = f"{fy(start)} ministries"
    anchors = {} if cell_based else _anchors(lines, ncols)

    def values(line: Line) -> list[float | None]:
        if cell_based:
            if len(line.values) != ncols:
                raise ParseError(f"{where}: line {line.label!r} has {len(line.values)} values, expected {ncols}")
            return [None if t in NA or t == "" else float(t) for t, _ in line.values]
        return _place(line, anchors[line.page], ncols, where)

    def split(vals: list[float | None]) -> list[dict]:
        return [dict(zip(subs, vals[i * 3 : i * 3 + 3])) for i in range(len(columns))]

    items: list[dict] = []
    unknown: list[str] = []
    data = [ln for ln in lines if not FURNITURE.match(ln.label.strip()) or ln.values]
    # The first data line is the first one with values after the header.
    i0 = next(i for i, ln in enumerate(data) if len(ln.values) >= ncols - 1 and not YEAR_RE.search(ln.label))
    data = data[i0:]
    if subs[0] == "plan":
        _parse_plan_era(data, values, split, items, unknown, where)
        _classify_plan_era(items)
    else:
        _parse_demand_era(data, values, split, items, unknown, where)
    return {"columns": columns, "subcolumns": subs, "items": items, "unknown_rows": unknown}


def _is_note(label: str) -> bool:
    return bool(re.match(r"^(notes?\b|\*|@|#|\$|actuals for|figures|source)", label.strip(), re.I))


SUBTOTAL_RE = re.compile(
    r"(?i:\btotal\b|^state plans$|^union territories$|^nec plan$|^doner$|"
    r"^union territories with(out)? legislature$|\([a-z0-9]{1,4}(\s*\+\s*[a-z0-9]{1,4})+\))"
    r"|^(I|II|III|IV|V)\.\s|^[AB]\.\s"  # section markers are upper case; "a." "i." are items
)


def _classify_plan_era(items: list[dict]) -> None:
    """Mark subtotals and the section of each line (to 2016-17).

    Sections: central (departments), state_plans (central assistance for State
    Plans, listed by the ministry it is routed through), union_territories.
    """
    section = "central"
    for it in items:
        name = it["name"]
        if it["level"] == "grand_total":
            it["section"] = None
            continue
        if SUBTOTAL_RE.search(name):
            it["level"] = "subtotal"
            low = name.lower()
            if "state plan" in low:
                section = "state_plans"
            elif "union territor" in low and "assistance" not in low:
                section = "union_territories"
            it["section"] = None if "assistance" in low or "central" in low else section
            continue
        it["section"] = section
        it["level"] = {"central": "department", "state_plans": "state_plan_assistance",
                       "union_territories": "union_territory"}[section]


def _parse_plan_era(data, values, split, items, unknown, where):
    """Department line, then 'Revenue' and 'Capital' lines. Labels may wrap above or below the numbers."""
    prefix: list[str] = []
    cur: dict | None = None
    stage = None  # None -> expecting entity; "suffix" -> collecting label after numbers; "rev" got revenue
    for ln in data:
        label = ln.label.strip()
        # A wrapped label line sometimes carries a stray "..." (empty cell) on its own
        # baseline. Empty cells carry no number, so such a line is just label text.
        if (
            ln.values
            and len(ln.values) < 3
            and all(t in NA for t, _ in ln.values)
            and re.sub(r"[^a-z]", "", label.lower()) not in ("revenue", "capital")
        ):
            ln = Line(ln.page, label, [])
        if not ln.values:
            if FURNITURE.match(label) or _is_note(label):
                continue
            if cur is not None and stage == "suffix":
                cur["label_parts"].append(label)
            else:
                prefix.append(label)
            continue
        key = re.sub(r"[^a-z]", "", label.lower())
        # "Revenue"/"Capital" right after a department are its split; elsewhere "Revenue"
        # is the Department of Revenue itself.
        if key == "revenue" and cur is not None and stage == "suffix":
            cur["revenue_line"] = split(values(ln))
            stage = "rev"
            continue
        if key == "capital" and cur is not None and stage == "rev":
            cur["capital_line"] = split(values(ln))
            items.append(_finish(cur))
            if items[-1]["level"] == "grand_total":
                return  # anything after the grand total is another statement
            cur, stage, prefix = None, None, []
            continue
        if cur is not None:
            raise ParseError(f"{where}: {cur['label_parts']} has no Revenue/Capital lines before {label!r}")
        cur = {"label_parts": prefix + [label], "periods": split(values(ln))}
        prefix, stage = [], "suffix"
    if cur is not None:
        raise ParseError(f"{where}: table ends inside {cur['label_parts']}")


def _parse_demand_era(data, values, split, items, unknown, where):
    """Demand line (label may continue below), then numbered category sub-lines; Grand Total at the end."""
    cur: dict | None = None
    last_target: dict | None = None
    grand: dict | None = None
    for ln in data:
        label = ln.label.strip()
        if not ln.values:
            if FURNITURE.match(label) or _is_note(label):
                continue
            if last_target is not None:
                last_target["label_parts"].append(label)
            continue
        if re.match(r"^grand total", label, re.I):
            if cur:
                items.append(_finish(cur))
                cur = None
            grand = {"label_parts": [label], "periods": split(values(ln)), "level": "grand_total", "subs": {}}
            last_target = None
            continue
        if re.match(r"^total\s*:?$", label, re.I):
            # 2023-24 prints a "Total:" line under each demand (Total columns only).
            if cur is None:
                raise ParseError(f"{where}: 'Total:' line before any demand")
            cur["printed_total"] = split(values(ln))
            last_target = None
            continue
        cat = _category(label)
        if cat:
            target = grand if grand is not None else cur
            if target is None:
                raise ParseError(f"{where}: category line {label!r} before any demand")
            if cat in target["subs"]:
                raise ParseError(f"{where}: {cat} twice under {target['label_parts']}")
            target["subs"][cat] = split(values(ln))
            last_target = None  # category labels do not wrap into the demand name
            continue
        if grand is not None:
            unknown.append(f"after Grand Total: {label!r}")
            continue
        if cur:
            items.append(_finish(cur))
        cur = {"label_parts": [label], "periods": split(values(ln)), "subs": {}, "demand_no": _demand_no(label)}
        last_target = cur
    if cur:
        items.append(_finish(cur))
    if grand is None:
        raise ParseError(f"{where}: no Grand Total line")
    items.append(_finish(grand))


def _finish(cur: dict) -> dict:
    printed = " ".join(p for p in cur["label_parts"] if p).strip()
    item = {
        "label_as_printed": printed,
        "name": _norm(printed),
        "level": cur.get("level", "department"),
        "periods": cur["periods"],
    }
    if "demand_no" in cur:
        item["demand_no"] = cur["demand_no"]
    if "revenue_line" in cur:
        item["revenue_line"] = cur["revenue_line"]
        item["capital_line"] = cur["capital_line"]
    if cur.get("subs"):
        item["subs"] = cur["subs"]
    if "printed_total" in cur:
        item["printed_total"] = cur["printed_total"]
    if re.search(r"\bgrand total\b", item["name"], re.I):
        item["level"] = "grand_total"
    return item

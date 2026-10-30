"""Total spending of each ministry / department, 2000-01 to 2026-27.

Sources (manifest key "ministries"):
- to 2016-17: Expenditure Budget Vol. 1, Statement 2 "Total Expenditure of
  Ministries/Departments". Each department has a line split Plan / Non-Plan /
  Total, followed by a "Revenue" line and a "Capital" line.
  2000-01 to 2010-11 print three periods (Actuals, Revised, Budget);
  2011-12 to 2016-17 print four (Actuals, Budget, Revised, Budget).
- from 2017-18: Expenditure Profile, Statement 3A (2017-18, 2018-19) / 3
  "Expenditure of Ministries and Departments". Each Demand for Grants has a
  line split Revenue / Capital / Total, followed by numbered sub-lines
  (Central Sector Schemes, Centrally Sponsored Schemes, Establishment, ...).

PDFs are read with a dedicated reader: these tables use 7-8.5pt type (too
small for the shared reader's footnote filter), have 9 or 12 value columns,
and sometimes print two numbers with no gap ("5200.351477.00"). Numbers are
placed into columns by the right edge of their text; "..." marks an empty
cell and keeps its column. Any line whose numbers do not fill the columns
exactly stops parsing with an error.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from .parse import Column, ParseError, ascii_text, fy
from .readers import read_any
from .sources import FORMAT_PRIORITY

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sources" / "manifest.json"
NAME_MAP = Path(__file__).resolve().parent / "data_maps" / "ministry_names.csv"

YEAR_RE = re.compile(r"(?<!\d)(\d{4})\s*-\s*(\d{4}|\d{2})(?!\d)")
TWO_DEC = re.compile(r"-?\d+\.\d{2}")
NA = {"...", "..", "…", "-", "--", "—", "–"}

# Sub-lines printed under each Demand from 2017-18.
CATEGORIES = [
    ("central_sector_schemes", r"^central sector schemes"),
    ("centrally_sponsored_schemes", r"^centrally sponsored schemes"),
    ("establishment", r"^establishment( expenditure)?$|^establishment expenditure"),
    ("other_central_sector", r"^other central (sector )?expenditure"),
    ("finance_commission_grants", r"^finance commission (grants|transfers)"),
    ("other_transfers", r"^other (grants\s*/?\s*loans\s*/?\s*)?transfers"),
]

# Header and page furniture lines (ignored wherever they appear).
FURNITURE = re.compile(
    r"^(expenditure budget|expenditure profile|statement\b|total expenditure of ministries|"
    r"expenditure of ministries|\(in |ministry\s*/\s*department|plan non-plan|revenue capital total|"
    r"actuals|budget estimates|page\b|\d+$)"
    r"|indiabudget\.(nic|gov)\.in|expenditure budget vol|expenditure profile 20"
    r"|^\d{4}-\d{2,4}\s+(actuals|budget|revised)"
    r"|^[\d\s\-]+$",  # page numbers, rows of column years
    re.I,
)


def _strip_furniture(label: str) -> str:
    """Remove page furniture glued onto a label line (URLs, running headers)."""
    label = re.sub(r"(website\s*:\s*)?(https?:?/*\S+|\S*indiabudget\.(nic|gov)\.in\S*)|^website\s*:", " ", label, flags=re.I)
    label = re.sub(
        r"\d{4}-\d{4}\s+expenditure budget vol\.?\s*i\b(.*?\bbudget\b(?=\s))?|"
        r"(\d+\s+)?expenditure budget vol\.?\s*i,?\s*\d{4}-\d{4}(\s+\d+)?",
        " ",
        label,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", label).strip()


# --------------------------------------------------------------------------- reading


class Line:
    def __init__(self, page: int, label: str, values: list[tuple[str, float]]):
        self.page = page
        self.label = label  # text left of the value columns
        self.values = values  # (token, right edge x)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Line(p{self.page} {self.label!r} {[t for t, _ in self.values]})"


def _split_number(text: str) -> list[str] | None:
    """'5200.351477.00' -> ['5200.35', '1477.00']; a single number -> [it]; not a number -> None."""
    t = text.replace(",", "")
    if t in NA:
        return [t]
    if re.fullmatch(r"-?\d+\.\d+", t):
        return [t]
    parts = TWO_DEC.findall(t)
    if len(parts) > 1 and "".join(parts) == t:
        return parts
    return None


def read_pdf_lines(path: Path) -> list[Line]:
    import pdfplumber

    out: list[Line] = []
    with pdfplumber.open(path) as pdf:
        sizes = [round(c["size"], 1) for p in pdf.pages[:2] for c in p.chars if c["text"].isdigit()]
        body = max(set(sizes), key=sizes.count) if sizes else 8.0
        for pno, page in enumerate(pdf.pages):
            page = page.filter(lambda o: o.get("object_type") != "char" or o.get("size", 99) >= body * 0.75)
            words = page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
            words.sort(key=lambda w: (w["bottom"], w["x0"]))
            lines: list[list[dict]] = []
            for w in words:
                if lines and abs(lines[-1][-1]["bottom"] - w["bottom"]) <= 2.0:
                    lines[-1].append(w)
                else:
                    lines.append([w])
            for ws in lines:
                ws.sort(key=lambda w: w["x0"])
                values: list[tuple[str, float]] = []
                while ws:
                    w = ws[-1]
                    parts = _split_number(w["text"])
                    if parts is None:
                        break
                    ws.pop()
                    width = (w["x1"] - w["x0"]) / max(len(w["text"]), 1)
                    end = len(w["text"])
                    for part in reversed(parts):
                        values.insert(0, (part, w["x0"] + width * end))
                        end -= len(part)
                label = _strip_furniture(ascii_text(" ".join(w["text"] for w in ws)))
                if label or values:
                    out.append(Line(pno, label, values))
    return out


SUBHEAD_RE = re.compile(r"^(plan|non-?\s*plan|revenue|capital|total)$", re.I)


def _cell_lines(rows: list[list[str]]) -> list[Line]:
    """Spreadsheet rows -> Lines. Value columns come from the sub-header row
    ("Plan Non-Plan Total ..." or "Revenue Capital Total ..."), because some
    files have empty spacer columns between them."""
    positions = None
    for r in rows[:40]:
        idx = [i for i, c in enumerate(r) if SUBHEAD_RE.match(c.strip())]
        if len(idx) >= 9:
            positions = idx
            break
    if positions is None:
        raise ParseError("spreadsheet: no Plan/Non-Plan/Total or Revenue/Capital/Total header row")
    out = []
    for r in rows:
        cells = list(r) + [""] * (max(positions) + 1 - len(r))
        values = []
        for p in positions:
            c = cells[p].strip().replace(",", "")
            if c and c not in NA and not re.fullmatch(r"-?\d+(\.\d+)?", c):
                values = None  # text in a value column: a heading row
                break
            values.append((c, float(p)))
        label_cells = [c for i, c in enumerate(cells) if i not in positions and c.strip()]
        label = ascii_text(" ".join(label_cells))
        if values is None:
            label = ascii_text(" ".join(c for c in cells if c.strip()))
            values = []
        elif all(t == "" for t, _ in values):
            values = []
        out.append(Line(0, label, values))
    return out


# --------------------------------------------------------------------------- header


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


# --------------------------------------------------------------------------- internal checks

TOL = 0.05  # values are printed to 2 decimals; allow rounding on sums of a few cells


def _close(a: float | None, b: float | None, tol: float = TOL) -> bool:
    return abs((a or 0.0) - (b or 0.0)) <= tol


def _sum(xs) -> float:
    return sum(x or 0.0 for x in xs)


def internal_checks(budget: str, parsed: dict) -> tuple[int, list[str], list[str], dict]:
    """Row and table identities for one parsed document.

    Returns (checked, failures, notes, results) where results keys are check names
    with per-check (checked, failures) counts for reporting.
    """
    cols = parsed["columns"]
    a, b = parsed["subcolumns"][:2]
    res: dict[str, list] = defaultdict(lambda: [0, []])

    def check(name: str, ok: bool, msg: str) -> None:
        res[name][0] += 1
        if not ok:
            res[name][1].append(f"Budget {budget}: {msg}")

    for it in parsed["items"]:
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
                    check("sub-lines add up to the demand", _close(got, it["periods"][c][sub], 0.05 * len(it["subs"])),
                          f"{col.kind} {col.fiscal_year} {it['name']!r} {sub}: sub-lines {got:.2f}, "
                          f"printed {it['periods'][c][sub]}")
        if "printed_total" in it:
            for c, col in enumerate(cols):
                check("'Total:' line repeats the demand total",
                      _close(it["printed_total"][c]["total"], it["periods"][c]["total"]),
                      f"{col.kind} {col.fiscal_year} {it['name']!r}: Total: line {it['printed_total'][c]['total']} "
                      f"vs {it['periods'][c]['total']}")

    grand = [it for it in parsed["items"] if it["level"] == "grand_total"]
    if len(grand) != 1:
        check("departments add up to the grand total", False, f"{len(grand)} grand total lines")
    else:
        g = grand[0]
        leaves = [it for it in parsed["items"] if it["level"] not in ("subtotal", "grand_total")]
        for c, col in enumerate(cols):
            for sub in parsed["subcolumns"]:
                got = _sum(it["periods"][c][sub] for it in leaves)
                check("departments add up to the grand total", _close(got, g["periods"][c][sub], 0.05 * len(leaves)),
                      f"{col.kind} {col.fiscal_year} {sub}: lines add to {got:.2f}, grand total {g['periods'][c][sub]}")
        if g.get("subs"):
            for cat, per in g["subs"].items():
                for c, col in enumerate(cols):
                    for sub in ("revenue", "capital", "total"):
                        got = _sum(it["subs"].get(cat, [{}] * len(cols))[c].get(sub) for it in leaves if it.get("subs"))
                        check("each spending category adds up across demands", _close(got, per[c][sub], 0.05 * len(leaves)),
                              f"{col.kind} {col.fiscal_year} {cat} {sub}: demands add to {got:.2f}, "
                              f"grand total line {per[c][sub]}")
    checked = sum(v[0] for v in res.values())
    failures = [f for v in res.values() for f in v[1]]
    return checked, failures, [], dict(res)


# --------------------------------------------------------------------------- names -> ids


def _map_key(name: str) -> str:
    """Strip list markers ('a.', 'aa.', '(iii)', '(1)') and normalise spaces for map lookup."""
    s = re.sub(r"^(\(?[ivx]+\)|\(\d+\)|[a-z]{1,2}\.)\s+", "", name.strip())
    return re.sub(r"\s+", " ", s).strip()


def load_name_map() -> list[dict]:
    with NAME_MAP.open() as f:
        return list(csv.DictReader(f))


def lookup(name: str, budget: str, name_map: list[dict]) -> dict:
    key = _map_key(name)
    hits = [
        r for r in name_map
        if r["printed_name"] == key
        and (not r["budget_from"] or r["budget_from"] <= budget)
        and (not r["budget_to"] or budget <= r["budget_to"])
    ]
    if len(hits) != 1:
        raise KeyError(f"Budget {budget}: printed name {key!r} has {len(hits)} entries in {NAME_MAP.name}")
    return hits[0]


def assign_ids(budget: str, parsed: dict, name_map: list[dict]) -> None:
    """Give every line a stable id. Fails loudly if a printed name is not in the map."""
    for it in parsed["items"]:
        if it["level"] == "grand_total":
            it["item_id"] = "grand_total"
            continue
        if it["level"] == "subtotal":
            it["item_id"] = "subtotal:" + re.sub(r"[^a-z0-9]+", "_", _map_key(it["name"]).lower()).strip("_")
            continue
        row = lookup(it["name"], budget, name_map)
        prefix = "state_plans:" if it["level"] == "state_plan_assistance" else ""
        it["item_id"] = prefix + row["department_id"]
        it["department_name"] = row["department_name"]
        it["ministry_id"] = row["ministry_id"]
        it["ministry_name"] = row["ministry_name"]
    ids = [it["item_id"] for it in parsed["items"] if it["level"] not in ("subtotal",)]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ParseError(f"Budget {budget}: the same id appears twice: {sorted(dupes)}")


# --------------------------------------------------------------------------- loading


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
    manifest = json.loads(MANIFEST.read_text())
    name_map = load_name_map()
    out = {}
    for budget, entry in manifest.items():
        files = entry.get("ministries", {}).get("files", {})
        start = int(budget[:4])
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


# --------------------------------------------------------------------------- checks

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

# (budget, check title, message fragment) -> reason. A failure is excused only if its
# message contains the fragment.
KNOWN_EXCEPTIONS: dict[tuple[str, str, str], str] = {
    **{(b, "Revenue line + Capital line = department line", "'III. UNION TERRITORIES (A + B)'"): UT_CAPITAL_LINE
       for b in ("2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17")},
    ("2023-24", "revenue + capital = total on every line", "'Grand Total' / central_sector_schemes"): GRAND_2023_CSS,
    ("2023-24", "each spending category adds up across demands", "central_sector_schemes revenue"): GRAND_2023_CSS,
    ("2023-24", "revenue + capital = total on every line", "'Grand Total' / other_transfers"): GRAND_2023_OTHER,
    ("2023-24", "each spending category adds up across demands", "other_transfers revenue"): GRAND_2023_OTHER,
    ("2000-01", "departments add up to the grand total", "Actual 1998-99"): ACTUAL_1998_99,
    ("2000-01", "grand total = Budget at a Glance", "Actual 1998-99"): ACTUAL_1998_99,
}

# Same table in another format (Excel) that disagrees with the PDF: (budget, ext) -> reason.
KNOWN_FORMAT_ISSUES: dict[tuple[str, str], str] = {}

# Lines present in only one copy, explained: (budget, ext) -> reason.
ONE_COPY_ONLY: dict[tuple[str, str], str] = {
    ("2017-18", "xlsx"): "the Excel copy mislabels the six category lines under Grand Total (all read "
                         "\"Centre's expenditure\" / \"Transfers to ...\"), so they cannot be matched; the PDF labels them correctly.",
    ("2025-26", "xlsx"): "the PDF has no category lines under Grand Total; the Excel copy adds them.",
}

# Budget 2017-18 abolished the Plan/Non-plan split. Its Statement 3A restates 2016-17 under the new
# structure: central assistance for State Plans is folded into the department it was routed through,
# and Police, Cabinet, Pensions, Direct/Indirect Taxes and others become separate demands. Lines of
# Budget 2016-17 and Budget 2017-18 are therefore not like-for-like; only the grand total must agree.
STRUCTURE_BREAK = ("2016-17", "2017-18")


def _excused(budget: str, title: str, msg: str) -> str | None:
    for (b, t, frag), reason in KNOWN_EXCEPTIONS.items():
        if b == budget and t == title and frag in msg:
            return reason
    return None


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


def checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple[str, int, list[str], list[str]]]:
    """All ministry checks. Returns [(title, checked, failures, notes)]."""
    sections: dict[str, list] = defaultdict(lambda: [0, [], []])

    def record(title: str, budget: str, checked: int, failures: list[str]) -> None:
        sec = sections[title]
        sec[0] += checked
        for f in failures:
            reason = _excused(budget, title, f)
            if reason:
                sec[2].append(f"Allowed: {f}. Reason: {reason}")
            else:
                sec[1].append(f)

    # (a)-(c): identities inside each primary document
    for budget, b in all_parsed.items():
        _, _, _, res = internal_checks(budget, b["parsed"][b["primary"]])
        for title, (n, fails) in res.items():
            record(title, budget, n, fails)

    # (d): grand total vs the Budget at a Glance summary table, same budget and column
    summ: dict[tuple, dict] = defaultdict(dict)
    for r in summary_observations:
        v = r.get("value_crore")
        if v not in (None, ""):
            summ[(r["source_budget"], r["fiscal_year"], r["kind"])][r["field"]] = float(v)
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
        record(title, budget, n, fails)

    # (e): the same line, year and estimate printed in two budgets. Restatements happen (lines move
    # between departments), so a line difference is accepted when the grand total agrees and either the
    # ministry's total agrees (a move inside the ministry) or the budgets straddle the 2017-18 restructuring.
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

    # (f): other formats agree with the PDF
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
            if grand_only and (budget, ext) in ONE_COPY_ONLY:
                sections[title][2].append(f"Budget {budget}: {len(grand_only)} values in only one copy: "
                                          f"{ONE_COPY_ONLY[(budget, ext)]}")
            elif grand_only:
                line_only += grand_only
            diffs += line_only
            if not diffs:
                sections[title][2].append(f"Budget {budget}: {ext.upper()} matches {b['primary'].upper()} exactly.")
            elif (budget, ext) in KNOWN_FORMAT_ISSUES:
                sections[title][2].append(f"Budget {budget}: {ext.upper()} differs in {len(diffs)} values (known): "
                                          f"{KNOWN_FORMAT_ISSUES[(budget, ext)]}")
            else:
                sections[title][1].append(f"Budget {budget}: {ext.upper()} differs from {b['primary'].upper()} in "
                                          f"{len(diffs)} values: " + "; ".join(diffs[:4]))
        for ext, err in b["errors"].items():
            sections[title][1].append(f"Budget {budget}: {ext.upper()} copy could not be read: {err}")

    order = [
        "plan + non_plan = total on every line", "revenue + capital = total on every line",
        "Revenue line + Capital line = department line", "sub-lines add up to the demand",
        "'Total:' line repeats the demand total", "departments add up to the grand total",
        "each spending category adds up across demands", "grand total = Budget at a Glance",
        "same line agrees in both budgets that print it", "Excel copies agree with the PDF",
    ]
    return [(f"Ministries: {t}", *sections[t]) for t in order if t in sections]

"""Scheme-level spending: Expenditure Profile Statements 4A and 4B.

- 4A "Centrally Sponsored Schemes" (css): schemes run by States with central money.
- 4B "Central Sector Schemes" (central_sector): schemes run by the Centre.

Coverage: budgets 2017-18 to 2026-27 (so Actuals from 2015-16). Before 2017-18
the budget split spending into Plan and Non-plan and schemes appear only as
Plan outlays (Expenditure Budget / "Highlights of Central Plan"), which are a
different, partial measure; those years are deliberately out of scope.

Each statement prints, for four periods (Actuals two years back, BE and RE of
last year, BE of the new year), Revenue, Capital and Total for every scheme,
grouped by Demand (department) or, for CSS until 2024-25, by category
("Core of the Core", "Core", "Others"), with subtotals and a Grand Total.

The PDF is the primary source. PDF text is read character by character and
each character is put in a value column by its horizontal position, because
these PDFs glue neighbouring cells together ("...25000.00"), print stray
symbols inside numbers ("37*340.71") and sometimes set part of a row a few
points higher than the rest. Every row must end up with all 12 cells filled
(a "..." counts as filled) or parsing stops with an error.

Public functions: parse_schemes(), parse_file(), load_all(), checks().
"""

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .parse import Column, ParseError, expected_columns, fy
from .readers import read_any
from .sources import FIRST_SCHEME_BUDGET, FORMAT_PRIORITY, LATEST_BUDGET

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sources" / "manifest.json"
NAME_MAP = Path(__file__).resolve().parent / "data_maps" / "scheme_names.csv"

SCHEME_TYPES = {"css": "Centrally Sponsored Schemes", "central_sector": "Central Sector Schemes"}
PARTS = ("revenue", "capital", "total")
TOLERANCE = 0.051  # crore; values are printed to two decimals

NA_TEXT = {"...", "..", "…", "-", "--", "–", "—"}
HEADER_PATTERNS = [
    r"^expenditure profile", r"^statement\s*4", r"^centrally sponsored schemes", r"^central sector schemes",
    r"^\(in\b", r"^actuals", r"^ministry\s*/\s*department", r"^sl\.?\s*name", r"^no\.?\s+scheme",
    r"^revenue capital total", r"^\(\s*rs\.?|^\(\s*`",
]


# ----- reading PDFs by position ----------------------------------------------


@dataclass
class Line:
    label: str
    cells: list[str | None]  # 12 raw value strings, None = nothing printed in that column
    page: int
    bottom: float
    text: str = ""  # the whole line as printed (for recognising page headers)

    @property
    def has_values(self) -> bool:
        return any(c is not None for c in self.cells)


def _is_numberish(text: str) -> bool:
    return bool(text) and re.fullmatch(r"[\d.,\-*…()]+", text) is not None and re.search(r"[\d.…]", text) is not None


def _anchors(pages_words: list[list[dict]]) -> list[float]:
    """Right edges of the 12 value columns, from lines that hold exactly 12 numbers."""
    samples: list[list[float]] = []
    for words in pages_words:
        for line in _group_lines(words):
            nums = [w for w in line if _is_numberish(w["text"])]
            if len(nums) >= 12:
                tail = nums[-12:]
                gaps = [tail[i + 1]["x1"] - tail[i]["x1"] for i in range(11)]
                if all(g > 15 for g in gaps):
                    samples.append([w["x1"] for w in tail])
    if not samples:
        raise ParseError("no complete 12-value row found to locate the value columns")
    anchors = []
    for i in range(12):
        xs = sorted(s[i] for s in samples)
        anchors.append(xs[len(xs) // 2])
    return anchors


# Values are printed with exactly two decimals, which lets glued cells be split: "283802.5269.09".
TOKEN_RE = re.compile(r"\.{2,}|…+|-?[\d,*]*\d\.\d{2}(?!\d)|-?[\d,*]*\d(?:\.\d+)?|\.(?=[\d,]+\.\d)|\.\d+|-")


def _tokens(word: dict) -> list[tuple[float, float, str]]:
    """Split a PDF word into value tokens with their own x positions.
    PDFs sometimes glue a "..." and the next number into one word ("...25000.00")."""
    text = word["text"]
    chars = word["chars"]
    if len(chars) != len(text):
        return [(word["x0"], word["x1"], text)]
    out = []
    for m in TOKEN_RE.finditer(text):
        cs = chars[m.start(): m.end()]
        out.append((cs[0]["x0"], cs[-1]["x1"], m.group(0)))
    return out


def _group_lines(words: list[dict], tol: float = 2.5) -> list[list[dict]]:
    words = sorted(words, key=lambda w: (w["bottom"], w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and abs(lines[-1][-1]["bottom"] - w["bottom"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def read_pdf_lines(path: Path) -> list[Line]:
    import pdfplumber

    pages_words: list[list[dict]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # Drop superscript footnote markers: characters much smaller than the page's body text.
            # (A fixed cut-off fails: some years print "Grand Total" at 6.8pt.)
            sizes = sorted(round(c["size"], 1) for c in page.chars)
            body = max(set(sizes), key=sizes.count) if sizes else 10.0
            cutoff = 0.75 * body
            page = page.filter(lambda o, cutoff=cutoff: o.get("object_type") != "char" or o.get("size", 99) >= cutoff)
            pages_words.append(page.extract_words(x_tolerance=1.5, keep_blank_chars=False, extra_attrs=["size"],
                                                  return_chars=True))
    anchors = _anchors(pages_words)
    widths = [anchors[i] - anchors[i - 1] for i in range(1, 12)]
    region_start = anchors[0] - min(widths)  # the first value column's stretch starts here
    # A column owns numbers ending up to 30% of the way to the next column (overprinted
    # figures can sit a few points right of the usual edge).
    bounds = [anchors[i] + 0.3 * (anchors[i + 1] - anchors[i]) for i in range(11)] + [anchors[11] + 6]

    out: list[Line] = []
    for pno, words in enumerate(pages_words, start=1):
        for line in _group_lines(words):
            label_parts: list[str] = []
            cells: list[list[tuple[float, str]]] = [[] for _ in range(12)]
            full_text = " ".join(w["text"] for w in line)
            if _is_header(full_text) or re.search(r"\b(19|20)\d{2}\s*-\s*(19|20)\d{2}\b", full_text):
                out.append(Line("", [None] * 12, pno, line[0]["bottom"], full_text))
                continue
            for w in line:
                if _is_numberish(w["text"]) and region_start < w["x1"] <= bounds[-1]:
                    # Each column owns the stretch from just right of the previous column's
                    # right edge to just right of its own. Digits printed apart ("1 9 000.00")
                    # therefore still land in one cell instead of being lost.
                    for x0, x1, tok in _tokens(w):
                        if tok == ".":
                            continue  # a stray dot left over from a neighbouring "..." (".22920.09")
                        if re.fullmatch(r"\.{2,}|…+", tok):
                            c = min(range(12), key=lambda i: abs(anchors[i] - x1))  # a "..." sits near its column's edge
                        else:
                            c = next(i for i in range(12) if x1 <= bounds[i])
                        cells[c].append((x0, tok))
                else:
                    label_parts.append(w["text"])
            out.append(Line(
                label=re.sub(r"\s+", " ", " ".join(label_parts)).strip(),
                cells=["".join(t for _, t in sorted(c)) or None for c in cells],
                page=pno,
                bottom=line[0]["bottom"],
                text=" ".join(w["text"] for w in line),
            ))
    return _merge_split_rows(_join_wrapped_digits(out))


def _join_wrapped_digits(lines: list[Line]) -> list[Line]:
    """A number too wide for its cell wraps its last digit onto the next line
    ("1209949.5" / "9"). Join such a digit back; other lone small numbers with no
    name are page numbers and are dropped."""
    out: list[Line] = []
    for ln in lines:
        filled = [k for k, c in enumerate(ln.cells) if c is not None]
        if not ln.label and len(filled) == 1 and re.fullmatch(r"\d{1,3}", ln.cells[filled[0]] or ""):
            k = filled[0]
            prev = out[-1] if out else None
            if (prev is not None and prev.page == ln.page and 0 < ln.bottom - prev.bottom < 14
                    and prev.cells[k] and re.search(r"\d\.\d$", prev.cells[k]) and len(ln.cells[k]) == 1):
                prev.cells[k] += ln.cells[k]
            continue
        out.append(ln)
    return out


def _merge_split_rows(lines: list[Line]) -> list[Line]:
    """Some rows are typeset with a few columns a couple of points higher or lower
    than the rest, so they come out as two lines. Merge two neighbouring lines
    when their filled columns are complementary and together make all 12."""
    merged: list[Line] = []
    i = 0
    while i < len(lines):
        a = lines[i]
        if i + 1 < len(lines) and a.has_values:
            b = lines[i + 1]
            fa = {k for k, c in enumerate(a.cells) if c is not None}
            fb = {k for k, c in enumerate(b.cells) if c is not None}
            if (b.page == a.page and abs(b.bottom - a.bottom) < 9 and fa and fb and not (fa & fb)
                    and len(fa | fb) == 12):
                label = " ".join(x for x in (a.label, b.label) if x)
                cells = [a.cells[k] if k in fa else b.cells[k] for k in range(12)]
                merged.append(Line(label, cells, a.page, b.bottom, a.text + " " + b.text))
                i += 2
                continue
        # Numbers set a few points above their (single-line) name: attach them to the name below.
        if (i + 1 < len(lines) and a.has_values and not a.label):
            b = lines[i + 1]
            if b.page == a.page and not b.has_values and b.label and 0 < b.bottom - a.bottom <= 6.5:
                merged.append(Line(b.label, a.cells, b.page, b.bottom, a.text + " " + b.text))
                i += 2
                continue
        merged.append(a)
        i += 1
    return merged


# ----- text-layer gaps, read from the rendered page ---------------------------
#
# A few PDFs draw some text without a usable text layer (the glyphs are on the
# page but not extractable). These cells were read from the page rendered as an
# image (pdfplumber .to_image at 170-200 dpi) and are applied only when the text
# layer shows exactly the broken fragment noted below, so a corrected file will
# not be silently overridden. Each row is then verified by the same checks as
# every other row (Revenue + Capital = Total, rows add up to totals).

IMAGE_READINGS: list[dict] = [
    {
        "budget": "2025-26", "scheme_type": "css", "page": 5,
        "label_re": r"^(Others|82\. Others)", "expect": {3: r"\.?4?2?"},
        "cells": {3: "-8034.42"},
        "reason": "Budget 2025-26 Statement 4A, 'Others' group and item 82: the text layer has only '-' and "
                  "'.42' for BE 2024-25 revenue (the digits are drawn but not extractable); the page image "
                  "shows -8034.42, which also equals the row's printed total.",
    },
    {
        "budget": "2025-26", "scheme_type": "css", "page": 5, "insert_grand_total": True,
        "cells": dict(enumerate(["444416.49", "130.71", "444547.20", "505941.24", "36.83", "505978.07",
                                 "415322.05", "34.20", "415356.25", "536826.78", "23.43", "541850.21"])),
        "reason": "Budget 2025-26 Statement 4A: the Grand Total row is printed (page image) but absent from "
                  "the PDF text layer and from the Excel copy. Values read from the page image.",
    },
    {
        "budget": "2025-26", "scheme_type": "central_sector", "page": 25,
        "label_re": r"^Grand Total", "expect": {1: r"734166\.62"},
        "cells": dict(enumerate(["689270.79", "734166.62", "1423437.41", "750579.03", "765596.72", "1516175.75",
                                 "761222.21", "751597.54", "1512819.75", "787524.99", "834373.91", "1621898.90"])),
        "reason": "Budget 2025-26 Statement 4B: the text layer (and the Excel copy) has only one of the 12 "
                  "Grand Total figures; the rest read from the page image.",
    },
]

IMAGE_READINGS.append({
    "budget": "2017-18", "scheme_type": "central_sector", "page": 12,
    "label_re": r"^313\. Gross Exp\. on Schemes for Safety of Women", "expect": {10: r"22\.69\.*"},
    "cells": {10: "22.69"},
    "reason": "Budget 2017-18 Statement 4B item 313: the text layer has '22.69..' for BE 2017-18 capital "
              "(dots from an overprinted '...'); the page image shows 22.69, and 340.61 + 22.69 = 363.30 "
              "as printed.",
})

# Names missing from the text layer: (budget, scheme_type, page, first value printed) -> name.
MISSING_LABELS: dict[tuple[str, str, int, str], tuple[str, str]] = {
    ("2020-21", "css", 2, "2224.47"): (
        "30. Pradhan Mantri Jan Arogya Yojana (including RSBY)",
        "Budget 2020-21 Statement 4A: the name of item 30 is printed but absent from the text layer; read "
        "from the page image. Budget 2021-22 prints the same 2019-20 RE (3,314.00) for this scheme.",
    ),
}


# Names garbled in the text layer (two overprinted strings interleaved): (budget, scheme_type, page,
# garbled label regex) -> (replacement label, text the previous row's name lost, reason).
GARBLED_LABELS: list[tuple[tuple[str, str, int, str], tuple[str, str, str]]] = [
    (("2022-23", "css", 2, r"^45\.\s*mGraeregnin R uenvodleurt iNoFnSA$"), (
        "45. Green Revolution", "Margin under NFSA",
        "Budget 2022-23 Statement 4A: the text layer interleaves item 45's name 'Green Revolution' with the "
        "last line of item 44's name ('Margin under NFSA'); both read from the page image.")),
]


def apply_text_layer_fixes(lines: list[Line], budget: str, scheme_type: str) -> tuple[list[Line], list[str]]:
    used: list[str] = []
    for (b_, t_, page, pat), (new_label, lost, reason) in GARBLED_LABELS:
        if (b_, t_) != (budget, scheme_type):
            continue
        idx = next((k for k, ln in enumerate(lines) if ln.page == page and re.match(pat, ln.label)), None)
        if idx is None:
            raise ParseError(f"{budget} {scheme_type}: garbled label {pat!r} not found; review GARBLED_LABELS")
        lines[idx].label = new_label
        lines.insert(idx, Line(lost, [None] * 12, page, lines[idx].bottom - 0.1, lost))
        used.append(reason)
    for fix in IMAGE_READINGS:
        if fix["budget"] != budget or fix["scheme_type"] != scheme_type:
            continue
        if fix.get("insert_grand_total"):
            if any(re.match(r"^grand\s*total", ln.label, re.I) for ln in lines):
                raise ParseError(f"{budget} {scheme_type}: a Grand Total row is now readable; review IMAGE_READINGS")
            last = max((ln for ln in lines if ln.page == fix["page"]), key=lambda ln: ln.bottom)
            cells = [fix["cells"][k] for k in range(12)]
            lines.append(Line("Grand Total", cells, fix["page"], last.bottom + 10, "Grand Total (from page image)"))
            used.append(fix["reason"])
            continue
        hits = 0
        for ln in lines:
            if ln.page == fix["page"] and re.match(fix["label_re"], ln.label):
                if any(not re.fullmatch(v, ln.cells[k] or "") for k, v in fix["expect"].items()):
                    raise ParseError(f"{budget} {scheme_type} p{ln.page} {ln.label!r}: text layer changed "
                                     f"({[ln.cells[k] for k in fix['expect']]}); review IMAGE_READINGS")
                for k, v in fix["cells"].items():
                    ln.cells[k] = v
                ln.label = re.sub(r"\s+-$", "", ln.label)
                hits += 1
        if not hits:
            raise ParseError(f"{budget} {scheme_type}: image reading {fix['label_re']!r} matched no row")
        used.append(fix["reason"])
    for ln in lines:
        key = (budget, scheme_type, ln.page, ln.cells[0] or "")
        if not ln.label and key in MISSING_LABELS:
            ln.label = MISSING_LABELS[key][0]
            used.append(MISSING_LABELS[key][1])
    return lines, used


# ----- reading spreadsheets ----------------------------------------------------


def read_sheet_lines(path: Path) -> tuple[list[Line], str, list[int]]:
    """Spreadsheet rows -> Lines. Returns (lines, header text, value column indices).

    Each period heading ("Actuals 2023-2024", "Budget Estimates 2024-2025", ...)
    starts three columns: Revenue, Capital, Total. (Some copies leave out the
    'Total' heading or the whole Revenue/Capital/Total row, so the period
    headings are used.) One 2024-25 copy has only the new BE period."""
    rows = read_any(path)
    hdr = next((i for i, r in enumerate(rows[:20])
                if sum(bool(re.search(r"(actual|budget|revised)\D{0,25}\d{4}", c, re.I)) for c in r) >= 1
                and not re.search(r"expenditure profile", " ".join(r), re.I)), None)
    if hdr is None:
        raise ParseError(f"{path.name}: no period headings")
    starts = [j for j, c in enumerate(rows[hdr]) if re.search(r"(actual|budget|revised)\D{0,25}\d{4}", c, re.I)]
    header_text = " ".join(rows[hdr][j] for j in starts)
    body = rows[hdr + 1:]
    cols = [j + k for j in starts for k in range(3)]
    if body and sum(c.strip().lower() in PARTS for c in body[0]) >= 2:
        rct = [c.strip().lower() for c in body[0]]
        body = body[1:]  # the Revenue / Capital / Total heading row
        found = []
        for n, j in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(rct)
            for part in PARTS:
                k = next((x for x in range(j, end) if rct[x] == part), None)
                if k is None:  # a heading left out (one copy omits 'Total'): assume the usual position
                    k = j + PARTS.index(part)
                found.append(k)
        cols = found
    lines = []
    for r in body:
        label = " ".join(c for c in r[: starts[0]] if c.strip())
        cells = [(r[j].strip() if j < len(r) and r[j].strip() else None) for j in cols]
        lines.append(Line(re.sub(r"\s+", " ", label).strip(), cells, 0, 0.0, " ".join(r)))
    return lines, header_text, cols


# ----- turning lines into items ----------------------------------------------


def parse_value(text: str | None, where: str) -> float | None:
    if text is None:
        return None  # nothing printed in the cell; checked through Revenue + Capital = Total and the sums
    t = text.strip().replace(",", "")
    if t in NA_TEXT or re.fullmatch(r"\.+|…+", t):
        return None
    t = t.replace("*", "")  # stray symbol printed inside a number, e.g. 37*340.71 (checked by Revenue+Capital=Total)
    if re.fullmatch(r"\(?-?\d+(\.\d+)?\)?", t):
        neg = t.startswith("(") and t.endswith(")")
        v = float(t.strip("()"))
        return -v if neg else v
    raise ParseError(f"{where}: cannot read value {text!r}")


SCHEME_NO_RE = re.compile(r"^(\d{1,3})\s*\.{0,2}\s+(?=\S)")
COMPONENT_RE = re.compile(r"^\(?([a-z]|[ivx]{1,4}|[IVX]{1,4})[.)]\s*(?=\S)|^([a-z])\s+(?=[A-Z])")
SPACED_NO_RE = re.compile(r"^(\d)\s+(\d)(?:\s+(\d))?\s*\.")  # "3 2 . Saksham" -> "32. Saksham"
OTHERS_GROUP_RE = re.compile(r"^others\s*-?$", re.I)
CATEGORY_RE = re.compile(r"^\(([A-Z])\)\s*(.*)$")
DEMAND_RE = re.compile(r"^Demand\s*No\.?\s*(\d+)\s*(.*)$", re.I)  # some copies put the department name on the same row
TOTAL_OF_RE = re.compile(r"^total of\b", re.I)  # 2017-18: category totals at the end of each category
RECOVERIES_RE = re.compile(r"^(actual\s+)?recoveries\b", re.I)


@dataclass
class Item:
    level: str  # scheme | component | demand_subtotal | category_subtotal | grand_total
    number: str  # scheme number, component letter, demand number, category letter, ""
    label_parts: list[str] = field(default_factory=list)
    values: list[float | None] | None = None
    demand_no: str | None = None
    department_parts: list[str] = field(default_factory=list)
    category: str | None = None
    parent_number: str | None = None
    page: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.label_parts)).strip()


def _is_header(label: str) -> bool:
    low = label.lower().strip()
    return any(re.search(p, low) for p in HEADER_PATTERNS)


def lines_to_items(lines: list[Line], where: str, lenient_numbering: bool = False) -> tuple[list[Item], list[str]]:
    items: list[Item] = []
    unknown: list[str] = []
    current: Item | None = None
    demand: Item | None = None
    category: str | None = None
    last_scheme_no = 0
    last_scheme: Item | None = None
    in_department = False
    gaps: list[str] = []
    used_numbers: set[int] = set()

    for ln in lines:
        label = SPACED_NO_RE.sub(lambda m: "".join(g for g in m.groups() if g) + ".", ln.label)
        if _is_header(ln.text or label) or (not ln.has_values and not label):
            continue
        if current is not None and current.level == "grand_total":
            if current.values is None and ln.has_values:
                current.label_parts.append(label)
                current.values = [parse_value(c, f"{where} p{ln.page} {label!r}") for c in ln.cells]
            if current.values is not None:
                break  # notes follow the Grand Total
            current.label_parts.append(label)
            continue
        if re.match(r"^grand\s*total", label, re.I):
            current = Item("grand_total", "", [label], page=ln.page)
            items.append(current)
            if ln.has_values:
                current.values = [parse_value(c, f"{where} p{ln.page} {label!r}") for c in ln.cells]
                break
            continue
        m_dem = DEMAND_RE.match(label)
        if not m_dem and ln.has_values and OTHERS_GROUP_RE.match(label):
            # A last group headed just "Others" (no Demand number) in some years.
            m_dem = re.match(r"(others)", "others")
        m_cat = CATEGORY_RE.match(label)
        m_no = SCHEME_NO_RE.match(label)
        m_comp = COMPONENT_RE.match(label) if not m_no else None
        new: Item | None = None
        if m_dem:
            new = Item("demand_subtotal", m_dem.group(1), [], page=ln.page)
            new.demand_no = m_dem.group(1)
            if len(m_dem.groups()) > 1 and m_dem.group(2):
                new.department_parts.append(m_dem.group(2))
            demand = new
            in_department = True
        elif TOTAL_OF_RE.match(label) and ln.has_values and category:
            new = Item("category_subtotal", category, [label], page=ln.page, category=category)
            in_department = False
        elif RECOVERIES_RE.match(label) and ln.has_values and not m_no:
            new = Item("scheme", f"rec{len(items)}", [label], page=ln.page)
            in_department = False
        elif m_cat:
            category = m_cat.group(1)
            new = Item("category_subtotal", category, [m_cat.group(2)], page=ln.page, category=category)
            in_department = False
        elif (m_no and demand is not None and re.match(r"^\d{1,3}\.?\s+Others \(including amount met from", label, re.I)
              and (int(m_no.group(1)) == last_scheme_no + 1)):
            # The statement ends with a line for amounts met from / transferred to funds that belongs
            # to no Demand. Some years print an "Others" heading for it; give it its own group.
            last_scheme_no = int(m_no.group(1))
            if demand.demand_no != "others":
                # No printed heading or subtotal: this row stands on its own, outside any Demand.
                demand = Item("demand_subtotal", "ungrouped", [], demand_no=None)
            new = Item("scheme", m_no.group(1), [label[m_no.end():]], page=ln.page)
            in_department = False
        elif m_no and (int(m_no.group(1)) == last_scheme_no + 1
                       or (lenient_numbering and ln.has_values and int(m_no.group(1)) not in used_numbers)
                       or (ln.has_values and re.match(r"^\d{1,3}\.\s", label)
                           and last_scheme_no + 1 < int(m_no.group(1)) <= last_scheme_no + 3)):
            if int(m_no.group(1)) != last_scheme_no + 1 and not lenient_numbering:
                gaps.append(f"numbering skips from {last_scheme_no} to {m_no.group(1)}")
            last_scheme_no = int(m_no.group(1))
            used_numbers.add(last_scheme_no)
            new = Item("scheme", m_no.group(1), [label[m_no.end():]], page=ln.page)
            in_department = False
        elif (m_comp and ln.has_values and category is not None and re.fullmatch(r"[IVX]+", m_comp.group(1) or "")
              and (last_scheme is None or last_scheme.category != category
                   or re.fullmatch(r"[IVX]+", last_scheme.number))):
            # 2020-21: the "(C) Others" category numbers its schemes I., II., ...
            new = Item("scheme", m_comp.group(1), [label[m_comp.end():]], page=ln.page)
            in_department = False
        elif m_comp and last_scheme is not None and (ln.has_values or (m_comp.group(2) and len(label) > 3)):
            # Components carry their own numbers, except the 2017-18 layout ("b Civil Rights ...")
            # where a name can wrap above its numbers; a bare "II)" line is a wrapped scheme name.
            letter = m_comp.group(1) or m_comp.group(2)
            new = Item("component", letter, [label[m_comp.end():]], page=ln.page,
                       parent_number=last_scheme.number)
            in_department = False
        if new is not None:
            if new.level in ("scheme", "component"):
                new.demand_no = demand.demand_no if demand else None
                new.category = category
                if new.level == "scheme":
                    last_scheme = new
            elif new.level == "category_subtotal" and not TOTAL_OF_RE.match(label):
                last_scheme = None
            items.append(new)
            current = new
            if ln.has_values:
                new.values = [parse_value(c, f"{where} p{ln.page} {label!r}") for c in ln.cells]
            continue
        # Not the start of a new item.
        if ln.has_values:
            if current is not None and current.values is None:
                # Name printed above its numbers (2017-18 layout): this line closes it.
                if label:
                    current.label_parts.append(label)
                current.values = [parse_value(c, f"{where} p{ln.page} {label!r}") for c in ln.cells]
                continue
            unknown.append(f"p{ln.page}: {label!r} -> {ln.cells}")
            continue
        if current is None:
            unknown.append(f"p{ln.page}: {label!r}")
            continue
        if current.level == "demand_subtotal" and in_department:
            current.department_parts.append(label)
        else:
            current.label_parts.append(label)
    # A category name without numbers is only a heading (2017-18 layout).
    items = [it for it in items if not (it.level == "category_subtotal" and it.values is None)]
    # Every item must have its numbers.
    for it in items:
        if it.values is None:
            raise ParseError(f"{where}: {it.level} {it.number} {it.label!r} has no values")
        if len(it.values) != 12:
            raise ParseError(f"{where}: {it.level} {it.number} has {len(it.values)} values")
    unknown.extend(f"note: {g}" for g in gaps)
    return items, unknown


def _columns(header_text: str, start: int) -> list[Column]:
    cols = expected_columns(header_text, start)
    if len(cols) != 4:
        raise ParseError(f"{fy(start)}: expected 4 periods, found {[(c.fiscal_year, c.kind) for c in cols]}")
    return cols


def parse_schemes(rows_or_path, start: int, cell_based: bool, scheme_type: str) -> dict:
    """Parse one statement. `rows_or_path` is the file path (PDF or spreadsheet).

    Returns {"columns": [Column x4], "items": [dict], "unknown_rows": [...], "periods_present": [...]}.
    Each item dict has scheme_type, item_id, level, number, label_as_printed, demand_no,
    department, category, parent, page, values {(fiscal_year, kind): {revenue, capital, total}}.
    """
    path = Path(rows_or_path)
    where = f"{fy(start)} {scheme_type} {path.suffix[1:]}"
    fixes_used: list[str] = []
    if cell_based:
        lines, header_text, _ = read_sheet_lines(path)
        years = re.findall(r"(\d{4})\s*-\s*\d{2,4}", header_text)
        cols_all = _columns(" ".join(f"{y}-{int(y) + 1}" for y in [start - 2, start - 1, start - 1, start]), start)
        period_cells = re.findall(r"(Actuals|Budget Estimates|Budget|Revised Estimates|Revised)\s*(\d{4})", header_text)
        present = []
        for kind_word, year in period_cells:
            kind = "Actual" if kind_word.startswith("Actual") else ("RE" if kind_word.startswith("Revised") else "BE")
            idx = next((k for k, c in enumerate(cols_all) if c.kind == kind and c.fiscal_year == fy(int(year))), None)
            if idx is not None and idx not in present:
                present.append(idx)
        if not present or not years:
            raise ParseError(f"{where}: no period headings")
        # Spreadsheet rows only carry the periods present; spread them into the 12-slot layout.
        width = 3 * len(present)
        fixed = []
        for ln in lines:
            if len(ln.cells) != width:
                raise ParseError(f"{where}: expected {width} value cells, found {len(ln.cells)}")
            cells: list[str | None] = ["..."] * 12
            for k, idx in enumerate(present):
                cells[idx * 3: idx * 3 + 3] = ln.cells[k * 3: k * 3 + 3]
            if all(c is None for c in ln.cells):
                cells = [None] * 12
            fixed.append(Line(ln.label, cells, ln.page, ln.bottom))
        lines = fixed
        columns = cols_all
    else:
        lines = read_pdf_lines(path)
        lines, fixes_used = apply_text_layer_fixes(lines, fy(start), scheme_type)
        header_text = " ".join(ln.text for ln in lines[:40] if re.search(r"actual|budget|revised", ln.text, re.I))
        columns = _columns(header_text, start)
        present = [0, 1, 2, 3]

    items, unknown = lines_to_items(lines, where, lenient_numbering=cell_based)
    out = []
    for it in items:
        values = {}
        for k, col in enumerate(columns):
            if k not in present:
                continue
            r, c, t = it.values[k * 3: k * 3 + 3]
            values[(col.fiscal_year, col.kind)] = {"revenue": r, "capital": c, "total": t}
        out.append({
            "scheme_type": scheme_type,
            "level": it.level,
            "number": it.number,
            "label_as_printed": it.label,
            "demand_no": it.demand_no,
            "department": re.sub(r"\s+", " ", " ".join(it.department_parts)).strip() or None,
            "category": it.category,
            "parent": it.parent_number,
            "page": it.page,
            "values": values,
        })
    # The 2017-18 CSS layout appends the department to each name: "... (Department of Rural Development)".
    for i in out:
        m = re.match(r"^(.*?)\s*\(((?:Department|Ministry) of [^()]*?)\)?\s*\*?$", i["label_as_printed"])
        if scheme_type == "css" and start == 2017 and m and m.group(1):
            i["label_as_printed"], i["department"] = m.group(1).strip(), m.group(2).strip()
    # Department name for schemes = their demand's department.
    dept = {i["demand_no"]: i["department"] for i in out if i["level"] == "demand_subtotal"}
    for i in out:
        if i["level"] in ("scheme", "component") and i["demand_no"] and not i["department"]:
            i["department"] = dept.get(i["demand_no"])
    names = load_name_map()
    counts = defaultdict(int)
    for i in out:
        if i["level"] in ("scheme", "component"):
            counts[normalise_name(i["label_as_printed"])] += 1
    for i in out:
        i["item_id"] = item_id(i, names, fy(start))
        if i["level"] in ("scheme", "component") and counts[normalise_name(i["label_as_printed"])] > 1:
            # Generic names repeated under several departments ("Actual Recoveries"): qualify by department.
            i["item_id"] += "@" + slug(i["department"] or f"demand {i['demand_no']}")
    seen_ids: dict[str, int] = defaultdict(int)
    for i in out:
        seen_ids[i["item_id"]] += 1
        if seen_ids[i["item_id"]] > 1:
            # Same name twice in one department (e.g. Defence revenue and capital demands share a
            # department name): keep ids unique, and mark them so year-to-year matching skips them.
            i["item_id"] += f"#{seen_ids[i['item_id']]}"
            i["ambiguous_name"] = True
    dup = {k for k, n in seen_ids.items() if n > 1}
    for i in out:
        if i["item_id"] in dup:
            i["ambiguous_name"] = True
    return {"columns": columns, "items": out, "unknown_rows": unknown, "periods_present": present,
            "text_layer_fixes": fixes_used}


# ----- stable ids ------------------------------------------------------------


def normalise_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def slug(name: str) -> str:
    return normalise_name(name).replace(" ", "_")[:80]


def load_name_map() -> dict[tuple[str, str], list[dict]]:
    """(scheme_type, normalised printed name) -> rows {budgets, scheme_id, scheme_name, evidence}.
    A row applies to the budgets listed (blank = all)."""
    out: dict[tuple[str, str], list[dict]] = defaultdict(list)
    if NAME_MAP.exists():
        with NAME_MAP.open() as f:
            for r in csv.DictReader(f):
                r["budget_set"] = set(b for b in r["budgets"].split() if b)
                out[(r["scheme_type"], normalise_name(r["printed_name"]))].append(r)
    return out


def item_id(i: dict, names: dict, budget: str = "") -> str:
    t = i["scheme_type"]
    if i["level"] == "grand_total":
        return f"{t}:grand_total"
    if i["level"] == "demand_subtotal":
        return f"{t}:demand:{i['demand_no']}"
    if i["level"] == "category_subtotal":
        return f"{t}:category:{i['category']}"
    rows = names.get((t, normalise_name(i["label_as_printed"])), [])
    m = next((r for r in rows if not r["budget_set"] or budget in r["budget_set"]), None)
    base = m["scheme_id"] if m else slug(i["label_as_printed"])
    if i["level"] == "component":
        return f"{t}:component:{base}"
    return f"{t}:{base}"


# Renames that the name-similarity rule cannot see, each backed by the same Budget Estimate
# printed under the old name in one budget and under the new name in the next.
SEMANTIC_RENAMES: dict[str, list[tuple[str, str]]] = {
    "css": [
        ("rashtriya swasthya bima yojna", "pradhan mantri jan arogya yojana including rsby"),
        ("pradhan mantri jan arogya yojana including rsby", "rashtriya swasthya bima yojna"),
        ("rashtriya swasthya bima yojna", "prime minister jan aarogya yojana by subsuming rsby"),
        ("integrated child development services", "umbrella icds"),
        ("rashtriya pashudhan vikash yojana", "development programmes animal husbandry"),
        ("digitalization of primary agriculture cooperative societies",
         "computerization of primary agricultural credit societies"),
        ("national rural drinking water mission", "jal jeevan mission jjm national rural drinking water mission"),
        ("mahatma gandhi national rural employment guarantee programme", "mgnrega programme component"),
        ("swachh bharat mission gramin", "sbm grameen"),
        ("pradhan mantri awas yojna pmay urban", "pmay urban"),
        ("swachh bharat mission urban", "swachh bharat mission"),
        ("swachh bharat mission", "swachh bharat mission sbm urban"),
    ],
    "central_sector": [],
}

_STOP = {"of", "and", "the", "for", "in", "to", "on", "a", "an", "scheme", "schemes", "programme", "program"}


def _tokens_of(name: str) -> set[str]:
    return set(normalise_name(name).split()) - _STOP


def build_name_map(all_parsed: dict) -> list[dict]:
    """Propose the scoped name map from the parsed statements (run by hand, then reviewed).

    Two printed names are the same scheme when, in consecutive budgets, one disappears and
    the other appears with the same non-zero BE figure for the year both budgets print, and
    either the names share most words or the pair is listed in SEMANTIC_RENAMES. An
    unchanged name in consecutive budgets is the same scheme unless that shared BE figure
    differs by more than half (then the name changed meaning, e.g. "Swachh Bharat Mission").
    """
    budgets = sorted(all_parsed["budgets"])
    parent: dict[tuple, tuple] = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    evidence: dict[tuple, list[str]] = defaultdict(list)
    for t in SCHEME_TYPES:
        sem = {(a, b) for a, b in SEMANTIC_RENAMES.get(t, [])}
        by_budget = {}
        for y in budgets:
            e = all_parsed["budgets"][y][t]
            rows = [i for i in (e["parsed"] or {}).get("items", []) if i["level"] == "scheme"
                    and not i.get("ambiguous_name") and "@" not in i["item_id"]]
            by_budget[y] = {normalise_name(i["label_as_printed"]): i for i in rows}
            for n in by_budget[y]:
                find((t, y, n))
        for a, b in zip(budgets, budgets[1:]):
            A, B = by_budget[a], by_budget[b]

            def be(i, yr=a):
                v = i["values"].get((yr, "BE"))
                return v["total"] if v else None
            for n in set(A) & set(B):
                va, vb = be(A[n]), be(B[n])
                if va and vb and abs(va - vb) > 0.5 * max(abs(va), abs(vb)):
                    evidence[(t, b, n)].append(f"name kept but BE {a} changed {va:,.2f} -> {vb:,.2f}: treated as a new scheme")
                    continue
                union((t, a, n), (t, b, n))
            only_a = [n for n in A if n not in B]
            only_b = [n for n in B if n not in A]
            for n in only_a:
                va = be(A[n])
                if not va:
                    continue
                cands = []
                for m in only_b:
                    vb = be(B[m])
                    if vb is None or abs(va - vb) > 0.005:
                        continue
                    ta, tb = _tokens_of(n), _tokens_of(m)
                    jac = len(ta & tb) / max(1, len(ta | tb))
                    if jac >= 0.5 or (n, m) in sem or (len(ta & tb) >= 2 and (ta <= tb or tb <= ta)):
                        cands.append(m)
                if len(cands) == 1:
                    m = cands[0]
                    union((t, a, n), (t, b, m))
                    evidence[(t, b, m)].append(f"BE {a} {va:,.2f} printed as '{A[n]['label_as_printed']}' in "
                                               f"budget {a} and as '{B[m]['label_as_printed']}' in budget {b}")
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for node in list(parent):
        groups[find(node)].append(node)
    rows = []
    used_ids: dict[str, int] = defaultdict(int)
    for members in sorted(groups.values(), key=lambda g: (g[0][0], max(m[1] for m in g))):
        names = {m[2] for m in members}
        t = members[0][0]
        latest = max(members, key=lambda m: m[1])
        latest_label = next(i for i in all_parsed["budgets"][latest[1]][t]["parsed"]["items"]
                            if i["level"] == "scheme" and normalise_name(i["label_as_printed"]) == latest[2])["label_as_printed"]
        sid = slug(latest_label)
        used_ids[(t, sid)] += 1
        if used_ids[(t, sid)] > 1:
            sid += f"_{min(m[1] for m in members)[:4]}"
        if len(names) == 1 and all(not evidence.get(m) for m in members) and used_ids[(t, slug(latest_label))] == 1:
            continue  # one unchanged name, nothing to map
        by_name: dict[str, list[str]] = defaultdict(list)
        for m in members:
            by_name[m[2]].append(m[1])
        for n, ys in sorted(by_name.items()):
            label = next(i for i in all_parsed["budgets"][ys[0]][t]["parsed"]["items"]
                         if i["level"] == "scheme" and normalise_name(i["label_as_printed"]) == n)["label_as_printed"]
            ev = "; ".join(e for y in ys for e in evidence.get((t, y, n), []))
            rows.append({"scheme_type": t, "printed_name": label, "budgets": " ".join(sorted(ys)),
                         "scheme_id": sid, "scheme_name": latest_label, "evidence": ev})
    return rows


# ----- all budgets -------------------------------------------------------------


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
                if abs(va - vb) > TOLERANCE:
                    diffs.append({"item": k, "label": ia["label_as_printed"], "period": pk, "part": part,
                                  "primary": va, "other": vb})
    return diffs


def load_all() -> dict:
    """Parse every copy of both statements for every budget from 2017-18.

    Returns {"budgets": {year: {scheme_type: {"primary": ext, "parsed": result,
    "differences": {ext: [...]}, "errors": {ext: msg}, "source": manifest entry}}}}.
    """
    manifest = json.loads(MANIFEST.read_text())
    out: dict = {"budgets": {}}
    for start in range(FIRST_SCHEME_BUDGET, LATEST_BUDGET + 1):
        year = fy(start)
        for t in SCHEME_TYPES:
            files = manifest.get(year, {}).get(t, {}).get("files", {})
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


# ----- checks ------------------------------------------------------------------

RAILWAYS_2017 = (
    "Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union "
    "Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' "
    "internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: "
    "55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed."
)
GROSS_2017 = (
    "Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal "
    "in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and "
    "some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the "
    "difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed."
)
MOHUA_2018 = (
    "Budget 2018-19 Statement 4B, Ministry of Housing and Urban Affairs, Actual 2016-17: the schemes' total "
    "matches the Demand subtotal, but 314.00 crore is classed as capital in the subtotal and as revenue in the "
    "scheme rows. Shown as printed."
)
FUNDS_2024 = (
    "Budget 2024-25 Statement 4B: MNRE and Road Transport scheme rows include transfers to funds (2,000 and "
    "6,000 crore) that the Demand subtotals leave out; the statement's last row 'Others (including amount met "
    "from & transfer to various funds)' carries the offsetting -8,000 crore. The scheme rows add up exactly to "
    "the Grand Total. Budget 2025-26, which reprints these BE 2024-25 figures, keeps the Demands gross."
)
GT_2025_CSS = (
    "Budget 2025-26 Statement 4A Grand Total, BE 2025-26: printed revenue 5,36,826.78 (read from the page image; "
    "the row is missing from the text layer) but printed total 5,41,850.21 = 5,41,826.78 + 23.43, and the "
    "Demand subtotals add to 5,41,826.78 revenue. The printed revenue figure is 5,000 crore short; shown as printed."
)

# (budget, scheme_type, check, key) -> reason. Keys: rct "<level> <number>|<kind> <year>",
# group "<level> <number>|<kind> <year>" or "<level> <number>|*", grand "<kind> <year>|<part>".
# Each entry was verified by hand (page images, other columns, other budgets).
KNOWN_EXCEPTIONS: dict[tuple[str, str, str, str], str] = {
    ("2017-18", "central_sector", "group", "demand_subtotal 80|*"): RAILWAYS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 31|*"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 48|*"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 67|Actual 2015-16"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 81|Actual 2015-16"): GROSS_2017,
    ("2017-18", "central_sector", "group", "demand_subtotal 81|BE 2016-17"): GROSS_2017,
    ("2018-19", "central_sector", "group", "demand_subtotal 56|Actual 2016-17"): MOHUA_2018,
    ("2024-25", "central_sector", "group", "demand_subtotal 71|BE 2024-25"): FUNDS_2024,
    ("2024-25", "central_sector", "group", "demand_subtotal 86|BE 2024-25"): FUNDS_2024,
    ("2025-26", "css", "rct", "grand_total|BE 2025-26"): GT_2025_CSS,
    ("2025-26", "css", "grand", "BE 2025-26|revenue"): GT_2025_CSS,
}

# (budget, scheme_type, ext) -> why a secondary copy differs from the PDF (the PDF is used).
KNOWN_FORMAT_ISSUES: dict[tuple[str, str, str], str] = {
    ("2021-22", "css", "xlsx"): (
        "An earlier version: about 25,786 crore of BE 2021-22 sits in item 36 'Others' (26,446.35) instead of the "
        "named Core schemes (e.g. Saksham Anganwadi and Poshan 2.0, 20,105), so the Core and Others subtotals "
        "differ. The PDF's rows add up to its subtotals and Grand Total."
    ),
    ("2023-24", "css", "xls"): (
        "The Excel copy leaves BE 2023-24 blank for 'Assistance to States Agencies for Intra-State Movement of "
        "Foodgrains...' (the PDF and its page image show 7,424.60) and numbers two rows '58', so 'Others "
        "(Recoveries)' cannot be matched."
    ),
    ("2024-25", "central_sector", "xlsx"): (
        "A BE-2024-25-only copy that leaves out 8 Demands (5, 9, 43, 44, 45, 78, 92, 95) and their 79 schemes; "
        "every row it does have matches the PDF."
    ),
    ("2025-26", "css", "xlsx"): (
        "Has no Grand Total row, like the PDF's text layer (apparently converted from the PDF); every other row "
        "matches."
    ),
}


def _lab(i: dict) -> str:
    return f"{i['level']} {i['number']}".strip()


def _per(pk: tuple) -> str:
    return f"{pk[1]} {pk[0]}"


def _exc(year: str, t: str, check: str, key: str) -> str | None:
    if (year, t, check, key) in KNOWN_EXCEPTIONS:
        return KNOWN_EXCEPTIONS[(year, t, check, key)]
    wild = key.split("|")[0] + "|*"
    return KNOWN_EXCEPTIONS.get((year, t, check, wild))


def _v(x: float | None) -> float:
    return x or 0.0


def checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple[str, int, list[str], list[str]]]:
    results = []
    budgets = all_parsed["budgets"]

    # (a) Revenue + Capital = Total, every row and period.
    checked, fails, notes = 0, [], []
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            if not e["parsed"]:
                fails.append(f"Budget {year} {t}: no copy could be read: {e['errors']}")
                continue
            for i in e["parsed"]["items"]:
                for pk, v in i["values"].items():
                    checked += 1
                    diff = _v(v["revenue"]) + _v(v["capital"]) - _v(v["total"])
                    if abs(diff) > TOLERANCE:
                        reason = _exc(year, t, "rct", f"{_lab(i)}|{_per(pk)}")
                        msg = (f"Budget {year} {t}: {i['label_as_printed'][:60]!r} {pk[1]} {pk[0]}: "
                               f"{_v(v['revenue']):.2f} + {_v(v['capital']):.2f} != {_v(v['total']):.2f}")
                        (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
    results.append(("Schemes: revenue + capital = total in every row", checked, fails, notes))

    # (b) Schemes add up to their group subtotal; groups add up to the grand total.
    checked, fails, notes = 0, [], []
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            if not e["parsed"]:
                continue
            items = e["parsed"]["items"]
            schemes = [i for i in items if i["level"] == "scheme"]
            comps = [i for i in items if i["level"] == "component"]
            groups = [i for i in items if i["level"] in ("demand_subtotal", "category_subtotal")]
            grand = [i for i in items if i["level"] == "grand_total"]
            if len(grand) != 1:
                fails.append(f"Budget {year} {t}: expected one Grand Total row, found {len(grand)}")
                continue
            for pk in grand[0]["values"]:
                for part in PARTS:
                    # groups -> grand total
                    checked += 1
                    if groups:
                        # Group subtotals, plus any row printed outside every group (see lines_to_items).
                        s = sum(_v(g["values"][pk][part]) for g in groups) + sum(
                            _v(s_["values"][pk][part]) for s_ in schemes
                            if s_["demand_no"] is None and s_["category"] is None)
                    else:
                        s = sum(_v(s_["values"][pk][part]) for s_ in schemes)
                    gt = _v(grand[0]["values"][pk][part])
                    all_rows = sum(_v(s_["values"][pk][part]) for s_ in schemes)
                    if abs(s - gt) > 0.5 and abs(all_rows - gt) <= 0.5:
                        notes.append(f"Budget {year} {t} {pk[1]} {pk[0]} {part}: Grand Total equals the sum of all "
                                     f"scheme rows ({all_rows:,.2f}) but not of the group subtotals ({s:,.2f}).")
                    elif abs(s - gt) > 0.5:
                        reason = _exc(year, t, "grand", f"{_per(pk)}|{part}")
                        msg = f"Budget {year} {t} {pk[1]} {pk[0]} {part}: groups sum to {s:,.2f}, Grand Total {gt:,.2f}"
                        (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
                    # schemes -> each group
                    for g in groups:
                        members = [s_ for s_ in schemes if (s_["demand_no"] == g["demand_no"] if g["level"] == "demand_subtotal"
                                                            else s_["category"] == g["category"])]
                        checked += 1
                        s = sum(_v(m["values"][pk][part]) for m in members)
                        gv = _v(g["values"][pk][part])
                        if abs(s - gv) > 0.5:
                            reason = _exc(year, t, "group", f"{_lab(g)}|{_per(pk)}")
                            msg = (f"Budget {year} {t} {g['level']} {g['number']} ({(g['department'] or g['label_as_printed'])[:40]}) "
                                   f"{pk[1]} {pk[0]} {part}: schemes sum to {s:,.2f}, subtotal {gv:,.2f}")
                            (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
                    # components -> parent scheme (only where a scheme lists components)
                    for parent in {c["parent"] for c in comps}:
                        p_item = next((s_ for s_ in schemes if s_["number"] == parent), None)
                        members = [c for c in comps if c["parent"] == parent]
                        if p_item is None:
                            continue
                        checked += 1
                        s = sum(_v(m["values"][pk][part]) for m in members)
                        pv = _v(p_item["values"][pk][part])
                        if abs(s - pv) > 0.5:
                            reason = _exc(year, t, "component", f"scheme {parent}|{_per(pk)}")
                            msg = (f"Budget {year} {t} scheme {parent} {p_item['label_as_printed'][:40]!r} {pk[1]} {pk[0]} "
                                   f"{part}: components sum to {s:,.2f}, scheme {pv:,.2f}")
                            (notes if reason else fails).append(msg + (f". Explained: {reason}" if reason else ""))
    results.append(("Schemes add up to their subtotals and the Grand Total", checked, fails, notes))

    # (c) Same item, same period, printed in two budgets.
    checked, fails, notes = 0, [], []
    seen: dict[tuple, list[tuple[str, float, str]]] = defaultdict(list)
    ambiguous = 0
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            if not e["parsed"]:
                continue
            for i in e["parsed"]["items"]:
                if i["level"] not in ("scheme", "grand_total"):
                    continue
                if i.get("ambiguous_name"):
                    ambiguous += 1
                    continue
                for pk, v in i["values"].items():
                    if pk[1] == "BE" and pk[0] == year:
                        # The new year's BE is printed again next year: compare.
                        pass
                    seen[(t, i["item_id"], pk)].append((year, _v(v["total"]), i["label_as_printed"]))
    for (t, iid, pk), obs in sorted(seen.items(), key=lambda x: str(x[0])):
        if len(obs) < 2:
            continue
        checked += 1
        vals = {round(v, 2) for _, v, _ in obs}
        if len(vals) > 1:
            (a_year, a, lab), (b_year, b, _) = obs[0], obs[1]
            rel = abs(a - b) / max(abs(a), abs(b), 1)
            msg = (f"{t} {lab[:50]!r} {pk[1]} {pk[0]}: {a:,.2f} in budget {a_year} vs {b:,.2f} in budget {b_year}")
            reason = _exc("cross", t, iid, _per(pk))
            if reason:
                notes.append(msg + f". Explained: {reason}")
            elif pk[1] == "BE" and (rel <= 0.02 or abs(a - b) <= 5):
                notes.append("Restated: " + msg)
            elif pk[1] == "BE":
                notes.append("Restated (reorganised schemes): " + msg)
            else:
                fails.append(msg)
    notes.insert(0, f"{ambiguous} scheme rows not compared: the same name appears twice under one department "
                    "in that budget, so they cannot be matched across budgets by name.")
    results.append(("Same scheme figure agrees across the two budgets that print it", checked, fails, notes))

    # (d) Other copies agree with the PDF.
    checked, fails, notes = 0, [], []
    for year, by_type in budgets.items():
        for t, e in by_type.items():
            for ext, err in e["errors"].items():
                notes.append(f"Budget {year} {t}: {ext.upper()} copy could not be read ({err}).")
            for ext, diffs in e["differences"].items():
                checked += 1
                if not diffs:
                    notes.append(f"Budget {year} {t}: {ext.upper()} agrees with the PDF.")
                elif (year, t, ext) in KNOWN_FORMAT_ISSUES:
                    notes.append(f"Budget {year} {t}: {ext.upper()} differs in {len(diffs)} values (known): "
                                 f"{KNOWN_FORMAT_ISSUES[(year, t, ext)]}")
                else:
                    sample = "; ".join(f"{d.get('label', '')[:30]!r} {d.get('period', '')} {d.get('part', d.get('issue'))}: "
                                       f"{d.get('primary', '')} vs {d.get('other', '')}" for d in diffs[:3])
                    fails.append(f"Budget {year} {t}: {ext.upper()} differs from PDF in {len(diffs)} values ({sample})")
    results.append(("Scheme tables: other copies agree with the PDF", checked, fails, notes))

    # (e) Share of total expenditure (context, not an identity).
    notes = []
    total_exp = {(r["source_budget"], r["fiscal_year"], r["kind"]): float(r["value_crore"])
                 for r in summary_observations if r["field"] == "total_expenditure" and r["value_crore"]}
    for year, by_type in budgets.items():
        parts = []
        for t, e in by_type.items():
            if not e["parsed"]:
                continue
            g = next((i for i in e["parsed"]["items"] if i["level"] == "grand_total"), None)
            if g is None:
                continue
            v = g["values"].get((year, "BE"))
            te = total_exp.get((year, year, "BE"))
            if v and te:
                parts.append(f"{t} {v['total'] / te:.1%}")
        if parts:
            notes.append(f"Budget {year}, BE {year}: share of total expenditure: " + ", ".join(parts))
    results.append(("Scheme spending as a share of total expenditure (context only)", 0, [], notes))
    return results


if __name__ == "__main__":
    import sys

    data = load_all()
    obs_path = ROOT / "data" / "observations.csv"
    with obs_path.open() as f:
        summary = list(csv.DictReader(f))
    failed = False
    for title, n, fails, notes in checks(data, summary):
        print(f"{'FAIL' if fails else 'ok  '} {title}: {n} checks, {len(fails)} failures")
        for x in fails[:15]:
            print("   x", x)
        if "-v" in sys.argv:
            for x in notes[:40]:
                print("   -", x)
        failed |= bool(fails)
    sys.exit(1 if failed else 0)

"""Turning a statement's text lines into items (schemes, components, subtotals, Grand Total) with their values."""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..parse import Column, ParseError, expected_columns, fy
from .common import NA_TEXT, Line, _is_header
from .ids import item_id, load_name_map, normalise_name, slug
from .read import read_pdf_lines, read_sheet_lines
from .text_layer import apply_text_layer_fixes


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


@dataclass
class _Position:
    """Where lines_to_items has got to: the Demand and category being read, and the scheme numbering so far."""
    items: list[Item] = field(default_factory=list)
    demand: Item | None = None
    category: str | None = None
    last_scheme_no: int = 0
    last_scheme: Item | None = None
    in_department: bool = False  # label lines continue the Demand's department name
    gaps: list[str] = field(default_factory=list)
    used_numbers: set[int] = field(default_factory=set)


def _new_item(ln: Line, label: str, pos: _Position, lenient_numbering: bool) -> Item | None:
    """The item this line starts (a Demand, category, scheme or component), or None if it starts none."""
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
        pos.demand = new
        pos.in_department = True
    elif TOTAL_OF_RE.match(label) and ln.has_values and pos.category:
        new = Item("category_subtotal", pos.category, [label], page=ln.page, category=pos.category)
        pos.in_department = False
    elif RECOVERIES_RE.match(label) and ln.has_values and not m_no:
        new = Item("scheme", f"rec{len(pos.items)}", [label], page=ln.page)
        pos.in_department = False
    elif m_cat:
        pos.category = m_cat.group(1)
        new = Item("category_subtotal", pos.category, [m_cat.group(2)], page=ln.page, category=pos.category)
        pos.in_department = False
    elif (m_no and pos.demand is not None
          and re.match(r"^\d{1,3}\.?\s+Others \(including amount met from", label, re.I)
          and (int(m_no.group(1)) == pos.last_scheme_no + 1)):
        # The statement ends with a line for amounts met from / transferred to funds that belongs
        # to no Demand. Some years print an "Others" heading for it; give it its own group.
        pos.last_scheme_no = int(m_no.group(1))
        if pos.demand.demand_no != "others":
            # No printed heading or subtotal: this row stands on its own, outside any Demand.
            pos.demand = Item("demand_subtotal", "ungrouped", [], demand_no=None)
        new = Item("scheme", m_no.group(1), [label[m_no.end():]], page=ln.page)
        pos.in_department = False
    elif m_no and (int(m_no.group(1)) == pos.last_scheme_no + 1
                   or (lenient_numbering and ln.has_values and int(m_no.group(1)) not in pos.used_numbers)
                   or (ln.has_values and re.match(r"^\d{1,3}\.\s", label)
                       and pos.last_scheme_no + 1 < int(m_no.group(1)) <= pos.last_scheme_no + 3)):
        if int(m_no.group(1)) != pos.last_scheme_no + 1 and not lenient_numbering:
            pos.gaps.append(f"numbering skips from {pos.last_scheme_no} to {m_no.group(1)}")
        pos.last_scheme_no = int(m_no.group(1))
        pos.used_numbers.add(pos.last_scheme_no)
        new = Item("scheme", m_no.group(1), [label[m_no.end():]], page=ln.page)
        pos.in_department = False
    elif (m_comp and ln.has_values and pos.category is not None
          and re.fullmatch(r"[IVX]+", m_comp.group(1) or "")
          and (pos.last_scheme is None or pos.last_scheme.category != pos.category
               or re.fullmatch(r"[IVX]+", pos.last_scheme.number))):
        # 2020-21: the "(C) Others" category numbers its schemes I., II., ...
        new = Item("scheme", m_comp.group(1), [label[m_comp.end():]], page=ln.page)
        pos.in_department = False
    elif m_comp and pos.last_scheme is not None and (ln.has_values or (m_comp.group(2) and len(label) > 3)):
        # Components carry their own numbers, except the 2017-18 layout ("b Civil Rights ...")
        # where a name can wrap above its numbers; a bare "II)" line is a wrapped scheme name.
        letter = m_comp.group(1) or m_comp.group(2)
        new = Item("component", letter, [label[m_comp.end():]], page=ln.page,
                   parent_number=pos.last_scheme.number)
        pos.in_department = False
    if new is not None:
        if new.level in ("scheme", "component"):
            new.demand_no = pos.demand.demand_no if pos.demand else None
            new.category = pos.category
            if new.level == "scheme":
                pos.last_scheme = new
        elif new.level == "category_subtotal" and not TOTAL_OF_RE.match(label):
            pos.last_scheme = None
    return new


def _complete(items: list[Item], where: str) -> list[Item]:
    """Drop category headings without numbers (2017-18 layout); every other item must have its 12 numbers."""
    items = [it for it in items if not (it.level == "category_subtotal" and it.values is None)]
    for it in items:
        if it.values is None:
            raise ParseError(f"{where}: {it.level} {it.number} {it.label!r} has no values")
        if len(it.values) != 12:
            raise ParseError(f"{where}: {it.level} {it.number} has {len(it.values)} values")
    return items


def lines_to_items(lines: list[Line], where: str, lenient_numbering: bool = False) -> tuple[list[Item], list[str]]:
    pos = _Position()
    items = pos.items
    unknown: list[str] = []
    current: Item | None = None

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
        new = _new_item(ln, label, pos, lenient_numbering)
        if new is not None:
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
        if current.level == "demand_subtotal" and pos.in_department:
            current.department_parts.append(label)
        else:
            current.label_parts.append(label)
    unknown.extend(f"note: {g}" for g in pos.gaps)
    return _complete(items, where), unknown


def _columns(header_text: str, start: int) -> list[Column]:
    cols = expected_columns(header_text, start)
    if len(cols) != 4:
        raise ParseError(f"{fy(start)}: expected 4 periods, found {[(c.fiscal_year, c.kind) for c in cols]}")
    return cols


def _sheet_lines(path: Path, start: int, where: str) -> tuple[list[Line], list[Column], list[int]]:
    """A spreadsheet copy's lines spread into the 12-cell layout of the PDF, with the four periods' columns and the
    indices of the periods the copy has (some copies have only the new BE)."""
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
    return fixed, cols_all, present


def _assign_ids(out: list[dict], start: int) -> None:
    """Give each item its stable id; qualify names repeated under several departments, and mark names repeated
    within one so year-to-year matching skips them."""
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
        lines, columns, present = _sheet_lines(path, start, where)
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
    _assign_ids(out, start)
    return {"columns": columns, "items": out, "unknown_rows": unknown, "periods_present": present,
            "text_layer_fixes": fixes_used}

"""The Budget at a Glance Receipts table: columns, PDF lines and the parser."""

import re

from ..parse import NA_TOKENS, YEAR_RE, Column, ParseError, ascii_text, fy, parse_cell, read_row_cells, value_positions
from .common import DEDUCTIONS, END_FIELD, GST_PARTS, NON_TAX_PARTS, match_item, printed_label, slug


def receipts_columns(header_text: str, start: int) -> list[Column]:
    years = [int(m.group(1)) for m in YEAR_RE.finditer(header_text)]
    low = header_text.lower()

    def contains(sub: list[int]) -> bool:
        return any(years[i : i + len(sub)] == sub for i in range(len(years) - len(sub) + 1))

    five = [start - 2, start - 1, start - 1, start - 1, start]
    four = [start - 2, start - 1, start - 1, start]
    three = [start - 1, start - 1, start]
    if "provisional" in low and contains(five):
        return [Column(fy(y), k) for y, k in zip(five, ["Actual", "BE", "RE", "PA", "BE"])]
    if "actual" in low and contains(four):
        return [Column(fy(y), k) for y, k in zip(four, ["Actual", "BE", "RE", "BE"])]
    if "actual" not in low and contains(three):
        return [Column(fy(y), k) for y, k in zip(three, ["BE", "RE", "BE"])]
    raise ParseError(f"{fy(start)}: unexpected column years {years} in the Receipts header")


# ----- reading PDF lines -------------------------------------------------------


def read_pdf_line(cells, ncols: int, anchors: list[float]) -> tuple[str, list[float | None] | None]:
    """Return (label, values) for a PDF line. Numbers left of the value columns
    (e.g. the '2' in 'Total Revenue Receipts (1a + 2)') are part of the label.
    values is None if the line has no numbers in the value columns."""
    label = cells[0] if cells else ""
    raw = list(cells[1:])
    xs = list(getattr(cells, "xs", []))
    if len(xs) != len(raw):
        raise ParseError("PDF line without positions")
    left_edge = min(anchors) - 30
    extra_label, toks = [], []
    raw = [".." if re.fullmatch(r"\.{2,}", t) else t for t in raw]  # "...." also means not available
    for tok, x in zip(raw, xs):
        if x < left_edge:
            extra_label.append(tok)
        else:
            toks.append((tok, x))
    # "(-)" or "-" printed before a number is its sign.
    joined: list[tuple[str, float]] = []
    sign = False
    for tok, x in toks:
        if tok in ("(-)", "-") and len(toks) > 1:
            sign = True
            continue
        if sign and not tok.startswith("-") and tok not in NA_TOKENS:
            tok = "-" + tok
        sign = False
        joined.append((tok, x))
    if not joined:
        return " ".join([label, *extra_label]).strip(), None
    placed: dict[int, float | None] = {}
    for tok, x in joined:
        ok, amount, pct = parse_cell(tok)
        if not ok or pct is not None:
            raise ParseError(f"unexpected token {tok!r} in {label!r}")
        col = min(range(ncols), key=lambda c: abs(anchors[c] - x))
        if abs(anchors[col] - x) > 25:
            raise ParseError(f"number {tok!r} at x={x:.0f} is not under any column in {label!r}")
        if col in placed:
            raise ParseError(f"two numbers in one column in {label!r}")
        placed[col] = amount
    return " ".join([label, *extra_label]).strip(), [placed.get(c) for c in range(ncols)]


# ----- the parser ------------------------------------------------------------


def parse_receipts(rows: list[list[str]], start: int, cell_based: bool) -> dict:
    first = next(
        (i for i, r in enumerate(rows) if re.search(r"gross tax revenue", ascii_text(" ".join(r)).lower())), None
    )
    if first is None:
        raise ParseError(f"{fy(start)}: no 'Gross Tax Revenue' row - not the Receipts table")
    header_text = " ".join(" ".join(r) for r in rows[max(0, first - 15) : first])
    columns = receipts_columns(header_text, start)
    ncols = len(columns)

    if cell_based:
        offsets, anchors = value_positions(rows, first, ncols), None
    else:
        xs = getattr(rows[first], "xs", None)
        if not xs or len(xs) != ncols:
            raise ParseError(f"{fy(start)}: 'Gross Tax Revenue' line has {len(xs or [])} values, expected {ncols}")
        offsets, anchors = None, xs
    items, unknown = _receipt_items(_receipt_lines(rows[first:], start, ncols, offsets, anchors), start)
    return {"columns": columns, "items": items, "unknown_rows": unknown}


def _receipt_lines(rows: list[list[str]], start: int, ncols: int, offsets: list[int] | None,
                   anchors: list[float] | None) -> list[tuple[str, list[float | None] | None]]:
    """Pass 1: turn rows into (label, values-or-None) lines. Spreadsheet rows are read by cell offsets, PDF lines by
    the positions of their numbers (anchors)."""
    lines: list[tuple[str, list[float | None] | None]] = []
    pending_text = ""
    for cells in rows:
        if lines and lines[-1][1] is not None and END_FIELD in (
            match_item(lines[-1][0]), match_item(pending_text + " " + lines[-1][0])
        ):
            break  # the revenue part ends with Total Revenue Receipts; charts and capital receipts follow
        if lines:
            pending_text = lines[-1][0] if lines[-1][1] is None else ""
        if offsets is not None:
            row = read_row_cells(cells, offsets)
            if row is None:
                continue
            if not row.amounts and not row.pcts:
                lines.append((row.label, None))
                continue
            if row.pcts:
                raise ParseError(f"{fy(start)}: unexpected percentages in {row.label!r}")
            if len(row.amounts) != ncols:
                raise ParseError(f"{fy(start)}: {row.label!r} has {len(row.amounts)} values, expected {ncols}")
            lines.append((row.label, row.amounts))
        else:
            label, values = read_pdf_line(cells, ncols, anchors)
            lines.append((label, values))
    return lines


def _receipt_items(lines: list[tuple[str, list[float | None] | None]], start: int) -> tuple[list[dict], list[str]]:
    """Pass 2: assign meaning. A wrapped label is either before the numbers (pending text) or right after them
    (continuation), so try both."""
    items: list[dict] = []
    unknown: list[str] = []
    section = "gross"
    seen: set[str] = set()
    pending = ""
    for i, (label, values) in enumerate(lines):
        if values is None:
            pending = (pending + " " + label).strip()
            continue
        nxt = next((lab for lab, v in lines[i + 1 : i + 2] if v is None), "")
        item = match_item(label)
        printed = label
        if nxt and match_item(label + " " + nxt) == "states_share_adjustment":
            # "Less- States' share" + "adjustment for prior years in RE" on the next line
            item, printed = "states_share_adjustment", label + " " + nxt
        if item is None and pending:
            item = match_item(pending + " " + label)
            printed = pending + " " + label
        if item is None and nxt:
            item = match_item(label + " " + nxt)
            printed = label + " " + nxt
        pending = ""

        # Sections follow the table's order.
        if item == "gross_tax_revenue":
            section = "gross"
        elif item in DEDUCTIONS:
            section = "deduction"
        elif item == "net_tax_revenue":
            section = "net"
        elif item in NON_TAX_PARTS or item == "non_tax_revenue_total":
            section = "non_tax"

        if section == "deduction" and item not in DEDUCTIONS:
            # Lines under "Less States' Share" that split it by tax (2000s).
            item_id, item_section = f"states_share_of:{item or slug(label)}", "deduction_detail"
        elif item is None:
            if section != "gross":
                unknown.append(f"{ascii_text(printed)!r} -> {values}")
                continue
            item_id, item_section = f"other:{slug(label)}", "gross"
            unknown.append(f"(kept as gross component) {ascii_text(printed)!r} -> {values}")
        elif item in GST_PARTS:
            item_id, item_section = item, "gst_part"
        elif item == END_FIELD:
            item_id, item_section = item, "total"
        elif item == "gross_tax_revenue":
            item_id, item_section = item, "gross_total"
        elif section == "gross":
            item_id, item_section = item, "gross"
        else:
            item_id, item_section = item, section

        if item_id in seen:
            raise ParseError(f"{fy(start)}: {item_id!r} appears twice (second time as {ascii_text(printed)!r})")
        seen.add(item_id)
        items.append(
            {"item_id": item_id, "label_as_printed": printed_label(printed, item), "values": values,
             "section": item_section}
        )
        if item == END_FIELD:
            break
    else:
        raise ParseError(f"{fy(start)}: no 'Total Revenue Receipts' row found")

    for need in ("gross_tax_revenue", "states_share", "net_tax_revenue", "revenue_receipts_total"):
        if need not in seen:
            raise ParseError(f"{fy(start)}: {need} not found")
    return items, unknown

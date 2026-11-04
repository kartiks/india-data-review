"""Reading a statement into text lines: PDFs with the positions of their numbers, spreadsheets by their
sub-header row."""

from __future__ import annotations

import re
from pathlib import Path

from ..parse import ParseError, ascii_text
from ..readers import FOOTNOTE_SIZE, body_size, drop_small_chars, group_lines
from .common import NA, TWO_DEC, Line, _strip_furniture


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
        # Body size from the digits of the first two pages: the whole table uses one type size.
        body = body_size([round(c["size"], 1) for p in pdf.pages[:2] for c in p.chars if c["text"].isdigit()], 8.0)
        for pno, page in enumerate(pdf.pages):
            page = drop_small_chars(page, body * FOOTNOTE_SIZE)
            words = page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
            for ws in group_lines(words, tol=2.0):
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

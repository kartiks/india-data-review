"""Turn each source file (HTML, XLS, XLSX, PDF) into plain rows of text cells.

The parser downstream only sees `list[list[str]]`, so the format-specific
quirks stay in this file.
"""

import html
import re
from pathlib import Path


def _clean(text: str) -> str:
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def read_html(path: Path) -> list[list[str]]:
    raw = path.read_bytes().decode("latin-1")
    raw = re.sub(r"<sup\b.*?</sup>", " ", raw, flags=re.S | re.I)  # footnote markers
    rows = []
    for tr in re.findall(r"<tr\b.*?</tr>", raw, flags=re.S | re.I):
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)
        cells = [_clean(re.sub(r"<[^>]+>", " ", c)) for c in cells]
        if any(cells):
            rows.append(cells)
    return rows


def read_xls(path: Path) -> list[list[str]]:
    import xlrd

    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)
    rows = []
    for r in range(sheet.nrows):
        cells = []
        for v in sheet.row_values(r):
            if isinstance(v, float):
                v = repr(v) if v != int(v) else str(int(v))
            cells.append(_clean(str(v)))
        if any(cells):
            rows.append(cells)
    return rows


def read_xlsx(path: Path) -> list[list[str]]:
    import openpyxl

    book = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet = book.worksheets[0]
    rows = []
    for values in sheet.iter_rows(values_only=True):
        cells = []
        for v in values:
            if v is None:
                v = ""
            elif isinstance(v, float):
                v = repr(v) if v != int(v) else str(int(v))
            cells.append(_clean(str(v)))
        if any(cells):
            rows.append(cells)
    return rows


NUM_TOKEN = re.compile(r"^-?\(?-?[\d,]+(\.\d+)?\)?[*$@#]*$|^\.{2,}$|^…$|^\(-\)$|^-$")
SUPERSCRIPT_MAX_SIZE = 7.0  # footnote markers are ~6pt; body text is 9-11pt
FOOTNOTE_SIZE = 0.75  # characters below this share of the body text size are footnote markers


# ----- shared steps of the PDF line readers ---------------------------------------------------------------------
# Three readers turn PDF pages into text lines: read_pdf below (the headline and Receipts tables) and the
# position-based readers of the ministries and schemes tables. They share these steps; the tables differ in type
# size and line spacing, so each reader passes its own cut-off and tolerance.


def body_size(sizes: list[float], default: float) -> float:
    """The most common character size (the body text), or `default` when there are no characters."""
    return max(set(sizes), key=sizes.count) if sizes else default


def drop_small_chars(page, min_size: float):
    """The page without characters smaller than `min_size`: superscript footnote markers, which would otherwise
    glue onto the number they follow (a footnote "1" printed after 62043 reads as 620431)."""
    return page.filter(lambda obj: obj.get("object_type") != "char" or obj.get("size", 99) >= min_size)


def group_lines(words: list[dict], tol: float) -> list[list[dict]]:
    """Group words into text lines, top to bottom, each line left to right. A word joins the line above when its
    bottom edge (baseline) is within `tol` points of the line's last word: numbers with a trailing symbol like "$"
    can sit a point higher than the rest of the line."""
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


class PdfLine(list):
    """A PDF text line as [label, value, value, ...] plus each value's right edge (x1)."""

    xs: list[float]


def read_pdf(path: Path) -> list[list[str]]:
    """Read PDF text lines, keeping the horizontal position of each number.

    Small superscript characters (footnote markers) are dropped first,
    otherwise a footnote "1" printed after 62043 reads as 620431.
    Positions let the parser put a number in the right column even when
    another cell on the line is blank.
    """
    import pdfplumber

    rows: list[list[str]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page = drop_small_chars(page, SUPERSCRIPT_MAX_SIZE)
            words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
            for line in group_lines(words, tol=2.5):
                values: list[dict] = []
                while line and NUM_TOKEN.match(line[-1]["text"]):
                    values.insert(0, line.pop())
                label = _clean(" ".join(w["text"] for w in line))
                if not label and not values:
                    continue
                row = PdfLine([label, *[v["text"] for v in values]])
                row.xs = [v["x1"] for v in values]
                rows.append(row)
    return rows


def read_any(path: Path) -> list[list[str]]:
    ext = path.suffix.lower()
    return {
        ".htm": read_html,
        ".html": read_html,
        ".xls": read_xls,
        ".xlsx": read_xlsx,
        ".pdf": read_pdf,
    }[ext](path)

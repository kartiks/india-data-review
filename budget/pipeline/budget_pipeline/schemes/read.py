"""Reading a statement into text lines of 12 value cells: PDFs by the position of each character, spreadsheets by
their period headings."""

import re
from pathlib import Path

from ..parse import ParseError
from ..readers import FOOTNOTE_SIZE, body_size, drop_small_chars, group_lines, read_any
from .common import PARTS, Line, _is_header


def _is_numberish(text: str) -> bool:
    return bool(text) and re.fullmatch(r"[\d.,\-*…()]+", text) is not None and re.search(r"[\d.…]", text) is not None


LINE_TOL = 2.5  # points between the bottom edges of words on one line


def _anchors(pages_words: list[list[dict]]) -> list[float]:
    """Right edges of the 12 value columns, from lines that hold exactly 12 numbers."""
    samples: list[list[float]] = []
    for words in pages_words:
        for line in group_lines(words, LINE_TOL):
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


def read_pdf_lines(path: Path) -> list[Line]:
    import pdfplumber

    pages_words: list[list[dict]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            # Drop superscript footnote markers: characters much smaller than the page's body text.
            # (A fixed cut-off fails: some years print "Grand Total" at 6.8pt.)
            body = body_size(sorted(round(c["size"], 1) for c in page.chars), 10.0)
            page = drop_small_chars(page, FOOTNOTE_SIZE * body)
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
        for line in group_lines(words, LINE_TOL):
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

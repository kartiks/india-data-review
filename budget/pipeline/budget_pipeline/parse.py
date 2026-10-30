"""Extract the headline table from one Budget at a Glance document.

Input: rows of text cells (from readers.py). Output: one observation per
(line item, column), keeping the label as printed so a person can find it in
the source document.

The table layout changed several times between 2000 and 2026 (Plan/Non-plan
split until 2016-17, a "Scheme" split in 2017-18, a simpler layout after),
so line items are recognised by their English label, not by row number.

Two ways of reading values:
- spreadsheets and HTML keep each column in a fixed cell, so values are read
  by the column positions found in the header row;
- PDF text has no cells, so values are the trailing numeric tokens of a line.
Either way, the number of values must match the number of columns exactly,
or parsing stops with an error rather than guessing.
"""

import re
from dataclasses import dataclass

# Canonical line items, matched against the English label after removing the
# item number (e.g. "17. ").
FIELD_PATTERNS: list[tuple[str, str]] = [
    ("revenue_receipts", r"^revenue receipts"),
    ("tax_revenue_net", r"^tax revenue"),
    ("non_tax_revenue", r"^non[- ]?tax revenue"),
    ("capital_receipts", r"^capital receipts"),
    ("recoveries_of_loans", r"^recover(y|ies) of loans"),
    ("other_receipts", r"^other receipts"),
    ("borrowings", r"^borrowings?\b"),
    ("total_receipts", r"^total receipts"),
    ("total_expenditure", r"^total expenditure"),
    ("revenue_expenditure", r"^revenue expenditure"),
    ("interest_payments", r"^interest payments"),
    ("grants_capital_assets", r"^grants?\b"),
    ("capital_expenditure", r"^capital expenditure"),
    ("effective_capital_expenditure", r"^effective capital"),
    ("revenue_deficit", r"^revenue deficit"),
    ("effective_revenue_deficit", r"^effective revenue"),
    ("fiscal_deficit", r"^fiscal deficit"),
    ("primary_deficit", r"^primary deficit"),
]
DEFICITS = ("revenue_deficit", "effective_revenue_deficit", "fiscal_deficit", "primary_deficit")
# Rows we know about but don't publish (Plan/Non-plan split etc.).
IGNORED_PATTERNS = [
    r"^non-?plan expenditure", r"^plan expenditure", r"^scheme expenditure",
    r"^expenditure on other", r"^lump sum", r"^of which disinvestment",
    r"^on revenue account", r"^on capital account", r"^than schemes",
]

YEAR_RE = re.compile(r"(?<!\d)(\d{4})\s*-\s*(\d{4}|\d{2})(?!\d)")
ITEM_NO_RE = re.compile(r"(?:^|\s)\d{1,2}\s*(?:\.\s*(?=[A-Za-z])|\s+(?=[A-Z][a-z]))")
NUM_RE = re.compile(r"^-?[\d,]*\d(\.\d+)?$")
PCT_RE = re.compile(r"^-?\((-?[\d.]+)\)$")
NA_TOKENS = {"...", "..", "....", ".....", "…", "-", "--", "—", "–", "NA", "N.A.", "nil", "Nil"}
FOOTNOTE_CHARS = "*$@#†¹²³"


class ParseError(Exception):
    pass


@dataclass
class Column:
    fiscal_year: str  # e.g. "2024-25"
    kind: str  # "Actual", "BE", "RE" or "PA" (provisional actuals)


@dataclass
class Observation:
    field: str
    fiscal_year: str
    kind: str
    value: float | None
    pct_gdp: float | None
    label_as_printed: str


def fy(start: int) -> str:
    return f"{start}-{str(start + 1)[-2:]}"


def ascii_text(text: str) -> str:
    text = "".join(ch if ord(ch) < 128 else " " for ch in text)
    return re.sub(r"\s+", " ", text).strip()


def label_key(label: str) -> str:
    """'7. Borrowings and other liabilities$' -> 'borrowings and other liabilities$'."""
    text = ascii_text(label)
    matches = list(ITEM_NO_RE.finditer(text))
    if matches:
        text = text[matches[-1].end():]
    key = text.lower()
    key = re.sub(r"^[\d\s.:,()$*@#{}\[\]+-]+", "", key)
    key = re.sub(r"^(of which,?|which,?)\s*", "", key)
    return key.strip()


def match_field(label: str) -> str | None:
    key = label_key(label)
    for field, pat in FIELD_PATTERNS:
        if re.search(pat, key):
            return field
    return None


def is_ignored(label: str) -> bool:
    key = label_key(label)
    return any(re.search(p, key) for p in IGNORED_PATTERNS)


def normalise(text: str) -> str:
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"(?<!\S)(?:-|\(-\))\s*(?=\()", "-", text)  # "- (0.2)" is a negative percentage
    text = re.sub(r"\(-\)\s*(?=\d)", "-", text)  # "(-) 8047" is negative
    return text


def parse_cell(cell: str) -> tuple[bool, float | None, float | None]:
    """Parse one value cell -> (ok, amount, pct). Accepts '100162 (4.3)', '140955*', '...', '(3.3)', ''."""
    text = normalise(cell.replace("\xa0", " ")).strip()
    if not text:
        return True, None, None
    amount = pct = None
    for tok in text.split():
        tok = tok.rstrip(FOOTNOTE_CHARS)
        if not tok:
            continue
        m = PCT_RE.match(tok)
        if m:
            pct = float(m.group(1))
            if tok.startswith("-"):
                pct = -abs(pct)
        elif NUM_RE.match(tok):
            amount = float(tok.replace(",", ""))
        elif tok in NA_TOKENS or re.fullmatch(r"\.{2,}", tok):
            pass
        else:
            return False, None, None
    return True, amount, pct


# ----- column detection -------------------------------------------------


def expected_columns(header_text: str, start: int) -> list[Column]:
    years = [int(m.group(1)) for m in YEAR_RE.finditer(header_text)]
    four = [start - 2, start - 1, start - 1, start]
    five = [start - 2, start - 1, start - 1, start - 1, start]

    def contains(seq: list[int], sub: list[int]) -> bool:
        return any(seq[i : i + len(sub)] == sub for i in range(len(seq) - len(sub) + 1))

    if "provisional" in header_text.lower() and contains(years, five):
        return [Column(fy(y), k) for y, k in zip(five, ["Actual", "BE", "RE", "PA", "BE"])]
    if contains(years, four):
        return [Column(fy(y), k) for y, k in zip(four, ["Actual", "BE", "RE", "BE"])]
    raise ParseError(f"{fy(start)}: unexpected column years {years} in the table header")


def value_positions(rows: list[list[str]], first: int, ncols: int) -> list[int]:
    """For cell-based formats: value columns as offsets from the END of the row.

    Header rows sometimes have an extra leading cell (HTML), so positions are
    counted from the right, where the value columns always sit.
    """
    for cells in reversed(rows[max(0, first - 12) : first]):
        idx = [i for i, c in enumerate(cells) if YEAR_RE.search(c)]
        if len(idx) >= ncols:
            return [len(cells) - i for i in idx[-ncols:]]
    raise ParseError("could not locate the value columns in the header")


# ----- row reading --------------------------------------------------------


@dataclass
class Row:
    label: str
    amounts: list[float | None]  # empty if the row has no values
    pcts: list[float | None]


def read_row_cells(cells: list[str], offsets: list[int]) -> Row | None:
    """Read values at fixed offsets from the end of the row (see value_positions)."""
    if len(cells) < offsets[0]:
        # Too short to hold all value columns: a heading or a wrapped label line.
        return Row(" ".join(c for c in cells if c.strip()), [], []) if not any(
            parse_cell(c)[1] is not None for c in cells
        ) else None
    start = len(cells) - offsets[0]
    label = " ".join(c for c in cells[:start] if c.strip())
    amounts, pcts, any_value = [], [], False
    for off in offsets:
        cell = cells[len(cells) - off]
        ok, a, pc = parse_cell(cell)
        if not ok:
            return None  # text in a value column: a heading or note, not a data row
        any_value |= a is not None or pc is not None or cell.strip() in NA_TOKENS
        amounts.append(a)
        pcts.append(pc)
    if not any_value:
        return Row(label, [], [])
    if all(a is None for a in amounts) and any(p is not None for p in pcts):
        return Row(label, [], pcts)
    return Row(label, amounts, pcts if any(p is not None for p in pcts) else [])


def read_row_tokens(cells: list[str], ncols: int, anchors: list[float] | None) -> Row | None:
    """Read a PDF line. With column anchors (right edges of the value columns),
    each number goes to the nearest column, so blank cells stay blank."""
    label = cells[0] if cells else ""
    raw = list(cells[1:])
    xs = list(getattr(cells, "xs", [None] * len(raw)))
    # Join sign markers like "(-)" / "-" with the number after them.
    tokens: list[tuple[str, float | None]] = []
    sign = ""
    for tok, x in zip(raw, xs):
        if tok in ("(-)", "-") and len(raw) > ncols:
            sign = "-"
            continue
        tokens.append((sign + tok if sign and not tok.startswith("-") else tok, x))
        sign = ""
    amounts: list[float | None] = []
    pcts: list[float | None] = []
    placed_a: dict[int, float | None] = {}
    placed_p: dict[int, float | None] = {}
    use_pos = anchors is not None and all(x is not None for _, x in tokens) and len(tokens) not in (0, ncols)
    for tok, x in tokens:
        ok, a, pc = parse_cell(tok)
        if not ok:
            return None
        if use_pos:
            col = min(range(ncols), key=lambda c: abs(anchors[c] - x))
            if abs(anchors[col] - x) > 25:
                return None  # a number outside the value columns (e.g. a year in a note)
            if pc is not None:
                placed_p[col] = pc
            else:
                placed_a[col] = a
        elif pc is not None:
            pcts.append(pc)
        else:
            amounts.append(a)
    if use_pos:
        amounts = [placed_a.get(c) for c in range(ncols)] if placed_a else []
        pcts = [placed_p.get(c) for c in range(ncols)] if placed_p else []
    return Row(label, amounts, pcts)


GDP_RE = re.compile(
    r"GDP for (?:the )?(?:Budget )?(?:BE|FY|Budget Estimates?)?\s*(?:FY\s*)?(\d{4}\s*-\s*\d{2,4})"
    r"(?:\s*\([A-Za-z]+\))?.{0,40}?(?:projected|estimated)\s+at[\s`%]{0,6}([\d,]{6,})\s*crore",
    re.I | re.S,
)


def parse_document(rows: list[list[str]], start: int, cell_based: bool) -> dict:
    # 1. Find the first data row and the column layout above it.
    first = None
    for i, cells in enumerate(rows):
        if any(match_field(c) == "revenue_receipts" for c in cells) and any(
            NUM_RE.match(c.strip().rstrip(FOOTNOTE_CHARS)) and len(c.strip()) > 3 for c in cells
        ):
            first = i
            break
    if first is None:
        raise ParseError(f"{fy(start)}: could not find the 'Revenue Receipts' row")
    header_text = " ".join(" ".join(c) for c in rows[max(0, first - 12) : first])
    columns = expected_columns(header_text, start)
    ncols = len(columns)
    positions = value_positions(rows, first, ncols) if cell_based else []
    anchors = None
    if not cell_based:
        xs = getattr(rows[first], "xs", None)
        if xs and len(xs) == ncols:
            anchors = xs  # right edges of the value columns, from the Revenue Receipts line

    found: dict[str, Row] = {}
    labels: dict[str, str] = {}
    unknown: list[str] = []
    pending = ""
    last: str | None = None
    after_total = False

    for cells in rows[first:]:
        row = read_row_cells(cells, positions) if cell_based else read_row_tokens(cells, ncols, anchors)
        if row is None:
            continue
        own = ascii_text(row.label)
        if not row.amounts and not row.pcts:
            if "primary_deficit" in found and re.search(r"note|actuals for|^[$*@#]|^\d\s", own, re.I):
                break  # footnotes below the table
            pending = (pending + " " + own).strip()
            continue

        label = own if match_field(own) or is_ignored(own) else (pending + " " + own).strip()
        pending = ""
        field = match_field(label)

        # A "% of GDP" line under a deficit: no label of its own, small decimals.
        # Spreadsheets store "(3.3)" as -3.3, so accept that shape too.
        looks_pct = not field and last in DEFICITS and (
            (row.pcts and not any(a is not None for a in row.amounts))
            or (row.amounts and any(a is not None for a in row.amounts) and all(a is None or abs(a) < 30 for a in row.amounts) and not re.search(r"[a-z]{3}", label_key(own)))
        )
        if looks_pct:
            values = row.pcts if row.pcts else [None if a is None else abs(a) for a in row.amounts]
            if len(values) != ncols:
                raise ParseError(f"{fy(start)}: {len(values)} % of GDP values under {last}, expected {ncols}")
            found[last].pcts = values
            continue
        if "primary_deficit" in found:
            break  # the primary deficit is the table's last line; later tables in a booklet are not ours

        if field is None and after_total and "revenue_expenditure" not in found and re.search(r"^on revenue\b", label_key(label)):
            field = "revenue_expenditure"  # from 2017-18: total revenue spending, listed after Total Expenditure
        elif field is None and after_total and "capital_expenditure" not in found and re.search(r"^on capital\b", label_key(label)):
            field = "capital_expenditure"
        if field is None:
            if not is_ignored(label):
                unknown.append(f"{label!r} -> {row.amounts}")
            last = None
            continue
        if field in found:
            raise ParseError(f"{fy(start)}: '{field}' appears twice (second time as {label!r})")
        if len(row.amounts) != ncols:
            raise ParseError(f"{fy(start)}: {label!r} has {len(row.amounts)} values, expected {ncols}")
        if row.pcts and len(row.pcts) != ncols:
            raise ParseError(f"{fy(start)}: {label!r} has {len(row.pcts)} % of GDP values, expected {ncols}")
        found[field] = row
        labels[field] = label_key(label)
        last = field
        if field == "total_expenditure":
            after_total = True

    observations = []
    for field, row in found.items():
        for c, col in enumerate(columns):
            pct = row.pcts[c] if row.pcts else None
            amount = row.amounts[c]
            if pct is not None and amount is not None and amount < 0:
                pct = -abs(pct)  # surpluses print as a positive % in some years
            observations.append(Observation(field, col.fiscal_year, col.kind, amount, pct, labels[field]))

    gdp = None
    m = GDP_RE.search(ascii_text(" ".join(" ".join(c) for c in rows).replace("₹", "`")))
    if m:
        gdp = {"fiscal_year": m.group(1).replace(" ", ""), "value": float(m.group(2).replace(",", "")), "text": m.group(0)}

    return {"columns": columns, "observations": observations, "gdp": gdp, "unknown_rows": unknown}

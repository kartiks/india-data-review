"""Tax breakdown: the "Receipts" table of each year's Budget at a Glance.

What we read (revenue part of the table only):
- gross tax revenue and every printed component (corporation tax, taxes on
  income, customs, union excise, service tax, GST and its parts, wealth tax,
  fringe benefit tax, taxes of UTs, other taxes...),
- deductions: NCCD transferred to the calamity fund, states' share, and any
  other printed "Less" line,
- the Centre's net tax revenue,
- non-tax revenue and its parts, and total revenue receipts.

Column layouts:
- 2000-01 to 2009-10: three columns, BE and RE for last year and BE for the
  new year (no Actuals column in this table),
- from 2010-11: Actuals (two years back), BE, RE, BE,
- 2024-25: an extra Provisional Actuals column.

Every value row must have exactly one value per column (blanks only where the
document leaves a cell empty), otherwise parsing stops with ParseError.

Public functions:
- parse_receipts(rows, start, cell_based) -> {"columns", "items", "unknown_rows"}
- load_all() -> {"budgets": {...}, "comparisons": [...]}
- checks(all_parsed, summary_observations) -> [(title, checked, failures, notes)]
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from .parse import (
    FOOTNOTE_CHARS,
    NA_TOKENS,
    YEAR_RE,
    Column,
    ParseError,
    ascii_text,
    fy,
    parse_cell,
    read_row_cells,
    value_positions,
)
from .readers import read_any
from .sources import FORMAT_PRIORITY

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sources" / "manifest.json"
OBSERVATIONS = ROOT / "data" / "observations.csv"

TOLERANCE_CRORE = 5

# ----- what each printed label means ---------------------------------------
# Matched anywhere in the English label (older PDFs prefix it with leftovers of
# the Hindi text), in this order, so specific patterns come before general ones.
LABEL_PATTERNS: list[tuple[str, str]] = [
    ("revenue_receipts_total", r"total\W*revenue(?! deficit)\b"),  # "Receipts" sometimes wraps to the next line
    ("gross_tax_revenue", r"gross tax revenue"),
    ("net_tax_revenue", r"net tax(?: revenue)?\b"),
    ("states_share_adjustment", r"less\W.*share adjustment"),
    ("nccd_transferred", r"less\W.*(nccd|surcharge|calamity)"),
    ("states_share", r"less\W.*\bstates?\W*s?\W*share"),
    ("other_non_tax", r"other non\W*tax"),
    ("non_tax_revenue_total", r"non\W*tax revenue$"),
    ("interest_receipts", r"interest receipts"),
    ("dividends_profits", r"dividends? and profits"),
    ("external_grants", r"external grants"),
    ("ut_non_tax_receipts", r"receipts of (the )?union"),
    ("gst_compensation_cess", r"gst compensation"),
    ("cgst", r"\bcgst\b"),
    ("igst", r"\bigst\b"),
    ("utgst", r"\butgst\b"),
    ("gst", r"\b(gst|goods and services tax)\b"),
    ("corporation_tax", r"corporation tax"),
    ("interest_tax", r"interest\W*tax"),
    ("income_tax", r"(taxes on income|income\W*tax)"),
    ("expenditure_tax", r"expenditure tax"),
    ("wealth_tax", r"wealth tax"),
    ("fringe_benefit_tax", r"fringe benefit"),
    ("securities_transaction_tax", r"securities transaction"),
    ("banking_cash_transaction_tax", r"banking cash"),
    ("commodities_transaction_tax", r"commodit"),
    ("customs", r"\bcustoms\b"),
    ("union_excise", r"excise"),
    ("service_tax", r"service tax"),
    ("ut_taxes", r"taxes (of|on) (the )?union"),
    ("other_taxes", r"other taxes"),
]
GST_PARTS = {"cgst", "igst", "utgst", "gst_compensation_cess"}
DEDUCTIONS = {"nccd_transferred", "states_share", "states_share_adjustment"}
NON_TAX_PARTS = {"interest_receipts", "dividends_profits", "external_grants", "other_non_tax", "ut_non_tax_receipts"}
# Rows that end the revenue part of the table.
END_FIELD = "revenue_receipts_total"

# ----- reviewed exceptions ---------------------------------------------------
# (budget, fiscal year, kind, check name) -> reason. Each was checked against the
# source file, its footnotes and the other copy of the table.
KNOWN_EXCEPTIONS: dict[tuple[str, str, str, str], str] = {
    ("cross", "2010-11", "BE", "income_tax"): (
        "Budget 2011-12 restated the 2010-11 Budget Estimate: Budget 2010-11 printed income tax 1,20,566 and "
        "'Other taxes and duties' 8,103; Budget 2011-12 has no 'Other taxes' row and prints income tax 1,28,066 "
        "(+7,500) and wealth tax 603 (= 8,103 - 7,500). Gross tax is 7,46,651 in both, so this is a "
        "reclassification, not a change in the estimate."
    ),
}
# (budget, format) -> reason for a secondary copy that disagrees with the primary.
KNOWN_FORMAT_ISSUES: dict[tuple[str, str], str] = {
    ("2004-05", "htm"): (
        "The HTML page's 2004-05 Budget Estimates differ from the PDF in 13 values (e.g. corporation tax "
        "79,546 vs 88,436). The PDF's figures are the ones Budget 2005-06 reprints as BE 2004-05, so the "
        "HTML page is not used (same problem as its headline-table page)."
    ),
    ("2005-06", "htm"): (
        "The HTML page carries the numbers of Budget 2003-04 under 2005-06 headings (e.g. 2005-06 BE "
        "corporation tax 51,499, which is BE 2003-04). Not used (same problem as its headline-table page)."
    ),
    ("2023-24", "xls"): (
        "The Excel copy prints RE 2022-23 states' share as 9,48,406, which already includes the prior-year "
        "adjustment of 32,607 that it also lists separately, so its own net tax does not add up "
        "(30,43,067 - 8,000 - 9,48,406 - 32,607 = 20,54,054, printed 20,86,662). The PDF prints 9,15,798 "
        "+ 32,607 = 9,48,405, which reconciles to the same net tax and to the headline table. PDF used."
    ),
    ("2025-26", "xlsx"): (
        "The Excel copy is an earlier classification: no 'Other Taxes' row (its 5,000 crore is inside union "
        "excise: 3,24,000 vs 3,19,000 for BE 2024-25, which Budget 2024-25 prints as 3,19,000), wealth tax "
        "without commodity transaction tax (7.43 vs 422), RE 2024-25 states' share with the 12,764 "
        "prior-year adjustment folded in, and a 2023-24 actual gross tax that is 415 crore more than its "
        "parts. The PDF adds up exactly and is used."
    ),
}
KNOWN_FORMAT_ISSUES[("2017-18", "xlsx")] = (
    "The Excel copy shows wealth tax as 0 where the PDF prints '...' (nil; wealth tax was abolished from "
    "2015-16) for BE/RE 2016-17 and BE 2017-18. All other values agree. Its header also mislabels the "
    "Actuals column '2016-2016' (fixed via HEADER_FIXES)."
)

# Typos in a copy's column headings, fixed before reading: (budget, format) -> [(printed, corrected)]
HEADER_FIXES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("2017-18", "xlsx"): [("2016-2016", "2015-2016")],  # Actuals column is 2015-16, as in the PDF
}


def english(label: str) -> str:
    """Lower-cased English text of a label, without bullets like '1.', 'a.', '-', '1a'."""
    text = re.sub(r"\(cid:\d+\)", " ", label)  # unmapped glyphs of the Hindi font in old PDFs
    text = ascii_text(text).lower().replace("'", " ").replace("`", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # Drop leading bullets/numbering, repeatedly: "1. ", "a. ", "1a ", "(ii) ", "- ", ". "
    while True:
        new = re.sub(r"^([0-9]+[a-z]?|[a-z]|\(?[ivx]+\)|[-./*@#$|]+)[.)]?\s+", "", text)
        if new == text:
            break
        text = new
    return text.strip(" -.")


def match_item(label: str) -> str | None:
    text = english(label)
    if not text:
        return None
    for item, pat in LABEL_PATTERNS:
        if re.search(pat, text):
            return item
    return None


def printed_label(label: str, item: str | None) -> str:
    """The English part of the printed label, starting where the recognised wording starts
    (older PDFs put transliterated Hindi before it)."""
    text = english(label)
    pattern = dict(LABEL_PATTERNS).get(item or "")
    m = re.search(pattern, text) if pattern else None
    if m:
        start = m.start()
        # keep words like "less -" / "total" that belong to the English label
        prefix = re.search(r"(less\W*|total\W*|centre\W*s\W*|gross\W*)$", text[:start])
        text = text[prefix.start() if prefix else start:]
    # Drop leftover fragments of transliterated Hindi ("b e", "{i", "|") between English words.
    keep = {"of", "to", "on", "in", "by", "an", "a", "&", "-", "/"}
    words = [w for w in text.split() if w in keep or (len(w) >= 3 and re.fullmatch(r"[a-z][a-z'()/&.,-]*", w))]
    return " ".join(words).strip()


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", english(label)).strip("_")[:50] or "unlabelled"


# ----- columns ---------------------------------------------------------------


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
        offsets = value_positions(rows, first, ncols)
    else:
        xs = getattr(rows[first], "xs", None)
        if not xs or len(xs) != ncols:
            raise ParseError(f"{fy(start)}: 'Gross Tax Revenue' line has {len(xs or [])} values, expected {ncols}")
        anchors = xs

    # Pass 1: turn rows into (label, values-or-None) lines.
    lines: list[tuple[str, list[float | None] | None]] = []
    pending_text = ""
    for cells in rows[first:]:
        if lines and lines[-1][1] is not None and END_FIELD in (
            match_item(lines[-1][0]), match_item(pending_text + " " + lines[-1][0])
        ):
            break  # the revenue part ends with Total Revenue Receipts; charts and capital receipts follow
        if lines:
            pending_text = lines[-1][0] if lines[-1][1] is None else ""
        if cell_based:
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

    # Pass 2: assign meaning. A wrapped label is either before the numbers
    # (pending text) or right after them (continuation), so try both.
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
    return {"columns": columns, "items": items, "unknown_rows": unknown}


# ----- loading every budget -------------------------------------------------


# ----- Receipt Budget, Annex 7: tax actuals for 2000-01 to 2007-08 -------------
# The Budget at a Glance Receipts table has no Actuals column before Budget
# 2010-11. Each Receipt Budget's Annex 7 ("Analysis of tax and non-tax revenue
# receipts") prints ten columns: audited Actuals/Accounts for eight past years,
# then RE and BE. Actuals for year Y are taken from Receipt Budget Y+2 (its newest
# Actuals column), the same vintage as the headline table's Actuals. Its RE and
# BE columns are only used to cross-check the Budget at a Glance.

ANNEX7_PATTERNS: list[tuple[str, str]] = [
    ("gross_tax_revenue", r"gross tax revenue"),
    ("income_tax", r"(taxes on income other|than corporation\s*tax)"),
    ("corporation_tax", r"corporation tax"),
    ("interest_tax", r"interest\W*tax"),
    ("other_taxes_on_income_expenditure", r"other taxes on income"),
    ("customs", r"\bcustoms\b"),
    ("union_excise", r"excise"),
    ("service_tax", r"service tax"),
    ("estate_duty", r"estate duty"),
    ("wealth_tax", r"wealth tax"),
    ("gift_tax", r"gift tax"),
    ("fringe_benefit_tax", r"fringe benefit"),
    ("securities_transaction_tax", r"securities transaction"),
    ("banking_cash_transaction_tax", r"banking cash"),
    ("commodities_transaction_tax", r"commodit"),
    ("other_taxes", r"other taxes"),
    ("ut_taxes", r"taxes of (the )?union"),
    ("states_share", r"less\W*states?\W*s?\W*share"),
    ("nccd_transferred", r"(nccf|nccd|calamity)"),
    ("ut_local_bodies_assignment", r"taxes to local bodies"),
    ("net_tax_revenue", r"net\W*centre\W*s?\W*tax revenue|net tax revenue"),
    ("non_tax_revenue_total", r"total\W*non\W*tax"),
    ("revenue_receipts_total", r"total\W*revenue receipts"),
]
ANNEX7_DEDUCTIONS = {"states_share", "nccd_transferred", "ut_local_bodies_assignment"}


def _annex7_item(label: str) -> str | None:
    text = english(label)
    for item, pat in ANNEX7_PATTERNS:
        if re.search(pat, text):
            return item
    return None


def annex7_header_text(path: Path) -> str:
    """Header words of Annex 7, read without the reader's small-font filter
    (the 2009-10 edition prints its column headings below 7pt)."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    lines = [ln for ln in text.splitlines() if re.search(r"Accounts|Actuals|Revised|Budget|\d{4}-\d{2,4}", ln)]
    header = " ".join(lines[:6])
    return re.sub(r"(\d{4}-\d{4})(?=\d)", r"\1 ", header)  # "1999-20002000-2001" (2008-09) -> two years


def annex7_columns(header_text: str, start: int) -> list[Column]:
    years = [int(m.group(1)) for m in YEAR_RE.finditer(header_text)]
    want = list(range(start - 9, start + 1))
    if not any(years[i : i + 10] == want for i in range(len(years) - 9)):
        raise ParseError(f"Receipt Budget {fy(start)} Annex 7: column years {years}, expected {want}")
    low = header_text.lower()
    if "revised" not in low or not re.search(r"actuals|accounts", low):
        raise ParseError(f"Receipt Budget {fy(start)} Annex 7: header lacks Actuals/Revised labels")
    return [Column(fy(y), "Actual") for y in want[:8]] + [Column(fy(start - 1), "RE"), Column(fy(start), "BE")]


KEEP = (7, 8, 9)  # newest Actuals column (year Y-2), RE (Y-1), BE (Y)


def _annex7_values(cells, anchors: list[float]) -> list[float | None] | None:
    """Place each positioned number under the nearest of the ten columns. Numbers
    that cannot be placed are ignored unless they would fall in a column we keep."""
    raw = [".." if re.fullmatch(r"\.{2,}", t) else t for t in cells[1:]]
    xs = list(getattr(cells, "xs", []))
    toks, sign = [], False
    for tok, x in zip(raw, xs):
        if tok in ("(-)", "-") and len(raw) > 1:
            sign = True
            continue
        if sign and not tok.startswith("-") and tok not in NA_TOKENS:
            tok = "-" + tok
        sign = False
        toks.append((tok, x))
    if not toks:
        return None
    placed: dict[int, float | None] = {}
    seen_cols: set[int] = set()
    for tok, x in toks:
        ok, amount, pct = parse_cell(tok)
        col = min(range(10), key=lambda c: abs(anchors[c] - x))
        if not ok or pct is not None or abs(anchors[col] - x) > 25:
            if col in KEEP and abs(anchors[col] - x) <= 25:
                raise ParseError(f"unreadable value {tok!r} in a needed column of {cells[0]!r}")
            continue
        if col in seen_cols:
            if col in KEEP:
                raise ParseError(f"two numbers in one needed column of {cells[0]!r}")
            continue
        seen_cols.add(col)
        placed[col] = amount
    return [placed.get(c) for c in range(10)]


def parse_annex7(rows: list[list[str]], start: int, header_text: str) -> dict:
    """Return {"columns" (Actual Y-2, RE Y-1, BE Y), "items", "unknown_rows"}."""
    columns = annex7_columns(header_text, start)
    first = next((i for i, r in enumerate(rows) if re.search(r"gross tax revenue", english(r[0]))), None)
    if first is None:
        raise ParseError(f"Receipt Budget {fy(start)} Annex 7: no 'Gross Tax Revenue' row")
    anchors = list(getattr(rows[first], "xs", []))
    if len(anchors) != 10:
        raise ParseError(f"Receipt Budget {fy(start)} Annex 7: 'Gross Tax Revenue' has {len(anchors)} values, expected 10")

    items, unknown, seen = [], [], set()
    section, pending = "gross", ""
    for cells in rows[first:]:
        values = _annex7_values(cells, anchors)
        label = cells[0] if cells else ""
        if values is None or all(v is None for v in values) and not any(
            t in NA_TOKENS for t in cells[1:]
        ):
            pending = (pending + " " + label).strip()
            continue
        item = _annex7_item(label)
        printed = label
        if item is None or (item == "corporation_tax" and re.search(r"taxes on income other", english(pending))):
            alt = _annex7_item(pending + " " + label)
            if alt:
                item, printed = alt, pending + " " + label
        pending = ""
        if item == "states_share":
            section = "deduction"
        elif item == "net_tax_revenue":
            section = "net"
        if section == "net" and item not in ("net_tax_revenue", "non_tax_revenue_total", "revenue_receipts_total"):
            continue  # non-tax details: not used
        if section == "deduction" and item not in ANNEX7_DEDUCTIONS:
            text = english(label)
            detail = ("income_tax" if re.search(r"income\W*tax", text) else "vdis" if "vdis" in text
                      else "union_excise" if "excise" in text else slug(label))
            item_id, item_section = f"states_share_of:{detail}", "deduction_detail"
        elif item is None:
            item_id, item_section = f"other:{slug(label)}", "gross"
            unknown.append(f"(kept as gross component) {ascii_text(printed)!r}")
        elif item == "gross_tax_revenue":
            item_id, item_section = item, "gross_total"
        elif item in ANNEX7_DEDUCTIONS:
            item_id, item_section = item, "deduction"
        elif item == "net_tax_revenue":
            item_id, item_section = item, "net"
        elif item in ("non_tax_revenue_total", "revenue_receipts_total"):
            item_id, item_section = item, "non_tax" if item == "non_tax_revenue_total" else "total"
        else:
            item_id, item_section = item, "gross"
        if item_id in seen:
            raise ParseError(f"Receipt Budget {fy(start)} Annex 7: {item_id!r} appears twice")
        seen.add(item_id)
        items.append({"item_id": item_id, "label_as_printed": english(printed), "section": item_section,
                      "values": [values[c] for c in KEEP]})
        if item_id == "revenue_receipts_total":
            break
    for need in ("gross_tax_revenue", "states_share", "net_tax_revenue", "revenue_receipts_total"):
        if need not in seen:
            raise ParseError(f"Receipt Budget {fy(start)} Annex 7: {need} not found")
    return {"columns": [columns[c] for c in KEEP], "items": items, "unknown_rows": unknown}


def load_receipt_budgets() -> dict:
    """{budget: {"url", "sha256", "parsed"} or {"error"}} for Receipt Budgets 2002-03..2009-10."""
    manifest = json.loads(MANIFEST.read_text())
    out = {}
    for budget, entry in manifest.items():
        f = entry.get("receipt_budget", {}).get("files", {}).get("pdf")
        if not f:
            continue
        path = ROOT / f["file"]
        try:
            parsed = parse_annex7(read_any(path), int(budget[:4]), annex7_header_text(path))
            out[budget] = {"url": f["url"], "sha256": f["sha256"], "parsed": parsed}
        except ParseError as exc:
            out[budget] = {"url": f["url"], "error": str(exc)}
    return out


def load_all() -> dict:
    """Parse every copy of every year's Receipts table.

    Returns {"budgets": {budget: {"primary": ext, "url", "sha256", "parsed": {...}}},
             "comparisons": [{"budget", "primary", "others": {ext: {...}}, "unparseable": {...}}]}
    """
    manifest = json.loads(MANIFEST.read_text())
    budgets: dict[str, dict] = {}
    comparisons: list[dict] = []
    for budget, entry in manifest.items():
        files = entry.get("receipts", {}).get("files", {})
        start = int(budget[:4])
        parsed: dict[str, dict] = {}
        errors: dict[str, str] = {}
        for ext in FORMAT_PRIORITY:
            if ext not in files:
                continue
            try:
                rows = read_any(ROOT / files[ext]["file"])
                for printed, corrected in HEADER_FIXES.get((budget, ext), []):
                    rows = [[c.replace(printed, corrected) for c in r] for r in rows]
                parsed[ext] = parse_receipts(rows, start, ext != "pdf")
            except ParseError as exc:
                errors[ext] = str(exc)
        if not parsed:
            comparisons.append({"budget": budget, "primary": None, "others": {}, "unparseable": errors})
            continue
        primary = next(e for e in FORMAT_PRIORITY if e in parsed)
        budgets[budget] = {
            "primary": primary,
            "url": files[primary]["url"],
            "sha256": files[primary]["sha256"],
            "parsed": parsed[primary],
        }
        comparisons.append(_compare(budget, primary, parsed, errors))
    return {"budgets": budgets, "comparisons": comparisons, "receipt_budgets": load_receipt_budgets()}


def _flatten(parsed: dict) -> dict[tuple[str, str, str], float | None]:
    out = {}
    for it in parsed["items"]:
        for col, v in zip(parsed["columns"], it["values"]):
            out[(it["item_id"], col.fiscal_year, col.kind)] = v
    return out


def _compare(budget: str, primary: str, parsed: dict[str, dict], errors: dict[str, str]) -> dict:
    base = _flatten(parsed[primary])
    result = {"budget": budget, "primary": primary, "others": {}, "unparseable": errors}
    for ext, p in parsed.items():
        if ext == primary:
            continue
        other = _flatten(p)
        diffs = []
        for key in sorted(set(base) | set(other)):
            a, b = base.get(key), other.get(key)
            if (a is None) != (b is None) or (a is not None and abs(a - b) > 1):
                diffs.append({"item": list(key), primary: a, ext: b})
        result["others"][ext] = {"compared": len(set(base) | set(other)), "differences": diffs}
    return result


def observations(all_parsed: dict) -> list[dict]:
    """Long-format rows (like observations.csv) for every value in every primary table,
    plus the 2000-01..2007-08 actuals from the Receipt Budget (document="receipt_budget")."""
    rows = []
    for budget, b in sorted(all_parsed["budgets"].items()):
        p = b["parsed"]
        for it in p["items"]:
            for col, v in zip(p["columns"], it["values"]):
                rows.append(
                    {
                        "fiscal_year": col.fiscal_year,
                        "kind": col.kind,
                        "item_id": it["item_id"],
                        "section": it["section"],
                        "value_crore": v,
                        "source_budget": budget,
                        "document": "receipts",
                        "label_as_printed": it["label_as_printed"],
                        "source_url": b["url"],
                        "source_sha256": b["sha256"],
                    }
                )
    for budget, b in sorted(all_parsed.get("receipt_budgets", {}).items()):
        if "parsed" not in b:
            continue
        p = b["parsed"]
        for it in p["items"]:
            col, v = p["columns"][0], it["values"][0]  # the Actuals column only
            rows.append(
                {
                    "fiscal_year": col.fiscal_year,
                    "kind": col.kind,
                    "item_id": it["item_id"],
                    "section": it["section"],
                    "value_crore": v,
                    "source_budget": budget,
                    "document": "receipt_budget",
                    "label_as_printed": it["label_as_printed"],
                    "source_url": b["url"],
                    "source_sha256": b["sha256"],
                }
            )
    return rows


# ----- checks ----------------------------------------------------------------


def _allowed(key, msg, failures, notes):
    if key in KNOWN_EXCEPTIONS:
        notes.append(f"Allowed: {msg}. Reason: {KNOWN_EXCEPTIONS[key]}")
    else:
        failures.append(msg)


def _identity_checks(all_parsed: dict) -> tuple[int, list[str], list[str]]:
    failures, notes, checked = [], [], 0
    for budget, b in sorted(all_parsed["budgets"].items()):
        p = b["parsed"]
        for c, col in enumerate(p["columns"]):
            vals = {it["item_id"]: it["values"][c] for it in p["items"]}
            sections = {it["item_id"]: it["section"] for it in p["items"]}

            def check(name: str, printed: float | None, parts: list[float | None]) -> None:
                nonlocal checked
                if printed is None or all(x is None for x in parts):
                    return
                calc = sum(x or 0 for x in parts)
                checked += 1
                if abs(printed - calc) > TOLERANCE_CRORE:
                    msg = (f"Budget {budget}, {col.kind} {col.fiscal_year}: {name} - printed {printed:,.0f}, "
                           f"parts give {calc:,.0f} (off by {printed - calc:,.0f})")
                    _allowed((budget, col.fiscal_year, col.kind, name), msg, failures, notes)

            check("gross tax = sum of printed taxes", vals.get("gross_tax_revenue"),
                  [v for k, v in vals.items() if sections[k] == "gross"])
            check("net tax = gross - deductions", vals.get("net_tax_revenue"),
                  [vals.get("gross_tax_revenue")] + [-(v or 0) for k, v in vals.items() if sections[k] == "deduction"])
            if any(sections[k] == "gst_part" for k in vals):
                check("GST = CGST + IGST + cess", vals.get("gst"),
                      [v for k, v in vals.items() if sections[k] == "gst_part"])
            check("non-tax total = its parts", vals.get("non_tax_revenue_total"),
                  [vals.get(k) for k in NON_TAX_PARTS if k in vals])
            check("revenue receipts = net tax + non-tax", vals.get("revenue_receipts_total"),
                  [vals.get("net_tax_revenue"), vals.get("non_tax_revenue_total")])
            detail = [v for k, v in vals.items() if sections[k] == "deduction_detail"]
            if detail:
                check("states' share = its printed split", vals.get("states_share"), detail)
    return checked, failures, notes


SUMMARY_LINKS = {
    "net_tax_revenue": "tax_revenue_net",
    "non_tax_revenue_total": "non_tax_revenue",
    "revenue_receipts_total": "revenue_receipts",
}


def _summary_checks(all_parsed: dict, summary_observations: list[dict]) -> tuple[int, list[str], list[str]]:
    summ = {}
    for r in summary_observations:
        v = r["value_crore"]
        summ[(r["source_budget"], r["fiscal_year"], r["kind"], r["field"])] = float(v) if v not in ("", None) else None
    failures, notes, checked = [], [], 0
    for budget, b in sorted(all_parsed["budgets"].items()):
        p = b["parsed"]
        for it in p["items"]:
            field = SUMMARY_LINKS.get(it["item_id"])
            if not field:
                continue
            for col, v in zip(p["columns"], it["values"]):
                s = summ.get((budget, col.fiscal_year, col.kind, field))
                if s is None or v is None:
                    continue
                checked += 1
                if abs(s - v) > TOLERANCE_CRORE:
                    msg = (f"Budget {budget}, {col.kind} {col.fiscal_year}: {it['item_id']} {v:,.0f} in Receipts "
                           f"vs {field} {s:,.0f} in the headline table")
                    _allowed((budget, col.fiscal_year, col.kind, f"summary:{it['item_id']}"), msg, failures, notes)
    return checked, failures, notes


def _cross_document_checks(all_parsed: dict) -> tuple[int, list[str], list[str]]:
    seen = defaultdict(dict)
    for r in observations(all_parsed):
        if r["value_crore"] is not None:
            seen[(r["fiscal_year"], r["kind"], r["item_id"])][r["source_budget"]] = r["value_crore"]
    failures, notes, checked = [], [], 0
    for (year, kind, item), by_doc in sorted(seen.items()):
        if len(by_doc) < 2:
            continue
        checked += 1
        (d1, v1), (d2, v2) = sorted(by_doc.items())[:2]
        if abs(v1 - v2) <= TOLERANCE_CRORE:
            continue
        rel = abs(v2 - v1) / max(abs(v1), 1)
        msg = f"{kind} {year} {item}: {v1:,.0f} in budget {d1} vs {v2:,.0f} in budget {d2} ({v2 - v1:+,.0f}, {rel:.1%})"
        key = ("cross", year, kind, item)
        if key in KNOWN_EXCEPTIONS:
            notes.append(f"{msg}. Explained: {KNOWN_EXCEPTIONS[key]}")
        elif rel > 0.02 and abs(v2 - v1) > 500:
            failures.append(msg)
        else:
            notes.append(f"Restated: {msg}")
    return checked, failures, notes


def _format_checks(all_parsed: dict) -> tuple[int, list[str], list[str]]:
    failures, notes, checked = [], [], 0
    for c in all_parsed["comparisons"]:
        budget, primary = c["budget"], c["primary"]
        if primary is None:
            failures.append(f"Budget {budget}: no copy of the Receipts table could be read ({c['unparseable']})")
            continue
        for ext, o in c["others"].items():
            checked += 1
            n = len(o["differences"])
            if n == 0:
                notes.append(f"Budget {budget}: {primary.upper()} and {ext.upper()} agree on all {o['compared']} values.")
            elif (budget, ext) in KNOWN_FORMAT_ISSUES:
                notes.append(f"Budget {budget}: {ext.upper()} differs in {n} values (known): "
                             f"{KNOWN_FORMAT_ISSUES[(budget, ext)]}")
            else:
                sample = "; ".join(f"{d['item']}: {d[primary]} vs {d[ext]}" for d in o["differences"][:3])
                failures.append(f"Budget {budget}: {ext.upper()} differs from {primary.upper()} in {n} values ({sample})")
        for ext, err in c["unparseable"].items():
            notes.append(f"Budget {budget}: {ext.upper()} copy could not be read ({err}).")
    return checked, failures, notes


# ----- checks on the Receipt Budget actuals ----------------------------------

ANNEX7_TO_BAG = {  # same meaning in both tables
    "gross_tax_revenue", "corporation_tax", "income_tax", "customs", "union_excise", "service_tax",
    "wealth_tax", "ut_taxes", "states_share", "nccd_transferred", "net_tax_revenue",
    "non_tax_revenue_total", "revenue_receipts_total", "interest_tax",
}


def _receipt_budget_checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple]:
    rbs = all_parsed.get("receipt_budgets", {})
    summ = {}
    for r in summary_observations:
        v = r["value_crore"]
        summ[(r["source_budget"], r["fiscal_year"], r["kind"], r["field"])] = float(v) if v not in ("", None) else None
    bag = {}
    for budget, b in all_parsed["budgets"].items():
        p = b["parsed"]
        for it in p["items"]:
            for col, v in zip(p["columns"], it["values"]):
                bag[(budget, col.fiscal_year, col.kind, it["item_id"])] = v

    ident_f, ident_n, ident_c = [], [], 0
    link_f, link_n, link_c = [], [], 0
    bag_f, bag_n, bag_c = [], [], 0
    for budget, b in sorted(rbs.items()):
        if "parsed" not in b:
            ident_f.append(f"Receipt Budget {budget}: Annex 7 could not be read ({b['error']})")
            continue
        p = b["parsed"]
        for c, col in enumerate(p["columns"]):
            vals = {it["item_id"]: it["values"][c] for it in p["items"]}
            sec = {it["item_id"]: it["section"] for it in p["items"]}

            def check(name, printed, parts):
                nonlocal ident_c
                if printed is None or all(x is None for x in parts):
                    return
                calc = sum(x or 0 for x in parts)
                ident_c += 1
                if abs(printed - calc) > TOLERANCE_CRORE:
                    msg = (f"Receipt Budget {budget}, {col.kind} {col.fiscal_year}: {name} - printed {printed:,.0f}, "
                           f"parts give {calc:,.0f} (off by {printed - calc:,.0f})")
                    _allowed(("rb:" + budget, col.fiscal_year, col.kind, name), msg, ident_f, ident_n)

            check("gross tax = sum of printed taxes", vals.get("gross_tax_revenue"),
                  [v for k, v in vals.items() if sec[k] == "gross"])
            check("net tax = gross - deductions", vals.get("net_tax_revenue"),
                  [vals.get("gross_tax_revenue")] + [-(v or 0) for k, v in vals.items() if sec[k] == "deduction"])
            check("revenue receipts = net tax + non-tax", vals.get("revenue_receipts_total"),
                  [vals.get("net_tax_revenue"), vals.get("non_tax_revenue_total")])
            detail = [v for k, v in vals.items() if sec[k] == "deduction_detail"]
            if any(d is not None for d in detail):
                check("states' share = its printed split", vals.get("states_share"), detail)

            # (b) the Actuals column against the headline table of the same budget
            if col.kind == "Actual":
                for item, field in SUMMARY_LINKS.items():
                    v, sv = vals.get(item), summ.get((budget, col.fiscal_year, "Actual", field))
                    if v is None or sv is None:
                        if v is not None:
                            link_f.append(f"Receipt Budget {budget}: no headline {field} Actual {col.fiscal_year} to compare")
                        continue
                    link_c += 1
                    if abs(v - sv) > TOLERANCE_CRORE:
                        msg = (f"Receipt Budget {budget}, Actual {col.fiscal_year}: {item} {v:,.0f} vs headline "
                               f"{field} {sv:,.0f} (Budget at a Glance {budget})")
                        _allowed(("rb:" + budget, col.fiscal_year, "Actual", f"summary:{item}"), msg, link_f, link_n)
            # (c) RE and BE columns against the Budget at a Glance Receipts table of the same budget
            else:
                for item in ANNEX7_TO_BAG:
                    v = vals.get(item)
                    key = (budget, col.fiscal_year, col.kind, item)
                    if key not in bag:
                        continue
                    bv = bag[key]
                    if v is None and bv is None:
                        continue
                    bag_c += 1
                    if (v is None) != (bv is None) or abs(v - bv) > TOLERANCE_CRORE:
                        msg = (f"Budget {budget}, {col.kind} {col.fiscal_year}: {item} {v} in Receipt Budget Annex 7 "
                               f"vs {bv} in Budget at a Glance Receipts")
                        _allowed(("rb:" + budget, col.fiscal_year, col.kind, f"bag:{item}"), msg, bag_f, bag_n)

    # completeness: actuals for every year the Budget at a Glance Receipts table lacks
    comp_f, comp_c = [], 0
    have = {(it_year, item) for budget, b in rbs.items() if "parsed" in b
            for item, it_year in ((it["item_id"], b["parsed"]["columns"][0].fiscal_year) for it in b["parsed"]["items"]
                                  if it["values"][0] is not None)}
    for start in range(2000, 2008):
        for item in ("gross_tax_revenue", "corporation_tax", "income_tax", "customs", "union_excise",
                     "service_tax", "states_share", "net_tax_revenue"):
            comp_c += 1
            if (fy(start), item) not in have:
                comp_f.append(f"Actual {fy(start)} {item} missing")
    return [
        ("Taxes (Receipt Budget actuals 2000-01..2007-08): totals equal their printed parts", ident_c, ident_f, ident_n),
        ("Taxes (Receipt Budget actuals): net tax, non-tax, revenue receipts match the headline table's Actuals",
         link_c, link_f, link_n),
        ("Taxes (Receipt Budget): its RE/BE columns match the Budget at a Glance Receipts table", bag_c, bag_f, bag_n),
        ("Taxes (Receipt Budget): actuals present for 2000-01..2007-08", comp_c, comp_f, []),
    ]


def checks(all_parsed: dict, summary_observations: list[dict]) -> list[tuple[str, int, list[str], list[str]]]:
    out = []
    out.append(("Taxes: totals equal their printed parts", *_identity_checks(all_parsed)))
    out.append(("Taxes: net tax, non-tax and revenue receipts match the headline table",
                *_summary_checks(all_parsed, summary_observations)))
    out.append(("Taxes: same figure agrees across budgets", *_cross_document_checks(all_parsed)))
    out.append(("Taxes: other copies (Excel/HTML) agree with the primary file", *_format_checks(all_parsed)))
    out.extend(_receipt_budget_checks(all_parsed, summary_observations))
    return out


def load_summary_observations(path: Path = OBSERVATIONS) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    data = load_all()
    for b, info in sorted(data["budgets"].items()):
        p = info["parsed"]
        print(b, info["primary"], " ".join(f"{c.kind}:{c.fiscal_year}" for c in p["columns"]), len(p["items"]), "items")
        for u in p["unknown_rows"]:
            print("   ", u)
    for title, checked, failures, notes in checks(data, load_summary_observations()):
        print(f"{'FAIL' if failures else 'ok  '} {title}: {checked} checks, {len(failures)} failures")
        for f in failures:
            print("   -", f)

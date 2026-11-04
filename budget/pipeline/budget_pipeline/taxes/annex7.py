"""Receipt Budget Annex 7: tax actuals for 2000-01 to 2007-08."""

import json
import re
from pathlib import Path

from pipeline_common.text import fy, fy_start

from ..parse import NA_TOKENS, YEAR_RE, Column, ParseError, ascii_text, parse_cell
from ..readers import read_any
from .common import MANIFEST, ROOT, english, slug

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


def _annex7_id(item: str | None, section: str, label: str) -> tuple[str, str]:
    """(item_id, section) of a recognised (or unrecognised: None) Annex 7 line in the given part of the table."""
    if section == "deduction" and item not in ANNEX7_DEDUCTIONS:
        text = english(label)
        detail = ("income_tax" if re.search(r"income\W*tax", text) else "vdis" if "vdis" in text
                  else "union_excise" if "excise" in text else slug(label))
        return f"states_share_of:{detail}", "deduction_detail"
    if item is None:
        return f"other:{slug(label)}", "gross"
    if item == "gross_tax_revenue":
        return item, "gross_total"
    if item in ANNEX7_DEDUCTIONS:
        return item, "deduction"
    if item == "net_tax_revenue":
        return item, "net"
    if item in ("non_tax_revenue_total", "revenue_receipts_total"):
        return item, "non_tax" if item == "non_tax_revenue_total" else "total"
    return item, "gross"


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
        item_id, item_section = _annex7_id(item, section, label)
        if item is None and section != "deduction":
            unknown.append(f"(kept as gross component) {ascii_text(printed)!r}")
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
            parsed = parse_annex7(read_any(path), fy_start(budget), annex7_header_text(path))
            out[budget] = {"url": f["url"], "sha256": f["sha256"], "parsed": parsed}
        except ParseError as exc:
            out[budget] = {"url": f["url"], "error": str(exc)}
    return out

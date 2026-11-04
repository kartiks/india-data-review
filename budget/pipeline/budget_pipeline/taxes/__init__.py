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

Modules: common (paths, label meanings), exceptions (reviewed exceptions), receipts (the Receipts table
parser), annex7 (Receipt Budget actuals), load (every budget and copy), validate (the checks).

Public functions:
- parse_receipts(rows, start, cell_based) -> {"columns", "items", "unknown_rows"}
- load_all() -> {"budgets": {...}, "comparisons": [...]}
- checks(all_parsed, summary_observations) -> [(title, checked, failures, notes)]
"""

from .annex7 import annex7_columns, annex7_header_text, load_receipt_budgets, parse_annex7
from .validate import checks
from .common import DATA, MANIFEST, ROOT, TOLERANCE_CRORE, english, match_item, printed_label, slug
from .exceptions import HEADER_FIXES, KNOWN_EXCEPTIONS, KNOWN_FORMAT_ISSUES
from .load import load_all, load_summary_observations, observations
from .receipts import parse_receipts, read_pdf_line, receipts_columns

__all__ = [
    "DATA", "HEADER_FIXES", "KNOWN_EXCEPTIONS", "KNOWN_FORMAT_ISSUES", "MANIFEST", "ROOT", "TOLERANCE_CRORE",
    "annex7_columns", "annex7_header_text", "checks", "english", "load_all", "load_receipt_budgets",
    "load_summary_observations", "match_item", "observations", "parse_annex7", "parse_receipts", "printed_label",
    "read_pdf_line", "receipts_columns", "slug",
]

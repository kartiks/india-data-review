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

Modules: common (constants, the text line), read (PDF and spreadsheet readers), text_layer (cells read from the
page image), items (lines -> items), ids (stable ids), load (every budget and copy), validate (the checks).
Public functions: parse_schemes(), parse_file(), load_all(), checks().
"""

from .validate import EXCEPTIONS, KNOWN_EXCEPTIONS, KNOWN_FORMAT_ISSUES, checks
from .common import MANIFEST, NAME_MAP, PARTS, ROOT, SCHEME_TYPES, TOLERANCE, Line
from .ids import build_name_map, item_id, load_name_map, normalise_name, slug
from .items import lines_to_items, parse_schemes, parse_value
from .load import compare, load_all, parse_file
from .read import read_pdf_lines, read_sheet_lines
from .text_layer import GARBLED_LABELS, IMAGE_READINGS, MISSING_LABELS, apply_text_layer_fixes

__all__ = [
    "EXCEPTIONS", "GARBLED_LABELS", "IMAGE_READINGS", "KNOWN_EXCEPTIONS", "KNOWN_FORMAT_ISSUES", "MANIFEST",
    "MISSING_LABELS",
    "NAME_MAP", "PARTS", "ROOT", "SCHEME_TYPES", "TOLERANCE", "Line", "apply_text_layer_fixes", "build_name_map",
    "checks", "compare", "item_id", "lines_to_items", "load_all", "load_name_map", "normalise_name", "parse_file",
    "parse_schemes", "parse_value", "read_pdf_lines", "read_sheet_lines", "slug",
]

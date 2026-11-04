"""Total spending of each ministry / department, 2000-01 to 2026-27.

Sources (manifest key "ministries"):
- to 2016-17: Expenditure Budget Vol. 1, Statement 2 "Total Expenditure of
  Ministries/Departments". Each department has a line split Plan / Non-Plan /
  Total, followed by a "Revenue" line and a "Capital" line.
  2000-01 to 2010-11 print three periods (Actuals, Revised, Budget);
  2011-12 to 2016-17 print four (Actuals, Budget, Revised, Budget).
- from 2017-18: Expenditure Profile, Statement 3A (2017-18, 2018-19) / 3
  "Expenditure of Ministries and Departments". Each Demand for Grants has a
  line split Revenue / Capital / Total, followed by numbered sub-lines
  (Central Sector Schemes, Centrally Sponsored Schemes, Establishment, ...).

PDFs are read with a dedicated reader: these tables use 7-8.5pt type (too
small for the shared reader's footnote filter), have 9 or 12 value columns,
and sometimes print two numbers with no gap ("5200.351477.00"). Numbers are
placed into columns by the right edge of their text; "..." marks an empty
cell and keeps its column. Any line whose numbers do not fill the columns
exactly stops parsing with an error.

Modules: common (paths, patterns, the text line), read (PDF and spreadsheet
readers), table (the parser), ids (stable ids), load (every budget and copy),
checks.
"""

from .validate import EXCEPTIONS, KNOWN_EXCEPTIONS, KNOWN_FORMAT_ISSUES, checks, internal_checks
from .common import MANIFEST, NAME_MAP, ROOT, Line
from .ids import assign_ids, load_name_map, lookup
from .load import load_all, observations, parse_file
from .read import _split_number, read_pdf_lines
from .table import detect_header, parse_ministries

__all__ = [
    "EXCEPTIONS", "KNOWN_EXCEPTIONS", "KNOWN_FORMAT_ISSUES", "MANIFEST", "NAME_MAP", "ROOT", "Line", "_split_number",
    "assign_ids", "checks", "detect_header", "internal_checks", "load_all", "load_name_map", "lookup",
    "observations", "parse_file", "parse_ministries", "read_pdf_lines",
]

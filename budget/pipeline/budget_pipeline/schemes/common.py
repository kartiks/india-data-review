"""Constants and the text line shared by the readers, the parser and the checks."""

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "sources" / "manifest.json"
NAME_MAP = Path(__file__).resolve().parents[1] / "data_maps" / "scheme_names.csv"

SCHEME_TYPES = {"css": "Centrally Sponsored Schemes", "central_sector": "Central Sector Schemes"}
PARTS = ("revenue", "capital", "total")
LEVEL_TOL = 0.051  # ₹ crore: values are printed to two decimals; a little over 0.05 for sums of rounded cells

NA_TEXT = {"...", "..", "…", "-", "--", "–", "—"}
HEADER_PATTERNS = [
    r"^expenditure profile", r"^statement\s*4", r"^centrally sponsored schemes", r"^central sector schemes",
    r"^\(in\b", r"^actuals", r"^ministry\s*/\s*department", r"^sl\.?\s*name", r"^no\.?\s+scheme",
    r"^revenue capital total", r"^\(\s*rs\.?|^\(\s*`",
]


@dataclass
class Line:
    label: str
    cells: list[str | None]  # 12 raw value strings, None = nothing printed in that column
    page: int
    bottom: float
    text: str = ""  # the whole line as printed (for recognising page headers)

    @property
    def has_values(self) -> bool:
        return any(c is not None for c in self.cells)


def _is_header(label: str) -> bool:
    low = label.lower().strip()
    return any(re.search(p, low) for p in HEADER_PATTERNS)

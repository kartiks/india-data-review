"""Paths, patterns and the text line shared by the readers and the parser."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "sources" / "manifest.json"
NAME_MAP = Path(__file__).resolve().parents[1] / "data_maps" / "ministry_names.csv"

YEAR_RE = re.compile(r"(?<!\d)(\d{4})\s*-\s*(\d{4}|\d{2})(?!\d)")
TWO_DEC = re.compile(r"-?\d+\.\d{2}")
NA = {"...", "..", "…", "-", "--", "—", "–"}

# Sub-lines printed under each Demand from 2017-18.
CATEGORIES = [
    ("central_sector_schemes", r"^central sector schemes"),
    ("centrally_sponsored_schemes", r"^centrally sponsored schemes"),
    ("establishment", r"^establishment( expenditure)?$|^establishment expenditure"),
    ("other_central_sector", r"^other central (sector )?expenditure"),
    ("finance_commission_grants", r"^finance commission (grants|transfers)"),
    ("other_transfers", r"^other (grants\s*/?\s*loans\s*/?\s*)?transfers"),
]

# Header and page furniture lines (ignored wherever they appear).
FURNITURE = re.compile(
    r"^(expenditure budget|expenditure profile|statement\b|total expenditure of ministries|"
    r"expenditure of ministries|\(in |ministry\s*/\s*department|plan non-plan|revenue capital total|"
    r"actuals|budget estimates|page\b|\d+$)"
    r"|indiabudget\.(nic|gov)\.in|expenditure budget vol|expenditure profile 20"
    r"|^\d{4}-\d{2,4}\s+(actuals|budget|revised)"
    r"|^[\d\s\-]+$",  # page numbers, rows of column years
    re.I,
)


def _strip_furniture(label: str) -> str:
    """Remove page furniture glued onto a label line (URLs, running headers)."""
    label = re.sub(r"(website\s*:\s*)?(https?:?/*\S+|\S*indiabudget\.(nic|gov)\.in\S*)|^website\s*:", " ", label, flags=re.I)
    label = re.sub(
        r"\d{4}-\d{4}\s+expenditure budget vol\.?\s*i\b(.*?\bbudget\b(?=\s))?|"
        r"(\d+\s+)?expenditure budget vol\.?\s*i,?\s*\d{4}-\d{4}(\s+\d+)?",
        " ",
        label,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", label).strip()


class Line:
    def __init__(self, page: int, label: str, values: list[tuple[str, float]]):
        self.page = page
        self.label = label  # text left of the value columns
        self.values = values  # (token, right edge x)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Line(p{self.page} {self.label!r} {[t for t, _ in self.values]})"

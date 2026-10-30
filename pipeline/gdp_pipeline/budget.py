"""The Union Budget's assumption for nominal GDP.

Budget at a Glance prints, under its headline table, the GDP used for the
% of GDP figures, e.g. "GDP for BE 2023-2024 has been projected at
₹3,01,75,065 crore assuming 10.5% growth over the estimated Nominal GDP of
₹2,73,07,751 crore as per the First Advance Estimates". This is the
government's working forecast of nominal (not real) GDP for the budget year.

From 2024-25 the page is bilingual (Hindi and English side by side), so the
English half of the page is read on its own.
"""

import re
from pathlib import Path

from .sources import fy

ROOT = Path(__file__).resolve().parents[2]

SENTENCE_RE = re.compile(
    r"GDP for (?:the )?(?:Budget )?(?:BE|FY|Budget Estimates?)?\s*(?:FY\s*)?(?P<year>\d{4}\s*-\s*\d{2,4})"
    r"(?:\s*\([A-Za-z]+\))?.{0,40}?(?:projected|estimated)\s+at[\s`%₹]{0,6}(?P<gdp>[\d,]{6,})\s*crore"
    r"(?P<rest>.{0,260})",
    re.I | re.S,
)
GROWTH_RE = re.compile(
    r"(?P<pct>\d+(?:\.\d+)?)\s*%\s*(?:growth\s*)?over\s+the\s+(?P<basis>.{0,90}?)\s*(?:of|at)\s*[\s`₹-]{0,4}(?P<base>[\d,]{6,})\s*crore",
    re.I | re.S,
)

# Numbers missing from a PDF's text layer, read from the rendered page instead.
# Each is checked: the stated growth % must reproduce from the two numbers.
IMAGE_READ = {
    "2025-26": {
        "text": "The GDP for FY 2025-26 is estimated at ₹ 356,97,923 crore, which is 10.1% over the Revised "
        "Estimates for FY 2024-25 of ₹ 324,11,406 crore released by NSO.",
        "note": "The two rupee amounts are not in the PDF's text layer; they were read from the rendered page.",
    },
}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def page_texts(path: Path) -> list[str]:
    """Whole-page text, then the right half of each page (the English column on bilingual pages)."""
    import pdfplumber

    out = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False)
            right = [w for w in words if w["x0"] > page.width * 0.48]
            right.sort(key=lambda w: (round(w["top"] / 3), w["x0"]))
            out.append(" ".join(w["text"] for w in right))
    return [re.sub(r"\s+", " ", t) for t in out]


def parse_sentence(text: str) -> dict | None:
    m = SENTENCE_RE.search(text)
    if not m:
        return None
    sentence = text[m.start(): m.end("gdp") + len(" crore")]
    out = {"gdp_crore": _num(m.group("gdp")), "printed_year": re.sub(r"\s", "", m.group("year"))}
    g = GROWTH_RE.search(m.group("rest"))
    if g:
        out.update(
            growth_pct=float(g.group("pct")),
            over=re.sub(r"\s+", " ", g.group("basis")).strip(" ,"),
            base_gdp_crore=_num(g.group("base")),
        )
        sentence = text[m.start(): m.end("rest") - len(m.group("rest")) + g.end()]
    out["text"] = sentence.strip()
    return out


def assumption(start: int, manifest: dict) -> dict | None:
    year = fy(start)
    entry = manifest.get(f"budget/{year}/bag1")
    if not entry:
        return None
    src = {"url": entry["url"], "sha256": entry["sha256"], "document": f"Budget at a Glance {year}"}
    if year in IMAGE_READ:
        parsed = parse_sentence(IMAGE_READ[year]["text"])
        return {"budget": year, **parsed, **src, "note": IMAGE_READ[year]["note"]}
    for text in page_texts(ROOT / entry["file"]):
        parsed = parse_sentence(text)
        if parsed:
            return {"budget": year, **parsed, **src}
    return None

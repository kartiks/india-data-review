"""Budget at a Glance: where its tables are on indiabudget.gov.in, and the GDP the budget assumes.

The budget and gdp areas both read Budget at a Glance: budget for its tables, gdp for the GDP assumption printed
under the headline table, e.g. "GDP for BE 2023-2024 has been projected at ₹3,01,75,065 crore assuming 10.5% growth
over the estimated Nominal GDP of ₹2,73,07,751 crore as per the First Advance Estimates". This is the government's
working forecast of nominal (not real) GDP for the budget year; budget checks its % of GDP figures against it.

From 2024-25 the page is bilingual (Hindi and English side by side), so the English half of the page is read on its
own (page_texts).
"""

import re
from pathlib import Path

from .numbers import strict_number
from .text import fy

INDIABUDGET = "https://www.indiabudget.gov.in"


# ---- where the tables are ------------------------------------------------------------------------

def site(start: int, latest: int) -> str:
    """The folder of a budget's documents. The latest budget (`latest`, its first year) is at the site's root,
    earlier ones under budget<year>/, and those before 2011-12 under budget_archive/."""
    y = fy(start)
    if start <= 2010:
        return f"{INDIABUDGET}/budget_archive/ub{y}"
    if start <= 2018:
        return f"{INDIABUDGET}/budget{start}-{start + 1}/ub{y}"
    return (INDIABUDGET if start == latest else f"{INDIABUDGET}/budget{y}") + "/doc"


def table(start: int, n: int) -> str:
    """Budget at a Glance table n, under site() and without its extension. 2016-17 names its headline table
    (table 1) bag11."""
    if start <= 2018:
        return "bag/bag11" if start == 2016 and n == 1 else f"bag/bag{n}"
    return f"Budget_at_Glance/bag{n}"


def url(start: int, latest: int, n: int = 1, ext: str = "pdf") -> str:
    return f"{site(start, latest)}/{table(start, n)}.{ext}"


# ---- the GDP assumption --------------------------------------------------------------------------

SENTENCE_RE = re.compile(
    r"GDP for (?:the )?(?:Budget )?(?:BE|FY|Budget Estimates?)?\s*(?:FY\s*)?(?P<year>\d{4}\s*-\s*\d{2,4})"
    r"(?:\s*\([A-Za-z]+\))?.{0,40}?(?:projected|estimated)\s+at[\s`%₹]{0,6}(?P<gdp>[\d,]{6,})\s*(?P<crore>crore)"
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


def parse_sentence(text: str, growth: bool = True) -> dict | None:
    """The first GDP sentence in text: {"gdp_crore", "printed_year", "text"}, and with growth=True, when the
    sentence states it, {"growth_pct", "over", "base_gdp_crore"}, with "text" running to the end of that part."""
    m = SENTENCE_RE.search(text)
    if not m:
        return None
    out = {"gdp_crore": strict_number(m.group("gdp")), "printed_year": re.sub(r"\s", "", m.group("year"))}
    sentence = text[m.start(): m.end("crore")]
    g = GROWTH_RE.search(m.group("rest")) if growth else None
    if g:
        out.update(
            growth_pct=float(g.group("pct")),
            # strip(): also a stray dash or rupee mark (printed ` in older PDFs) left in front of the words, as in
            # 2023-24's "growth over the - ` estimated Nominal GDP" ("text" keeps the sentence as printed)
            over=re.sub(r"\s+", " ", g.group("basis")).strip(" ,-`₹"),
            base_gdp_crore=strict_number(g.group("base")),
        )
        sentence = text[m.start(): m.start("rest") + g.end()]
    out["text"] = sentence.strip()
    return out


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


def texts(year: str, path: Path) -> tuple[list[str], str | None]:
    """The texts of a budget's headline table PDF to look for the GDP sentence in, and a note when they were read
    from the rendered page (IMAGE_READ) because the text layer lacks the numbers."""
    if year in IMAGE_READ:
        return [IMAGE_READ[year]["text"]], IMAGE_READ[year]["note"]
    return page_texts(path), None

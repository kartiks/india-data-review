"""Paths, tolerance and what each printed label of the Receipts table means."""

import re
from pathlib import Path

from pipeline_common import text

from ..parse import ascii_text

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "sources" / "manifest.json"
DATA = ROOT / "data"  # observations.csv, the headline figures written by build.py

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
    """An id for an unrecognised line, from its English label: at most 50 characters."""
    return text.slug(english(label), ascii_only=True, max_len=50) or "unlabelled"

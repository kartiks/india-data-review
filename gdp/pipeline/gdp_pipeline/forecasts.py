"""Published forecasts of India's real GDP growth, each tied to its official document.

The figures are listed by hand in forecast_sources/*.json, each with the exact
sentence it was read from and the document's URL. fetch.py downloads every
document; the checks (verify_quotes) find the sentence in it and check the
record against its sentences (record_problems): every number recorded (the
projection, its band and the nominal projection) is in them, and so is the
fiscal year. For the RBI, the is_first / is_last / is_first_april_policy flags
are checked against the dates of each year's records (flag_problems).

- economic_survey.json : the Economic Survey's projection for the coming year
                         (Ministry of Finance, indiabudget.gov.in)
- rbi.json             : the Reserve Bank of India's projections in its
                         monetary policy statements (rbi.org.in)
"""

import hashlib
import json
import math
import re
from pathlib import Path

from pipeline_common.text import fy, fy_start, is_fy, prev_fy

ROOT = Path(__file__).resolve().parents[2]
CURATED = Path(__file__).resolve().parent / "forecast_sources"
SOURCES = {
    "economic_survey": "Economic Survey (Ministry of Finance)",
    "rbi": "Reserve Bank of India, monetary policy statements",
}
QUOTE_FIELDS = ("quote", "quote_text_layer", "quote_2", "nominal_quote")


def load(name: str) -> list[dict]:
    path = CURATED / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else []


def doc_key(url: str) -> str:
    return "forecast/" + hashlib.sha1(url.encode()).hexdigest()[:12]


def urls(record: dict) -> list[str]:
    return [u for u in (record.get("url"), record.get("quote_2_url")) if u]


# ---- reading documents ---------------------------------------------------------

def _pdf_texts(path: Path, page: int | None) -> list[str]:
    """Text of the cited page (whole, left column, right column), or of every page if no page is cited."""
    import pdfplumber

    out = []
    with pdfplumber.open(path) as pdf:
        pages = [pdf.pages[page - 1]] if page and page <= len(pdf.pages) else pdf.pages
        for p in pages:
            w = p.width
            out += [p.extract_text() or "", p.crop((0, 0, w / 2, p.height)).extract_text() or "",
                    p.crop((w / 2, 0, w, p.height)).extract_text() or ""]
    return out


def _html_text(path: Path) -> str:
    import html

    text = path.read_text(errors="replace")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def norm(s: str) -> str:
    """Compare text ignoring layout: case, spacing, line-end hyphens, quote marks, dashes."""
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(\w)-\s+(\w)", r"\1-\2", s)
    s = re.sub(r"\s*-\s*", "-", s)
    return s.strip().lower()


# Years and period labels, which are not projections: fiscal years ('2016-17', 'H1:2019-20', '1999-2000'),
# 'FY24' / 'FY2018', calendar years ('April 2017') and quarters or halves ('Q3', 'H1').
FY_IN_TEXT = re.compile(r"(?<!\d)(?<!\d\.)(\d{4})\s*[-–]\s*(\d{4}|\d{2})(?!\.?\d)")
FY_SHORT_IN_TEXT = re.compile(r"\bFY\s?(\d{4}|\d{2})\b", re.IGNORECASE)
NOT_A_FIGURE = [FY_IN_TEXT, FY_SHORT_IN_TEXT, re.compile(r"(?<!\d)(?<!\d\.)(?:19|20)\d{2}(?!\.?\d)"),
                re.compile(r"\b[QH][1-4]\b")]


def years_in(text: str) -> set[str]:
    """The fiscal years a sentence names, in the short form: '2016-17' and '1999-2000' as written, 'FY24' as
    2023-24 and 'FY2018' as 2017-18 (the Indian fiscal year is named by the year it ends in)."""
    out = {fy(fy_start(f"{a}-{b}")) for a, b in FY_IN_TEXT.findall(text) if is_fy(f"{a}-{b}")}
    for end in FY_SHORT_IN_TEXT.findall(text):
        out.add(fy((2000 + int(end) if len(end) == 2 else int(end)) - 1))
    return out


def numbers_in(text: str) -> set[float]:
    """The figures in a sentence (with a negative sign where one is written), leaving out years and period labels,
    so that '2016-17' gives neither 2016 nor 17."""
    text = text.replace("¾", ".75").replace("½", ".5").replace("¼", ".25")
    for pattern in NOT_A_FIGURE:
        text = pattern.sub(" ", text)
    out = set()
    # a hyphen after a number is a range ('6.8-7.1'), not a minus sign
    for sign, x in re.findall(r"(\(-\)\s*|−\s*|(?<![\d.])(?<![\d.]\s)-\s*|minus\s+)?(\d+(?:\.\d+)?)", text):
        out.add(float(x))
        if sign:
            out.add(-float(x))
    return out


def _fmt_ok(value: float | None, quote: str) -> bool:
    return value is None or value in numbers_in(quote)


def record_problems(r: dict) -> list[str]:
    """What in a record its own sentences do not bear out (messages start with the record's label):

    - the projection (value, low, high) must be in `quote`;
    - the band (band_low, band_high) must be in `quote` or `quote_2`, or be the projection plus or minus the
      '(+/- x)' the quote gives;
    - the nominal projection (nominal_low, nominal_high) must be in `nominal_quote`;
    - the quotes must name the record's fiscal year, and no other year than that one and the year before (which
      a sentence names as the year growth is measured from)."""
    out = []
    label = r.get("_label", r.get("fiscal_year"))
    quote = r.get("quote") or ""
    values = [r.get("low"), r.get("high"), r.get("value")]
    if not all(_fmt_ok(v, quote) for v in values):
        out.append(f"{label}: recorded {[v for v in values if v is not None]} not all in the quote “{quote}”")
    band = [r.get("band_low"), r.get("band_high")]
    if any(v is not None for v in band):
        both = quote + " " + (r.get("quote_2") or "")
        pm = re.search(r"\+\s*/\s*-\s*(\d+(?:\.\d+)?)", quote)  # '9 per cent (+/- 0.25)'
        around = (pm is not None and None not in (r.get("low"), r.get("high"), *band)
                  and math.isclose(band[0], r["low"] - float(pm[1])) and math.isclose(band[1], r["high"] + float(pm[1])))
        if None in band or not (all(_fmt_ok(v, both) for v in band) or around):
            out.append(f"{label}: band {band} not in the quotes, nor the projection ± the quote's (+/- x): “{both.strip()}”")
    nominal = [r.get("nominal_low"), r.get("nominal_high")]
    if any(v is not None for v in nominal) and not all(_fmt_ok(v, r.get("nominal_quote") or "") for v in nominal):
        out.append(f"{label}: nominal {[v for v in nominal if v is not None]} not all in “{r.get('nominal_quote')}”")
    named = set().union(*(years_in(r.get(f) or "") for f in QUOTE_FIELDS))
    year = r.get("fiscal_year")
    if not named:
        out.append(f"{label}: the quotes name no fiscal year")
    elif year not in named or named - {year, prev_fy(year)}:
        out.append(f"{label}: the quotes name {sorted(named)}, not {year}")
    return out


def has_figure(r: dict) -> bool:
    """Whether a record gives a full-year projection as a number (not 'negative', not quarters only)."""
    return any(r.get(k) is not None for k in ("value", "low", "high"))


def flag_problems(records: list[dict], label=lambda r: r["fiscal_year"]) -> list[str]:
    """The RBI's flags, checked against the dates of each fiscal year's records (as gdp/README.md defines them):

    - is_first: the year's first record with a figure, and no other;
    - is_first_april_policy: the first record with a figure from the April-May policy at the start of the year
      (the first of the fiscal year), if there is one, and no other;
    - is_latest_available: at most one per year, on its latest record, while the year is still being projected;
    - is_last: otherwise, the year's last record with a figure, and no other."""
    out = []
    by_year: dict[str, list[dict]] = {}
    for r in records:
        by_year.setdefault(r["fiscal_year"], []).append(r)
    for year, rs in by_year.items():
        rs = sorted(rs, key=lambda r: r["date"])
        figures = [r for r in rs if has_figure(r)]
        start = fy_start(year)
        april = [r for r in figures if f"{start}-04-01" <= r["date"] <= f"{start}-05-31"]
        running = [r for r in rs if r.get("is_latest_available")]
        want = {
            "is_first": figures[:1],
            "is_first_april_policy": april[:1],
            "is_latest_available": rs[-1:] if running else [],
            "is_last": [] if running else figures[-1:],
        }
        for flag, expected in want.items():
            have = [r for r in rs if r.get(flag)]
            if [id(r) for r in have] != [id(r) for r in expected]:
                out.append(f"{year}: {flag} is set on {[label(r) for r in have] or 'no record'}, "
                           f"expected {[label(r) for r in expected] or 'no record'}")
    return out


def words(s: str) -> list[str]:
    """Lower-case words and numbers, splitting on dashes and punctuation (so 'manufac-\nthe' gives 'the')."""
    return re.findall(r"[a-z0-9½¾¼']+(?:\.[0-9]+)?", s.lower().replace("’", "'"))


def in_order(quote: str, text: str, max_gap: int = 8) -> bool:
    """The quote's words appear in order, with at most max_gap other words between neighbours
    (for sentences broken up by a margin box or a second column)."""
    q, t = words(quote), words(text)
    for start in (i for i, w in enumerate(t) if w == q[0]):
        pos, ok = start, True
        for w in q[1:]:
            nxt = next((j for j in range(pos + 1, min(len(t), pos + 2 + max_gap)) if t[j] == w), None)
            if nxt is None:
                ok = False
                break
            pos = nxt
        if ok:
            return True
    return False


_cache: dict[str, list[str]] = {}


def document_texts(manifest: dict, url: str, page: int | None) -> list[str] | None:
    entry = manifest.get(doc_key(url))
    if not entry:
        return None
    k = f"{url}#{page}"
    if k not in _cache:
        path = ROOT / entry["file"]
        _cache[k] = _pdf_texts(path, page) if path.suffix == ".pdf" else [_html_text(path)]
    return _cache[k]


def verify_quotes(ds: dict) -> tuple[int, list[str], list[str]]:
    manifest = json.loads((ROOT / "sources" / "manifest.json").read_text())
    checked, failures, notes = 0, [], []
    found = 0
    for name in SOURCES:
        for r in load(name):
            label = f"{SOURCES[name]}, {r.get('statement') or r.get('survey')} → {r['fiscal_year']}"
            for field in QUOTE_FIELDS:
                q = r.get(field)
                if not q:
                    continue
                if field == "quote_text_layer":
                    continue  # checked together with "quote"
                url = r.get("quote_2_url") if field == "quote_2" and r.get("quote_2_url") else r["url"]
                page = r.get("quote_2_pdf_page") if field == "quote_2" and r.get("quote_2_pdf_page") else r.get("pdf_page")
                texts = document_texts(manifest, url, page)
                checked += 1
                if texts is None:
                    failures.append(f"{label}: document not downloaded ({url})")
                    continue
                candidates = [q] + ([r["quote_text_layer"]] if field == "quote" and r.get("quote_text_layer") else [])
                if any(norm(c) in norm(t) for c in candidates for t in texts):
                    found += 1
                elif any(in_order(c, t) for c in candidates for t in texts):
                    found += 1
                    notes.append(f"{label}: {field} found with other text (a margin box or second column) printed "
                                 "between its words")
                else:
                    failures.append(f"{label}: {field} not found on {'page ' + str(page) if page else 'the page'} of {url}: “{q}”")
            # the recorded numbers and year must be in the sentences
            checked += 1
            failures += record_problems({**r, "_label": label})
        if name == "rbi":
            checked += 1
            failures += flag_problems(load(name), lambda r: f"{r['statement']} ({r['date']})")
    notes.append(f"{found} quoted sentences found in their official documents; recorded numbers, bands and years "
                 "checked against each record's sentences; the RBI's first and last flags checked against the dates.")
    return checked, failures, notes


# ---- dataset -------------------------------------------------------------------

def build(manifest: dict) -> dict:
    out = {}
    for name, title in SOURCES.items():
        rows = []
        for r in load(name):
            entry = manifest.get(doc_key(r["url"]), {})
            rows.append({**r, "source": title, "sha256": entry.get("sha256")})
        out[name] = rows
    return out

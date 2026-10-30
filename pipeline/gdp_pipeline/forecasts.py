"""Published forecasts of India's real GDP growth, each tied to its official document.

The figures are listed by hand in forecast_sources/*.json, each with the exact
sentence it was read from and the document's URL. The pipeline downloads every
document and checks that the sentence is there and that the numbers in the
sentence are the numbers recorded (see verify_quotes).

- economic_survey.json : the Economic Survey's projection for the coming year
                         (Ministry of Finance, indiabudget.gov.in)
- rbi.json             : the Reserve Bank of India's projections in its
                         monetary policy statements (rbi.org.in)
"""

import hashlib
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURATED = Path(__file__).resolve().parent / "forecast_sources"
RAW = ROOT / "sources" / "raw" / "forecasts"
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


def fetch(manifest: dict, force: bool) -> None:
    from .fetch import RAW as RAW_ROOT, get, save

    for name in SOURCES:
        for r in load(name):
            for url in urls(r):
                key = doc_key(url)
                if key in manifest and not force:
                    continue
                try:
                    content = get(url)
                except Exception as exc:  # noqa: BLE001 - report and carry on; the check will fail
                    print(f"{key}: {url} -> {exc}")
                    continue
                ext = "pdf" if content.startswith(b"%PDF") else "html"
                save(manifest, key, RAW_ROOT / f"{key}.{ext}", content, url, {"document": f"{name} {r['fiscal_year']}"})
                print(f"{key}: saved {url} ({len(content):,} bytes)")
                time.sleep(0.5)


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


def numbers_in(text: str) -> set[float]:
    text = text.replace("¾", ".75").replace("½", ".5").replace("¼", ".25")
    out = set()
    for sign, x in re.findall(r"(\(-\)\s*|−\s*|-\s*|minus\s+)?(\d+(?:\.\d+)?)", text):
        out.add(float(x))
        if sign.strip() in ("(-)", "−", "minus") or (sign.strip() == "-" and not re.search(r"\d$", sign)):
            out.add(-float(x))
    return out


def _fmt_ok(value: float | None, quote: str) -> bool:
    return value is None or value in numbers_in(quote)


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
            # the recorded numbers must be in the sentence
            checked += 1
            quote = r.get("quote", "")
            values = [r.get("low"), r.get("high"), r.get("value")]
            if not all(_fmt_ok(v, quote) for v in values):
                failures.append(f"{label}: recorded {[v for v in values if v is not None]} not all in the quote “{quote}”")
            if r.get("nominal_low") is not None:
                checked += 1
                if not _fmt_ok(r["nominal_low"], r.get("nominal_quote") or ""):
                    failures.append(f"{label}: nominal {r['nominal_low']} not in “{r.get('nominal_quote')}”")
    notes.append(f"{found} quoted sentences found in their official documents; recorded numbers checked against each sentence.")
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

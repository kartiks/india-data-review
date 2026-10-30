"""Consumer Price Index on base 2024 = 100, read from MoSPI's monthly press releases (PIB pages).

Each release carries:
- a summary table: CPI (General) and the Consumer Food Price Index (CFPI), index and inflation, rural / urban /
  combined, for the month (provisional) and the month before (final);
- Annexure I: the 12 divisions (food and beverages, housing, transport ...) for the month;
- Annexure II: the 43 groups for the month;
- Annexure III: every state's general index and inflation for the month;
- Annexure IV: the All-India general index (and inflation from January 2026) for every month from January 2025.

Values are read exactly as printed. MoSPI compiles indices from unrounded values and prints two decimals.
"""

import re
from html.parser import HTMLParser

MONTH_ABBR = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
SECTORS = ("Rural", "Urban", "Combined")


class Tables(HTMLParser):
    """Every <table> as a list of rows of cell texts (whitespace collapsed)."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._stack: list[list[list[str]]] = []
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._stack[-1].append([])
        elif tag in ("td", "th") and self._stack:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._stack and self._stack[-1]:
            self._stack[-1][-1].append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._stack and self._stack[-1]:
            row = self._stack[-1][-1]
            while row and row[-1] == "":  # some tables end each row with an empty cell
                row.pop()
        elif tag == "table" and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def text_of(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    import html as h

    return re.sub(r"\s+", " ", h.unescape(t)).strip()


def num(s: str) -> float | None:
    s = s.replace(",", "").replace("*", "").strip()
    if s in ("", "-", "–"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def numbers(row: list[str]) -> list[float | None]:
    return [num(c) for c in row]


def six(row: list[str]) -> list[float | None] | None:
    """The last six cells as numbers (index R/U/C, inflation R/U/C), if they look like that."""
    vals = [num(c) for c in row[-6:]]
    if len(row) < 7 or sum(v is not None for v in vals) < 3:
        return None
    return vals


def parse(html: str, month: str) -> dict:
    """Read one release. month = '2026-09' (the release's own month)."""
    p = Tables()
    p.feed(html)
    out: dict = {"month": month, "divisions": [], "groups": [], "states": [], "series": [], "series_combined": [],
                 "linking": {}, "weights": [], "summary": {}, "problems": []}
    for t in p.tables:
        flat = " ".join(" ".join(r) for r in t)
        if "Division name" in flat:
            for r in t:
                if r and re.fullmatch(r"\d{2}", r[0]) and (v := six(r)):
                    out["divisions"].append({"code": r[0], "name": " ".join(r[1:-6]).strip(), "values": v})
                elif r and r[0].strip() == "All India" and (v := six(r)):
                    out["divisions"].append({"code": "00", "name": "All India", "values": v})
        elif "Group name" in flat:
            for r in t:
                code = next((c for c in r[:3] if re.fullmatch(r"\d{2}\.\d", c)), None)
                if code and (v := six(r)):
                    i = r.index(code)
                    out["groups"].append({"code": code, "name": " ".join(r[i + 1:-6]).strip(), "values": v})
        elif "Andhra Pradesh" in flat and "Uttar Pradesh" in flat:
            for r in t:
                name = " ".join(c for c in r[:-6] if c and not re.fullmatch(r"\d+\.?", c)).replace("*", "").strip()
                if len(r) >= 7 and name and (v := six(r)):
                    out["states"].append({"name": name, "values": v, "printed": r[-6:]})
        elif re.search(r"\bJan-25\b", flat):
            for r in t:
                m = re.fullmatch(r"([A-Z][a-z]{2})-(\d{2})\*?", r[0].strip()) if r else None
                if not m:
                    continue
                ym = f"20{m.group(2)}-{MONTH_ABBR[m.group(1)]:02d}"
                if len(r) == 4 and "Inflation" in " ".join(t[0]):  # index only (2025 rows have no inflation yet)
                    r = r + ["", "", ""]
                if v := six(r):
                    out["series"].append({"month": ym, "values": v, "provisional": r[0].strip().endswith("*")})
                elif len(r) == 3:  # first release: combined CPI and CFPI index only
                    out["series_combined"].append({"month": ym, "cpi": num(r[1]), "cfpi": num(r[2])})
        elif "Linking factor" in flat and not out["linking"]:
            for r in t:
                if len(r) >= 2 and r[-2] in SECTORS and num(r[-1]) is not None:
                    out["linking"][r[-2]] = num(r[-1])
        elif "CPI 2012" in flat and "CPI 2024" in flat:
            for r in t:
                vals = [num(c) for c in r[1:]]
                if len(r) == 7 and all(v is not None for v in vals):
                    out["weights"].append({"division": r[0], "rural_2012": vals[0], "rural_2024": vals[1], "urban_2012": vals[2],
                                           "urban_2024": vals[3], "combined_2012": vals[4], "combined_2024": vals[5]})
        elif "CFPI" in flat and "CPI" in flat and not out["summary"]:
            # rows: CPI (General) inflation, CFPI inflation, CPI (General) index, CFPI index. Columns: R/U/C for each
            # month in the header, which some releases print provisional-first and others final-first.
            header = [c for c in t[0] if c] if t else []
            order = ["current" if "Provisional" in c else "previous" for c in header if "Provisional" in c or "Final" in c]
            kind = None
            for r in t:
                cells = [c for c in r if c]
                label = " ".join(c for c in cells if num(c) is None)
                vals = [num(c) for c in cells if num(c) is not None]
                if "Inflation" in label:
                    kind = "inflation"
                elif "Index" in label:
                    kind = "index"
                what = "cfpi" if "CFPI" in label else "general"
                bad = [c for c in cells if re.search(r"\d", c) and num(c) is None]
                if kind and bad and ("CFPI" in label or "CPI" in label):
                    out["problems"].append(f"{month}: summary table, {what} {kind}: not a number as printed: {bad}")
                elif kind and len(vals) in (3, 6):
                    blocks = order[: len(vals) // 3] or ["current"]
                    for b, start in zip(blocks, range(0, len(vals), 3)):
                        out["summary"].setdefault(b, {})[f"{what}_{kind}"] = vals[start:start + 3]
    text = text_of(html)
    m = re.search(r"for the month of ([A-Za-z]+),? (\d{4}) over [A-Za-z]+,? \d{4} is ([\d.]+) ?%", text)
    if m:
        out["headline"] = {"sentence": m.group(0), "month_name": m.group(1), "year": m.group(2), "combined": float(m.group(3))}
    m = re.search(r"Corresponding inflation rates for rural and urban are ([\d.]+) ?% and ([\d.]+) ?%", text)
    if m:
        out.setdefault("headline", {})["rural"], out["headline"]["urban"] = float(m.group(1)), float(m.group(2))
    for part in ("divisions", "states"):
        if not out[part]:
                out["problems"].append(f"{month}: no {part} table found")
    if not out["series"] and not out["series_combined"]:
        out["problems"].append(f"{month}: no All-India series table found")
    return out


def pdf_numbers(path) -> list[str]:
    """All decimal numbers in a release PDF's text, written with two decimals (the PDF sometimes prints 102.8 for 102.80),
    used to cross-check the web page's tables."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return [f"{float(x):.2f}" for x in re.findall(r"-?\d+\.\d{1,2}\b", text)]

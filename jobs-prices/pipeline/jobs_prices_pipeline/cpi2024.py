"""Consumer Price Index on base 2024 = 100, read from MoSPI's monthly press releases (PIB pages).

Each release carries:
- a summary table: CPI (General) and the Consumer Food Price Index (CFPI), index and inflation, rural / urban /
  combined, for the month (provisional) and the month before (final);
- Annexure I: the 12 divisions (food and beverages, housing, transport ...) for the month;
- Annexure II: the 43 groups for the month;
- Annexure III: every state's general index and inflation for the month;
- Annexure IV: the All-India general index (and inflation from January 2026) for every month from January 2025.

Values are read exactly as printed. MoSPI compiles indices from unrounded values and prints two decimals.

parse() reads one release; dataset() reads every release in sources.CPI2024_RELEASES and builds the series the site
uses (the All-India series, the food index by month), cpi2024.csv and the site's part of jobs_prices.json.
"""

import re
from html.parser import HTMLParser

from pipeline_common.numbers import number

from .common import ROOT
from .sources import CPI2024_RELEASES

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
    """A figure in a press release table: footnote marks ('*') ignored; '-', blanks and anything else not a
    number are None."""
    return number(s, strip="*")


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
            out["divisions"] += divisions(t)
        elif "Group name" in flat:
            out["groups"] += groups(t)
        elif "Andhra Pradesh" in flat and "Uttar Pradesh" in flat:
            out["states"] += states(t)
        elif re.search(r"\bJan-25\b", flat):
            series, combined = all_india_series(t)
            out["series"] += series
            out["series_combined"] += combined
        elif "Linking factor" in flat and not out["linking"]:
            out["linking"] = linking(t)
        elif "CPI 2012" in flat and "CPI 2024" in flat:
            out["weights"] += weights(t)
        elif "CFPI" in flat and "CPI" in flat and not out["summary"]:
            out["summary"], problems = summary(t, month)
            out["problems"] += problems
    if headline := headline_figures(text_of(html)):
        out["headline"] = headline
    for part in ("divisions", "states"):
        if not out[part]:
            out["problems"].append(f"{month}: no {part} table found")
    if not out["series"] and not out["series_combined"]:
        out["problems"].append(f"{month}: no All-India series table found")
    return out


def divisions(t: list[list[str]]) -> list[dict]:
    """Annexure I: the 12 divisions, and the All-India row (code '00')."""
    out = []
    for r in t:
        if r and re.fullmatch(r"\d{2}", r[0]) and (v := six(r)):
            out.append({"code": r[0], "name": " ".join(r[1:-6]).strip(), "values": v})
        # The releases print the All-India row with an empty code cell before the name.
        elif [c.strip() for c in r[:-6] if c.strip()] == ["All India"] and (v := six(r)):
            out.append({"code": "00", "name": "All India", "values": v})
    return out


def groups(t: list[list[str]]) -> list[dict]:
    """Annexure II: the 43 groups."""
    out = []
    for r in t:
        code = next((c for c in r[:3] if re.fullmatch(r"\d{2}\.\d", c)), None)
        if code and (v := six(r)):
            i = r.index(code)
            out.append({"code": code, "name": " ".join(r[i + 1:-6]).strip(), "values": v})
    return out


def states(t: list[list[str]]) -> list[dict]:
    """Annexure III: each state's general index and inflation."""
    out = []
    for r in t:
        name = " ".join(c for c in r[:-6] if c and not re.fullmatch(r"\d+\.?", c)).replace("*", "").strip()
        if len(r) >= 7 and name and (v := six(r)):
            out.append({"name": name, "values": v, "printed": r[-6:]})
    return out


def all_india_series(t: list[list[str]]) -> tuple[list[dict], list[dict]]:
    """Annexure IV: the All-India index (and inflation) for every month from January 2025, a '*' marking the
    provisional month; and, in the first release, the combined CPI and CFPI index only."""
    series, combined = [], []
    for r in t:
        m = re.fullmatch(r"([A-Z][a-z]{2})-(\d{2})\*?", r[0].strip()) if r else None
        if not m:
            continue
        ym = f"20{m.group(2)}-{MONTH_ABBR[m.group(1)]:02d}"
        if len(r) == 4 and "Inflation" in " ".join(t[0]):  # index only (2025 rows have no inflation yet)
            r = r + ["", "", ""]
        if v := six(r):
            series.append({"month": ym, "values": v, "provisional": r[0].strip().endswith("*")})
        elif len(r) == 3:  # first release: combined CPI and CFPI index only
            combined.append({"month": ym, "cpi": num(r[1]), "cfpi": num(r[2])})
    return series, combined


def linking(t: list[list[str]]) -> dict[str, float]:
    """The first release's linking factors (new base ÷ old base), by sector."""
    return {r[-2]: num(r[-1]) for r in t if len(r) >= 2 and r[-2] in SECTORS and num(r[-1]) is not None}


def weights(t: list[list[str]]) -> list[dict]:
    """The first release's division weights, base 2012 and base 2024."""
    out = []
    for r in t:
        vals = [num(c) for c in r[1:]]
        if len(r) == 7 and all(v is not None for v in vals):
            out.append({"division": r[0], "rural_2012": vals[0], "rural_2024": vals[1], "urban_2012": vals[2],
                        "urban_2024": vals[3], "combined_2012": vals[4], "combined_2024": vals[5]})
    return out


def summary(t: list[list[str]], month: str) -> tuple[dict, list[str]]:
    """The summary table, {"current" | "previous": {"general_inflation" | "cfpi_inflation" | "general_index" |
    "cfpi_index": [rural, urban, combined]}}, and its problems.

    Rows: CPI (General) inflation, CFPI inflation, CPI (General) index, CFPI index. Columns: R/U/C for each month in
    the header, which some releases print provisional-first and others final-first."""
    out: dict = {}
    problems = []
    header = [c for c in t[0] if c] if t else []
    order = ["current" if "Provisional" in c else "previous" for c in header if "Provisional" in c or "Final" in c]
    kind = None
    for r in t:
        cells = [c for c in r if c]
        # A figure is a cell with a digit; one that is not a number as printed (e.g. '109.`39') is read as
        # missing, so the rest of its row is kept.
        figures = [c for c in cells if re.search(r"\d", c)]
        label = " ".join(c for c in cells if c not in figures)
        vals = [num(c) for c in figures]
        if "Inflation" in label:
            kind = "inflation"
        elif "Index" in label:
            kind = "index"
        what = "cfpi" if "CFPI" in label else "general"
        bad = [c for c in figures if num(c) is None]
        if kind and bad and ("CFPI" in label or "CPI" in label):
            problems.append(f"{month}: summary table, {what} {kind}: not a number as printed, read as missing: {bad}")
        if kind and len(vals) in (3, 6):
            blocks = order[: len(vals) // 3] or ["current"]
            for b, start in zip(blocks, range(0, len(vals), 3)):
                out.setdefault(b, {})[f"{what}_{kind}"] = vals[start:start + 3]
    return out, problems


def headline_figures(text: str) -> dict:
    """The release's opening sentences: combined inflation, then rural and urban."""
    out: dict = {}
    m = re.search(r"for the month of ([A-Za-z]+),? (\d{4}) over [A-Za-z]+,? \d{4} is ([\d.]+) ?%", text)
    if m:
        out = {"sentence": m.group(0), "month_name": m.group(1), "year": m.group(2), "combined": float(m.group(3))}
    m = re.search(r"Corresponding inflation rates for rural and urban are ([\d.]+) ?% and ([\d.]+) ?%", text)
    if m:
        out["rural"], out["urban"] = float(m.group(1)), float(m.group(2))
    return out


def pdf_numbers(path) -> list[str]:
    """All decimal numbers in a release PDF's text, written with two decimals (the PDF sometimes prints 102.8 for 102.80),
    used to cross-check the web page's tables."""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return [f"{float(x):.2f}" for x in re.findall(r"-?\d+\.\d{1,2}\b", text)]


# ---- the series across releases ------------------------------------------------------------------

def dataset(manifest: dict) -> dict:
    """Every monthly release read in full, plus the series the site uses:
    - All-India general index and inflation from the latest release's Annexure IV (each month final except the latest);
    - the food price index (CFPI) from the release summaries (final where a later release gives it);
    - divisions, groups and states for each month as first published (provisional; later releases do not repeat them).
    """
    releases: dict[str, dict] = {}
    for month in CPI2024_RELEASES:
        e = manifest.get(f"cpi2024/{month}")
        if not e or e.get("empty"):
            continue
        r = parse((ROOT / e["file"]).read_text(), month)
        r["source"], r["url"] = f"cpi2024/{month}", e["url"]
        pdf = manifest.get(f"cpi2024/{month}/pdf")
        r["pdf"] = pdf["file"] if pdf and not pdf.get("empty") else None
        r["pdf_url"] = pdf["url"] if r["pdf"] else None
        releases[month] = r
    latest = max(releases) if releases else None
    series = [{**s, "source": f"cpi2024/{latest}"} for s in releases[latest]["series"]] if latest else []
    jan = releases.get(min(releases)) if releases else None
    return {"releases": releases, "latest": latest, "series": series, "cfpi": cfpi_by_month(releases),
            "linking": jan["linking"] if jan else {}, "weights": jan["weights"] if jan else []}


def cfpi_by_month(releases: dict[str, dict]) -> dict[str, dict]:
    """The food price index (CFPI), index and inflation (rural, urban, combined), for each month: as first published
    (provisional), then replaced figure by figure with the final ones in the next release. A figure the next release
    does not give (not printed as a number) keeps its provisional value, and the month stays provisional until the
    next release gives every final figure."""
    cfpi: dict[str, dict] = {}
    for month, r in sorted(releases.items()):
        cur, prev = r["summary"].get("current", {}), r["summary"].get("previous", {})
        if "cfpi_index" in cur or "cfpi_inflation" in cur:
            cfpi.setdefault(month, {"index": cur.get("cfpi_index"), "inflation": cur.get("cfpi_inflation"), "provisional": True,
                                    "source": r["source"]})
        pm = f"{int(month[:4]) - (month[5:] == '01')}-{(int(month[5:]) - 2) % 12 + 1:02d}"
        final = {k: prev.get(f"cfpi_{k}") for k in ("index", "inflation")}
        if pm not in cfpi or all(v is None or set(v) == {None} for v in final.values()):
            continue  # no final figure read: the month stays as first published
        old = cfpi[pm]
        merged = {k: [f if f is not None else p for f, p in zip(v, old[k] or [None] * len(v))] if v else old[k]
                  for k, v in final.items()}
        complete = all(v and None not in v for v in final.values())
        cfpi[pm] = {**merged, "provisional": not complete, "source": r["source"]}
    return cfpi


def csv_rows(c: dict) -> list[dict]:
    """Every figure read from the releases, one line each, for cpi2024.csv."""
    out = []
    for month, r in sorted(c["releases"].items()):
        base = {"release_month": month, "source": r["source"]}
        for table, rows in (("division", r["divisions"]), ("group", r["groups"]), ("state", r["states"])):
            for x in rows:
                for i, sec in enumerate(SECTORS):
                    out.append({**base, "table": table, "month": month, "code": x.get("code", ""), "name": x["name"], "sector": sec,
                                "index": x["values"][i], "inflation": x["values"][i + 3], "status": "provisional"})
        for x in r["series"]:
            for i, sec in enumerate(SECTORS):
                out.append({**base, "table": "all_india_series", "month": x["month"], "code": "", "name": "All India", "sector": sec,
                            "index": x["values"][i], "inflation": x["values"][i + 3], "status": "provisional" if x["provisional"] else "final"})
        for x in r["series_combined"]:
            out.append({**base, "table": "all_india_series", "month": x["month"], "code": "", "name": "All India", "sector": "Combined",
                        "index": x["cpi"], "inflation": None, "status": "provisional" if x["month"] == month else "final"})
    return out


def site(c: dict) -> dict:
    rel = c["releases"]
    return {
        "latest": c["latest"],
        "series_fields": ["month", "index_rural", "index_urban", "index_combined", "inflation_rural", "inflation_urban",
                          "inflation_combined", "provisional"],
        "series": [[x["month"], *x["values"], x["provisional"]] for x in c["series"]],
        "cfpi": {m: v for m, v in sorted(c["cfpi"].items())},
        "fields": ["code", "name", "index_rural", "index_urban", "index_combined", "inflation_rural", "inflation_urban", "inflation_combined"],
        "divisions": {m: [[x["code"], x["name"], *x["values"]] for x in r["divisions"]] for m, r in sorted(rel.items())},
        "groups": {m: [[x["code"], x["name"], *x["values"]] for x in r["groups"]] for m, r in sorted(rel.items())},
        "states": {m: [["", x["name"], *x["values"]] for x in r["states"]] for m, r in sorted(rel.items())},
        "releases": {m: {"page": r["url"], "pdf": r["pdf_url"]} for m, r in sorted(rel.items())},
        "linking": c["linking"],
        "weights": c["weights"],
    }

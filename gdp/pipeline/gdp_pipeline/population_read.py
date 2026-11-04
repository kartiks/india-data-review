"""The documents population is read from (see population.py), and reading them: the 2019 projections (PDF), MoSPI's
press notes (PDF, rows quoted in population_sources/mospi_press_notes.json), the RBI's handbook tables (xlsx) and
MoSPI's National Accounts Statistics per-capita statement (xlsx, downloaded by hand). fetch.py downloads them."""

import hashlib
import json
import re
from pathlib import Path

from pipeline_common.numbers import strict_number
from pipeline_common.text import fy


ROOT = Path(__file__).resolve().parents[2]
CURATED = Path(__file__).resolve().parent / "population_sources"

PROJECTIONS = {
    "key": "population/projections-2019",
    "url": "https://nhm.gov.in/New_Updates_2018/Report_Population_Projection_2019.pdf",
    "title": "Census of India 2011: Population Projections for India and States 2011-2036, Report of the Technical "
             "Group on Population Projections (National Commission on Population, November 2019)",
    "table": "Table 14: projected total population as on 1st October ('000)",
    "pdf_page": 125,
}
RBI_EDITION = "2025-26"
RBI_TABLES = {
    "cur": {
        "key": "population/rbi-hbs-table-1",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/1T_HBIE310720260FBAA53A59A94B94A78CB8313C150B62.XLSX",
        "title": f"RBI, Handbook of Statistics on the Indian Economy {RBI_EDITION}, Table 1: Macro-Economic Aggregates (at current prices)",
    },
    "con": {
        "key": "population/rbi-hbs-table-2",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/2T_HBIE310720261ED415A38F9E465C9B9BEDEA897741FB.XLSX",
        "title": f"RBI, Handbook of Statistics on the Indian Economy {RBI_EDITION}, Table 2: Macro-Economic Aggregates (at constant prices)",
    },
}

# MoSPI's National Accounts Statistics: its per-capita statement gives population to the thousand and unrounded
# per-person figures for the years the publication covers. MoSPI's publication pages need a browser, so the file is
# downloaded by hand and added with `uv run python -m gdp_pipeline.population --add <file>` (see gdp/README.md).
NAS_STATEMENTS = [
    {
        "key": "population/nas-2026-statement-1.2",
        "url": "https://mospi.gov.in/publications-reports/innerpage/2861",
        "document": "MoSPI, National Accounts Statistics 2026, Statement 1.2: Per capita income, product and final consumption",
        "date": "2026-08-31",
        "base": "2022-23",
    },
]


def press_notes() -> list[dict]:
    return json.loads((CURATED / "mospi_press_notes.json").read_text())


def note_key(url: str) -> str:
    return "population/press-note-" + hashlib.sha1(url.encode()).hexdigest()[:12]


def documents() -> list[tuple[str, str, str]]:
    """(manifest key, url, extension) of every document this module reads."""
    out = [(PROJECTIONS["key"], PROJECTIONS["url"], "pdf")]
    out += [(t["key"], t["url"], "xlsx") for t in RBI_TABLES.values()]
    out += [(note_key(n["url"]), n["url"], "pdf") for n in press_notes()]
    return out


def path_of(manifest: dict, key: str) -> Path | None:
    entry = manifest.get(key)
    return ROOT / entry["file"] if entry and (ROOT / entry["file"]).exists() else None


def page_text(path: Path, page: int) -> str:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return (pdf.pages[page - 1].extract_text() or "") if page <= len(pdf.pages) else ""


# ---- reading the sources ---------------------------------------------------------

def read_projections(manifest: dict) -> tuple[dict, list[str]]:
    """{fiscal year: {persons, male, female}} in thousands, from Table 14 (India columns)."""
    path = path_of(manifest, PROJECTIONS["key"])
    if not path:
        return {}, [f"{PROJECTIONS['title']}: not downloaded"]
    text = page_text(path, PROJECTIONS["pdf_page"])
    problems = []
    if "Projected Total Population by Sex as on 1st October" not in text or "INDIA" not in text:
        problems.append(f"page {PROJECTIONS['pdf_page']} is not Table 14 for India")
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(20[1-3]\d) ([\d,]+) ([\d,]+) ([\d,]+) ", line)
        if m:
            if fy(int(m[1])) in out:
                problems.append(f"projections: year {m[1]} read twice on page {PROJECTIONS['pdf_page']}")
            out[fy(int(m[1]))] = {"persons": strict_number(m[2]), "male": strict_number(m[3]), "female": strict_number(m[4])}
    return out, problems


def numbers(quote: str) -> list[float]:
    """The figures in a quoted statement row, leaving out its row number."""
    body = re.sub(r"^\d+\s+", "", quote)
    return [strict_number(x) for x in re.findall(r"(?<![\w.,])\d[\d,]*(?![\w.])", body)]


def read_notes(manifest: dict) -> tuple[list[dict], list[str], int]:
    """Each press-note table with its figures by year, and any quote not found in its document."""
    out, problems, checked = [], [], 0
    for n in press_notes():
        path = path_of(manifest, note_key(n["url"]))
        for t in n["tables"]:
            text = page_text(path, t["pdf_page"]) if path else ""
            flat = re.sub(r"\s+", " ", text)
            figures = {}
            for row, quote in t["rows"].items():
                checked += 1
                where = f"{n['document']}, {t['statement']}, '{row}'"
                if not path:
                    problems.append(f"{where}: document not downloaded ({n['url']})")
                elif quote not in flat:
                    problems.append(f"{where}: row not found on PDF page {t['pdf_page']}: “{quote}”")
                vals = numbers(quote)
                if len(vals) != len(n["years"]):
                    problems.append(f"{where}: {len(vals)} figures for {len(n['years'])} years in “{quote}”")
                    continue
                figures[row] = dict(zip(n["years"], vals))
            out.append({"document": n["document"], "date": n["date"], "base": n["base"], "url": n["url"],
                        "statement": t["statement"], "prices": t["prices"], "years": n["years"], "figures": figures})
    return out, problems, checked


RBI_ROWS = {
    "Population (in Lakhs)": "population_lakh",
    "Gross Domestic Product": "gdp", "Gross National Income": "gni", "Net National Income": "nni",
    "Private Final Consumption Expenditure": "pfce",
    "Per Capita GDP (₹)": "pc_gdp", "Per Capita GNI (₹)": "pc_gni", "Per Capita NNI (₹)": "pc_nni",
    "Per Capita PFCE (₹)": "pc_pfce",
}


def read_rbi(manifest: dict) -> tuple[list[dict], list[str]]:
    """The RBI's tables as press-note-like records: one per (prices, base)."""
    import openpyxl

    out, problems = [], []
    for prices, t in RBI_TABLES.items():
        path = path_of(manifest, t["key"])
        if not path:
            problems.append(f"{t['title']}: not downloaded")
            continue
        rows = list(openpyxl.load_workbook(path, data_only=True).active.iter_rows(values_only=True))
        head = next((r for r in rows if "Item/Year" in r), None)
        base_row = next((r for r in rows if any(isinstance(c, str) and c.startswith("(Base Year") for c in r)), None)
        if not head or not base_row:
            problems.append(f"{t['title']}: layout changed (no year or base-year row)")
            continue
        bases, current = [], None
        for c in base_row:
            if isinstance(c, str) and (m := re.search(r"Base Year: (\d{4}-\d{2})", c)):
                current = m[1]
            bases.append(current)
        label = head.index("Item/Year")
        by_base: dict[str, dict] = {}
        for r in rows:
            name = r[label].strip() if isinstance(r[label], str) else None
            if name not in RBI_ROWS:
                continue
            for i in range(label + 1, len(r)):
                if isinstance(head[i], str) and re.fullmatch(r"\d{4}-\d{2}", head[i]) and bases[i] and isinstance(r[i], (int, float)):
                    by_base.setdefault(bases[i], {}).setdefault(RBI_ROWS[name], {})[head[i]] = float(r[i])
        if not by_base:
            problems.append(f"{t['title']}: no figures read")
        for base, figures in by_base.items():
            years = sorted({y for v in figures.values() for y in v})
            out.append({"document": t["title"], "date": None, "base": base, "url": t["url"], "statement": "",
                        "prices": prices, "years": years, "figures": figures})
    return out, problems


# ---- population and per-person figures -------------------------------------------

# Labels as printed, without their bracketed units: "Population (in million)", "Per Capita GDP( ₹)".
NAS_ROWS = {"Population": "population", "Per Capita GDP": "pc_gdp", "Per Capita GNI": "pc_gni",
            "Per Capita NNI": "pc_nni", "Per Capita PFCE": "pc_pfce"}


UNIT = {"population": "million", "pc": "₹"}  # what the bracket after each label must say


def parse_nas(rows: list[tuple]) -> tuple[dict, list[str], list[str]]:
    """Statement rows -> ({"cur"|"con": {row: {year: value}}}, years, problems). Reads the English labels; checks the
    section headings, units and that no row is read twice, so a changed layout is a problem, not a silent misread."""
    problems: list[str] = []
    head = next((r for r in rows if any(isinstance(c, str) and c.strip() == "Item" for c in r)), None)
    if not head:
        return {}, [], ["layout changed (no 'Item' header row)"]
    label = next(i for i, c in enumerate(head) if isinstance(c, str) and c.strip() == "Item")
    cols = {i: c.strip() for i, c in enumerate(head) if isinstance(c, str) and re.fullmatch(r"\d{4}-\d{2}", c.strip())}
    odd = [c for i, c in enumerate(head) if i < label and i not in cols and isinstance(c, str) and re.search(r"\d{4}-", c)]
    if odd:
        problems.append(f"year headings not understood: {odd}")
    figures: dict[str, dict] = {"cur": {}, "con": {}}
    prices = None
    for r in rows:
        name = r[label].strip() if len(r) > label and isinstance(r[label], str) else ""
        low = name.lower()
        if "percentage" in low or "growth" in low:
            prices = None  # growth rates follow; not used
            continue
        if low.startswith("at current prices"):
            prices = "cur"
            continue
        if low.startswith("at constant"):
            prices = "con"
            continue
        base_name = re.sub(r"\s*\(.*$", "", name)
        key = NAS_ROWS.get(base_name)
        if not key or (key != "population" and not prices):
            continue
        unit = re.search(r"\(([^)]*)\)", name)
        want = UNIT["population" if key == "population" else "pc"]
        if not unit or unit[1].strip().lower().replace("in ", "") != want.lower():
            problems.append(f"'{name}': unit is not {want}")
            continue
        vals = {cols[i]: float(r[i]) for i in cols if isinstance(r[i], (int, float))}
        for p_ in (("cur", "con") if key == "population" else (prices,)):
            if key in figures[p_]:
                problems.append(f"'{name}' read twice at {'current' if p_ == 'cur' else 'constant'} prices")
            figures[p_][key] = vals
    for p_, f in figures.items():
        missing = [k for k in NAS_ROWS.values() if k not in f]
        if missing:
            problems.append(f"{', '.join(missing)} not read at {'current' if p_ == 'cur' else 'constant'} prices")
    return figures, sorted(cols.values()), problems


def read_nas(manifest: dict) -> tuple[list[dict], list[str]]:
    """MoSPI's per-capita statement from National Accounts Statistics: one record per price basis, with the
    population (to the thousand) and unrounded per-person figures; no totals (see comparisons)."""
    import openpyxl

    out, problems = [], []
    for n in NAS_STATEMENTS:
        path = path_of(manifest, n["key"])
        if not path:
            problems.append(f"{n['document']}: not added (download it by hand; gdp/README.md)")
            continue
        rows = list(openpyxl.load_workbook(path, data_only=True).active.iter_rows(values_only=True))
        figures, years, found = parse_nas(rows)
        problems += [f"{n['document']}: {p}" for p in found]
        for prices_, f in figures.items():
            out.append({"document": n["document"], "date": n["date"], "base": n["base"], "url": n["url"],
                        "statement": "current prices" if prices_ == "cur" else "constant prices", "prices": prices_,
                        "years": years, "figures": f, "exact_population": True})
    return out, problems

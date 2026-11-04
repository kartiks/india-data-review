"""RBI Handbook of Statistics on Indian States: the state tables this area uses.

The handbook's page lists every table of the latest edition with its Excel file. The pipeline finds the tables in
RBI_STATE_TABLES by their number, checks each title, and keeps the Excel files. When RBI publishes a new edition
(usually in December), the weekly refresh (`--refresh-api`) picks it up; changed files are kept in sources/snapshots/.

Each sheet has a title, an optional sub-title ("(Rural Male)"), a unit ("(₹ Lakh)", "(Per Thousands)"), a header
row starting "State/Union Territory" with the years (on that row or the next), one row per state and often an
"ALL INDIA" row, then footnotes. "-" means not available, "." not applicable; a "*" marks a footnote. Each table's
unit and sub-titles are listed in RBI_STATE_TABLES, and a sheet with any other is reported as a problem (a failure in
the checks).
"""

import re
from typing import NamedTuple

from pipeline_common.numbers import number
from pipeline_common.text import is_fy

from .common import ROOT

HANDBOOK_PAGE = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20States"

class Table(NamedTuple):
    id: str  # our id for the table
    words: str  # words the title must contain
    unit: str  # the unit the sheet must give (spelled as UNIT_SPELLINGS maps it)
    variants: tuple[str, ...] = ("",)  # the sub-titles its sheets may have ("" for none)


UNEMPLOYMENT = "UNEMPLOYMENT RATE"
RBI_STATE_TABLES = {
    8: Table("unemployment_rural", UNEMPLOYMENT, "Per Thousands", ("Rural Male", "Rural Female", "Rural Overall")),
    9: Table("unemployment_urban", UNEMPLOYMENT, "Per Thousands", ("Urban Male", "Urban Female", "Urban Overall")),
    19: Table("nsdp_per_capita_current", "PER CAPITA NET STATE DOMESTIC PRODUCT", "₹"),
    20: Table("nsdp_per_capita_constant", "PER CAPITA NET STATE DOMESTIC PRODUCT", "₹"),
    21: Table("gsdp_current", "GROSS STATE DOMESTIC PRODUCT", "₹ Lakh"),
    22: Table("gsdp_constant", "GROSS STATE DOMESTIC PRODUCT", "₹ Lakh"),
    108: Table("cpi_inflation", "AVERAGE INFLATION (CPI) - GENERAL", "Per cent"),
    112: Table("wage_construction", "CONSTRUCTION WORKERS", "₹"),
    113: Table("wage_agriculture", "GENERAL AGRICULTURAL LABOURERS", "₹"),
    114: Table("wage_horticulture", "HORTICULTURE WORKERS", "₹"),
    115: Table("wage_non_agriculture", "NON-AGRICULTURAL LABOURERS", "₹"),
}
# Other spellings RBI has used for the same units
UNIT_SPELLINGS = {"Rs.": "₹", "Rs. Lakh": "₹ Lakh", "Per Cent": "Per cent", "Per Thousand": "Per Thousands"}
YEAR = re.compile(r"^\d{4}-\d{2}$")


def table_links(page_html: str) -> tuple[str, dict[int, tuple[str, str]]]:
    """(edition, {table number: (title, Excel URL)}) from the handbook page."""
    import html as h

    m = re.search(r"Handbook of Statistics on Indian States,?\s*(\d{4}-\d{2})", page_html)
    edition = m.group(1) if m else ""
    out = {}
    for title, url in re.findall(
            r"<a class='link2' href=PublicationsView\.aspx\?id=\d+>(.*?)</a>.*?href='(https://rbidocs[^']+\.XLSX)'",
            page_html, flags=re.S):
        title = re.sub(r"\s+", " ", h.unescape(title)).strip()
        n = re.match(r"Table ?(\d+)", title)
        if n:
            out[int(n.group(1))] = (title, url)
    return edition, out


def cell(v) -> tuple[float | None, str, str]:
    """(number, as printed, flag): flag is '' , 'not available', 'not applicable' or 'footnote'."""
    if v is None:
        return None, "", "not available"
    if isinstance(v, (int, float)):
        return float(v), str(v), ""
    s = str(v).strip()
    if s in ("-", "–", "NA", "N.A."):
        return None, s, "not available"
    if s == ".":
        return None, s, "not applicable"
    x = number(s, strip="*")
    if x is None:
        return None, s, "unreadable"
    return x, s, "footnote" if "*" in s else ""


def read_table(path, table_no: int, spec: Table) -> tuple[list[dict], list[str]]:
    """Every value of one table, one record each, and any problems. Each sheet's notes under the title (in brackets)
    must be the table's unit and one of its variants: anything else is a problem, since the site looks figures up
    by variant and shows them in that unit."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out, problems = [], []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        b = [str(r[1]).strip() if len(r) > 1 and r[1] is not None else "" for r in rows]
        title = re.sub(r"\s*\((Contd|Concld)\.?\)\s*$", "", re.sub(r"\s+", " ", b[0]), flags=re.I) if b else ""
        head = next((i for i, x in enumerate(b) if x.startswith("State/Union Territory")), None)
        if head is None:
            problems.append(f"Table {table_no} sheet {ws.title}: no 'State/Union Territory' header")
            continue
        notes = [x.strip("()") for x in b[1:head] if x.startswith("(")]
        units = [UNIT_SPELLINGS.get(x, x) for x in notes if UNIT_SPELLINGS.get(x, x) == spec.unit]
        variant = " ".join(x for x in notes if UNIT_SPELLINGS.get(x, x) != spec.unit)
        unit = units[0] if units else ""
        if not units:
            problems.append(f"Table {table_no} sheet {ws.title}: unit ({spec.unit}) not found; notes under the title: {notes}")
        if variant not in spec.variants:
            problems.append(f"Table {table_no} sheet {ws.title}: sub-title {variant!r} is not one of {list(spec.variants)}")
        cols = {j: str(c).strip() for j, c in enumerate(rows[head]) if c is not None and YEAR.match(str(c).strip())}
        start = head + 1
        if not cols:
            cols = {j: str(c).strip() for j, c in enumerate(rows[head + 1]) if c is not None and YEAR.match(str(c).strip())}
            start = head + 2
        # YEAR only looks like a fiscal year; a typo such as '2023-25' would break the year-before lookups later
        for j, year in list(cols.items()):
            if not is_fy(year):
                problems.append(f"Table {table_no} sheet {ws.title}: year {year!r} in the header is not a fiscal year; "
                                "its column is left out")
                del cols[j]
        if not cols:
            problems.append(f"Table {table_no} sheet {ws.title}: no years in the header")
            continue
        for r, name in zip(rows[start:], b[start:]):
            if not name or not any(r[j] is not None for j in cols if j < len(r)):
                continue  # footnotes and blank rows
            state = name.replace("*", "").strip()
            for j, year in cols.items():
                v, printed, flag = cell(r[j] if j < len(r) else None)
                if flag == "unreadable":
                    problems.append(f"Table {table_no} {variant} {state} {year}: value {printed!r} is not a table_no")
                out.append({"table": table_no, "table_id": spec.id, "title": title, "variant": variant, "unit": unit,
                            "state": "All India" if state.upper() == "ALL INDIA" else state, "year": year, "value": v,
                            "value_as_printed": printed, "flag": flag, "sheet": ws.title})
    return out, problems


def read_all(manifest: dict) -> tuple[list[dict], list[str], dict]:
    """Every value of the chosen handbook tables, the reader's problems, and {table number: edition}."""
    out, problems, editions = [], [], {}
    for n, spec in RBI_STATE_TABLES.items():
        e = manifest.get(f"rbi/table{n:03d}")
        if not e or e.get("empty"):
            problems.append(f"RBI table {n} not downloaded")
            continue
        recs, probs = read_table(ROOT / e["file"], n, spec)
        for r in recs:
            r["source"] = f"rbi/table{n:03d}"
        out += recs
        problems += probs
        editions[n] = e.get("edition", "")
    return out, problems, editions

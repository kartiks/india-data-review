"""RBI Handbook of Statistics on Indian States: the state tables this area uses.

The handbook's page lists every table of the latest edition with its Excel file. The pipeline finds the tables in
RBI_STATE_TABLES by their number, checks each title, and keeps the Excel files. When RBI publishes a new edition
(usually in December), the weekly refresh (`--refresh-api`) picks it up; changed files are kept in sources/snapshots/.

Each sheet has a title, an optional sub-title ("(Rural Male)"), a unit ("(₹ Lakh)", "(Per Thousands)"), a header
row starting "State/Union Territory" with the years (on that row or the next), one row per state and often an
"ALL INDIA" row, then footnotes. "-" means not available, "." not applicable; a "*" marks a footnote.
"""

import re

HANDBOOK_PAGE = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20States"

# table number -> (our id, words the title must contain)
RBI_STATE_TABLES = {
    8: ("unemployment_rural", "UNEMPLOYMENT RATE"),
    9: ("unemployment_urban", "UNEMPLOYMENT RATE"),
    19: ("nsdp_per_capita_current", "PER CAPITA NET STATE DOMESTIC PRODUCT"),
    20: ("nsdp_per_capita_constant", "PER CAPITA NET STATE DOMESTIC PRODUCT"),
    21: ("gsdp_current", "GROSS STATE DOMESTIC PRODUCT"),
    22: ("gsdp_constant", "GROSS STATE DOMESTIC PRODUCT"),
    108: ("cpi_inflation", "AVERAGE INFLATION (CPI) - GENERAL"),
    112: ("wage_construction", "CONSTRUCTION WORKERS"),
    113: ("wage_agriculture", "GENERAL AGRICULTURAL LABOURERS"),
    114: ("wage_horticulture", "HORTICULTURE WORKERS"),
    115: ("wage_non_agriculture", "NON-AGRICULTURAL LABOURERS"),
}
UNITS = ("₹", "₹ Lakh", "Per Thousands", "Per cent", "Per Cent", "Rs.", "Rs. Lakh")
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
    flag = "footnote" if "*" in s else ""
    try:
        return float(s.replace("*", "").replace(",", "").strip()), s, flag
    except ValueError:
        return None, s, "unreadable"


def read_table(path, number: int, table_id: str) -> tuple[list[dict], list[str]]:
    """Every value of one table, one record each, and any problems."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out, problems = [], []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        b = [str(r[1]).strip() if len(r) > 1 and r[1] is not None else "" for r in rows]
        title = re.sub(r"\s*\((Contd|Concld)\.?\)\s*$", "", re.sub(r"\s+", " ", b[0]), flags=re.I) if b else ""
        head = next((i for i, x in enumerate(b) if x.startswith("State/Union Territory")), None)
        if head is None:
            problems.append(f"Table {number} sheet {ws.title}: no 'State/Union Territory' header")
            continue
        notes = [x.strip("()") for x in b[1:head] if x.startswith("(")]
        unit = next((x for x in notes if x in UNITS), "")
        variant = " ".join(x for x in notes if x not in UNITS)
        cols = {j: str(c).strip() for j, c in enumerate(rows[head]) if c is not None and YEAR.match(str(c).strip())}
        start = head + 1
        if not cols:
            cols = {j: str(c).strip() for j, c in enumerate(rows[head + 1]) if c is not None and YEAR.match(str(c).strip())}
            start = head + 2
        if not cols:
            problems.append(f"Table {number} sheet {ws.title}: no years in the header")
            continue
        for r, name in zip(rows[start:], b[start:]):
            if not name or not any(r[j] is not None for j in cols if j < len(r)):
                continue  # footnotes and blank rows
            state = name.replace("*", "").strip()
            for j, year in cols.items():
                v, printed, flag = cell(r[j] if j < len(r) else None)
                if flag == "unreadable":
                    problems.append(f"Table {number} {variant} {state} {year}: value {printed!r} is not a number")
                out.append({"table": number, "table_id": table_id, "title": title, "variant": variant, "unit": unit,
                            "state": "All India" if state.upper() == "ALL INDIA" else state, "year": year, "value": v,
                            "value_as_printed": printed, "flag": flag, "sheet": ws.title})
    return out, problems

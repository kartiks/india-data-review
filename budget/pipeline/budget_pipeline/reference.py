"""Independent reference data used to check our figures.

RBI Handbook of Statistics on Indian Economy, tables 86, 87 and 89: the
Reserve Bank's own long-run series of central government finances. It is
compiled separately from our pipeline (partly from the audited Finance
Accounts), so agreement is strong evidence that we read the budget documents
correctly. Only line items with the same definition on both sides are compared.

The tables are saved under sources/reference/rbi/ and recorded in sources/manifest.json, as
"reference/rbi/<name>" (pipeline_common.download has the manifest's layout).

Run: uv run python -m budget_pipeline.reference   (downloads the tables)
"""

import logging
from pathlib import Path

from pipeline_common import download
from pipeline_common import log as pipeline_log
from pipeline_common.download import file_kind, get
from pipeline_common.numbers import number
from pipeline_common.text import is_fy

from .readers import read_xlsx

ROOT = Path(__file__).resolve().parents[2]
REF_DIR = ROOT / "sources" / "reference" / "rbi"
MANIFEST = ROOT / "sources" / "manifest.json"
PUBLISHER = "Reserve Bank of India, Handbook of Statistics on Indian Economy"

log = logging.getLogger(__name__)

RBI_HANDBOOK_PAGE = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy"
RBI_TABLES = {
    "table86_key_deficit_indicators": {
        "title": "Table 86: Key Deficit Indicators of the Central Government",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/86T_HBIE31072026203A23E1F5D24AD7B7E5DF7D7F5E4EBF.XLSX",
        # our field -> column number printed in the table's header row
        "columns": {"fiscal_deficit": 2, "primary_deficit": 4, "revenue_deficit": 6},
    },
    "table87_receipts": {
        "title": "Table 87: Central Government Receipts - Major Components",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/87T_HBIE3107202679618CE76D754BE68DEF2DB893347E32.XLSX",
        "columns": {"tax_revenue_net": 2, "non_tax_revenue": 10, "revenue_receipts": 12},
    },
    "table89_expenditure": {
        "title": "Table 89: Major Heads of Expenditure of the Central Government",
        "url": "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/89T_HBIE31072026AA3C6C3FD76B4236955058A14C0078EC.XLSX",
        "columns": {"revenue_expenditure": 2, "interest_payments": 4, "capital_expenditure": 6, "total_expenditure": 10},
    },
}


def manifest_key(name: str) -> str:
    return f"reference/rbi/{name}"


def fetch() -> None:
    """Download every table again (each is checked before any is saved) and record it in the manifest; a changed
    table's previous copy is kept under sources/snapshots/ (pipeline_common.download.save)."""
    contents = {}
    for name, spec in RBI_TABLES.items():
        content = get(spec["url"])
        if file_kind(content) != "xlsx":  # stop: an error page saved here would break every later build
            raise RuntimeError(f"{name}: {spec['url']} is not an Excel file")
        contents[name] = content
    manifest = download.load_manifest(MANIFEST)
    sources = MANIFEST.parent
    for name, content in contents.items():
        dest = REF_DIR / f"{name}.xlsx"
        download.save(manifest, manifest_key(name), dest, content, RBI_TABLES[name]["url"],
                      {"title": RBI_TABLES[name]["title"], "publisher": PUBLISHER, "index_page": RBI_HANDBOOK_PAGE},
                      root=ROOT, raw=sources, snapshots=sources / "snapshots")
        log.info(f"saved {dest.name}")
    download.write_manifest(MANIFEST, manifest)


def reference_sources(manifest: dict) -> dict[str, dict]:
    """{table name: {"title", "publisher", "index_page", "url", "file", "sha256", "fetched_at"}} from the manifest,
    as fiscal.json lists the reference tables."""
    fields = ("title", "publisher", "index_page", "url", "file", "sha256", "fetched_at")
    return {name: {k: manifest[manifest_key(name)][k] for k in fields} for name in RBI_TABLES}


def _latest_kinds(rows: list[list[str]]) -> dict[str, str]:
    """Read note 1 ('Data for 2025-26 are Revised Estimates and data for 2026-27 are Budget Estimates')."""
    import re

    text = " ".join(" ".join(r) for r in rows)
    kinds = {}
    for year, kind in re.findall(r"(\d{4}-\d{2}) (?:are|is) (Revised|Budget) Estimates", text):
        kinds[year] = "re" if kind == "Revised" else "be"
    return kinds


def load_rbi() -> dict[tuple[str, str, str], dict]:
    """Return {(fiscal_year, field, kind): {"value", "table"}} where kind is actual/re/be."""
    out: dict[tuple[str, str, str], dict] = {}
    for name, spec in RBI_TABLES.items():
        rows = read_xlsx(REF_DIR / f"{name}.xlsx")
        kinds = _latest_kinds(rows)
        # The row of column numbers ("1", "2", ...) tells us where each numbered column sits.
        number_row = next((r for r in rows if r[1:4] == ["1", "2", "3"]), None)
        if number_row is None:
            raise ValueError(f"{name}.xlsx: no row of column numbers (1, 2, 3, ...) under the header; "
                             "the table's layout has changed")
        pos = {int(c): i for i, c in enumerate(number_row) if c.isdigit()}
        if missing := sorted(set(spec["columns"].values()) - pos.keys()):
            raise ValueError(f"{name}.xlsx: column number(s) {missing} not in the row of column numbers; "
                             "the table's layout has changed")
        for r in rows:
            year = r[1]
            if not (len(year) == 7 and year[4] == "-"):
                continue  # not a year row
            if not is_fy(year, short=True):
                raise ValueError(f"{name}.xlsx: year {year!r} is not a fiscal year; the table's layout has changed")
            for field, col in spec["columns"].items():
                value = number(r[pos[col]]) if pos[col] < len(r) else None
                if value is None:
                    continue
                out[(year, field, kinds.get(year, "actual"))] = {"value": value, "table": spec["title"]}
    return out


if __name__ == "__main__":
    import argparse

    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    pipeline_log.setup(__package__)
    fetch()

"""Independent reference data used to check our figures.

RBI Handbook of Statistics on Indian Economy, tables 86, 87 and 89: the
Reserve Bank's own long-run series of central government finances. It is
compiled separately from our pipeline (partly from the audited Finance
Accounts), so agreement is strong evidence that we read the budget documents
correctly. Only line items with the same definition on both sides are compared.

Run: uv run python -m budget_pipeline.reference   (downloads the tables)
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from .readers import read_xlsx

ROOT = Path(__file__).resolve().parents[2]
REF_DIR = ROOT / "sources" / "reference" / "rbi"
REF_MANIFEST = ROOT / "sources" / "reference" / "manifest.json"
HEADERS = {"User-Agent": "india-data-review-budget-pipeline/0.1 (python-requests)"}

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


def fetch() -> None:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    manifest = {}
    for name, spec in RBI_TABLES.items():
        resp = session.get(spec["url"], timeout=60)
        resp.raise_for_status()
        dest = REF_DIR / f"{name}.xlsx"
        dest.write_bytes(resp.content)
        manifest[name] = {
            "title": spec["title"],
            "publisher": "Reserve Bank of India, Handbook of Statistics on Indian Economy",
            "index_page": RBI_HANDBOOK_PAGE,
            "url": spec["url"],
            "file": str(dest.relative_to(ROOT)),
            "sha256": hashlib.sha256(resp.content).hexdigest(),
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        print(f"saved {dest.name}")
    REF_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


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
        number_row = next(r for r in rows if r[1:4] == ["1", "2", "3"])
        pos = {int(c): i for i, c in enumerate(number_row) if c.isdigit()}
        for r in rows:
            year = r[1]
            if not (len(year) == 7 and year[4] == "-" and year[:4].isdigit()):
                continue
            for field, col in spec["columns"].items():
                cell = r[pos[col]] if pos[col] < len(r) else ""
                try:
                    value = float(cell.replace(",", ""))
                except ValueError:
                    continue
                out[(year, field, kinds.get(year, "actual"))] = {"value": value, "table": spec["title"]}
    return out


if __name__ == "__main__":
    fetch()

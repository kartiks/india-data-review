"""Where each official table lives on indiabudget.gov.in, for every budget year.

Document types:
- summary         Budget at a Glance, the headline table (receipts, spending, deficits)
- receipts        Budget at a Glance, "Receipts": taxes by type, states' share, non-tax
- ministries      Expenditure Budget Vol. 1 Statement 2 (to 2016-17) / Expenditure
                  Profile Statement 3A (from 2017-18): total spending of each ministry
- css             Expenditure Profile Statement 4A: Centrally Sponsored Schemes (from 2017-18)
- central_sector  Expenditure Profile Statement 4B: Central Sector Schemes (from 2017-18)
- receipt_budget  Receipt Budget, Annex 7 "Analysis of tax and non-tax revenue receipts"
                  (budgets 2002-03 to 2009-10 only): audited tax actuals by type for
                  2000-01 to 2007-08, which the Budget at a Glance Receipts table lacks

Each budget prints four columns: Actuals (two years back), BE and RE for last
year, and BE for the new year, so one document per budget gives every year's
BE, RE and Actuals, and most figures appear in two budgets (a cross-check).

The site often has the same table as PDF, Excel and HTML. All are downloaded:
the PDF is the printed document laid before Parliament and is the primary
source; the others are compared against it (several have turned out wrong).

Scheme tables start in 2017-18: before that, spending was split into Plan and
Non-plan and schemes only appear as Plan outlays, which are not comparable.

Interim budgets (election years) are skipped: the full budget later that year
replaces their estimates.
"""

from pipeline_common import budget_glance
from pipeline_common.text import fy

FIRST_BUDGET = 2000  # 2000-01
LATEST_BUDGET = budget_glance.LATEST_BUDGET  # set in pipeline_common/budget_glance.py, which the gdp area reads too
FIRST_SCHEME_BUDGET = 2017  # 2017-18, the first budget without the Plan/Non-plan split

# Preferred order when choosing the primary file for a year.
FORMAT_PRIORITY = ["pdf", "xlsx", "xls", "htm"]

DOC_TYPES = ["summary", "receipts", "ministries", "css", "central_sector", "receipt_budget"]
RECEIPT_BUDGET_YEARS = range(2002, 2010)  # budgets 2002-03..2009-10 -> tax actuals 2000-01..2007-08

# Words that must appear in a file for it to count as that table (guards against wrong files).
TITLE_MUST_CONTAIN = {
    "summary": r"budget at a glance",
    "receipts": r"gross tax revenue",
    "ministries": r"ministr",
    "css": r"centrally sponsored",
    "central_sector": r"central sector",
    "receipt_budget": r"analysis of tax",
}


def candidate_urls(start: int, doc: str) -> list[str]:
    """Every URL where this table might be, in any format."""
    site = budget_glance.site(start, LATEST_BUDGET)
    if start <= 2010:
        exts = ("pdf", "xls", "htm")
    elif start <= 2018:
        exts = ("pdf", "xls", "xlsx")
    else:
        exts = ("pdf", "xlsx", "xls")

    if doc == "summary":
        names = [budget_glance.table(start, 1)]
    elif doc == "receipts":
        # Table 2 to 2016-17; from 2017-18 table 2 is "Deficit Statistics" and the receipts are table 5.
        names = [budget_glance.table(start, 2 if start <= 2016 else 5)]
    elif doc == "ministries":
        names = ["eb/stat02"] if start <= 2016 else ["eb/stat3a", "eb/stat3"]
    elif doc == "receipt_budget":
        if start not in RECEIPT_BUDGET_YEARS:
            return []
        names = ["rec/annex7"]
    elif doc in ("css", "central_sector"):
        if start < FIRST_SCHEME_BUDGET:
            return []
        names = ["eb/stat4a"] if doc == "css" else ["eb/stat4b"]
    else:
        raise ValueError(doc)
    urls = [f"{site}/{n}.{e}" for n in names for e in exts]
    if doc == "summary" and start == 2016:
        urls += [f"{site}/bag/bag1.xls"]  # its PDF is bag11, its Excel copy bag1
    return urls


BUDGETS = list(range(FIRST_BUDGET, LATEST_BUDGET + 1))


def expected_documents(start: int) -> list[str]:
    """The document types a budget must have downloaded (those with somewhere to look for them)."""
    return [doc for doc in DOC_TYPES if candidate_urls(start, doc)]


def manifest_key(year: str, doc: str, ext: str) -> str:
    """The key of one budget document's file in one format in sources/manifest.json (pipeline_common.download has
    the manifest's layout): "2016-17/summary/pdf"."""
    return f"{year}/{doc}/{ext}"


def documents(manifest: dict) -> dict[str, dict[str, dict[str, dict]]]:
    """The budget documents in sources/manifest.json, by budget: {budget year: {document type: {format: manifest
    entry}}}, budgets in order, document types in DOC_TYPES' order and formats in FORMAT_PRIORITY's. The reference
    tables (keys under "reference/") are left out."""
    out: dict[str, dict[str, dict[str, dict]]] = {}
    for key, entry in sorted(manifest.items()):
        if key.startswith("reference/"):
            continue
        year, doc, ext = key.split("/")
        out.setdefault(year, {}).setdefault(doc, {})[ext] = entry
    return {year: {doc: {ext: docs[doc][ext] for ext in sorted(docs[doc], key=FORMAT_PRIORITY.index)}
                   for doc in sorted(docs, key=DOC_TYPES.index)}
            for year, docs in out.items()}


def missing_documents(manifest: dict) -> dict[str, list[str]]:
    """{budget year: [document types]} for every budget up to LATEST_BUDGET whose documents are not all in the
    manifest: usually the newest budget, when LATEST_BUDGET is raised before its documents are downloaded."""
    have = documents(manifest)
    out = {}
    for start in BUDGETS:
        year = fy(start)
        if missing := [doc for doc in expected_documents(start) if not have.get(year, {}).get(doc)]:
            out[year] = missing
    return out


def missing_message(missing: dict[str, list[str]]) -> str:
    years = "; ".join(f"{year}: {', '.join(docs)}" for year, docs in missing.items())
    return (f"Budget documents not downloaded ({years}). LATEST_BUDGET is {LATEST_BUDGET} "
            f"({fy(LATEST_BUDGET)}, set in shared/pipeline/pipeline_common/budget_glance.py): run "
            "`uv run python -m budget_pipeline --fetch` once that budget is on indiabudget.gov.in "
            "(budget/README.md, Adding a new budget), or lower LATEST_BUDGET until it is.")

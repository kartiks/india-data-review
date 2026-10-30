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

BASE = "https://www.indiabudget.gov.in"

FIRST_BUDGET = 2000  # 2000-01
LATEST_BUDGET = 2026  # 2026-27
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


def fy(start: int) -> str:
    """2000 -> '2000-01'."""
    return f"{start}-{str(start + 1)[-2:]}"


def _site(start: int) -> str:
    y = fy(start)
    if start <= 2010:
        return f"{BASE}/budget_archive/ub{y}"
    if start <= 2018:
        return f"{BASE}/budget{start}-{start + 1}/ub{y}"
    return (BASE if start == LATEST_BUDGET else f"{BASE}/budget{y}") + "/doc"


def candidate_urls(start: int, doc: str) -> list[str]:
    """Every URL where this table might be, in any format."""
    site = _site(start)
    if start <= 2010:
        exts = ("pdf", "xls", "htm")
    elif start <= 2018:
        exts = ("pdf", "xls", "xlsx")
    else:
        exts = ("pdf", "xlsx", "xls")

    if doc == "summary":
        if start <= 2018:
            names = ["bag/bag11" if start == 2016 else "bag/bag1"]  # 2016-17 names this PDF bag11.pdf
        else:
            names = ["Budget_at_Glance/bag1"]
    elif doc == "receipts":
        if start <= 2016:
            names = ["bag/bag2"]
        elif start <= 2018:
            names = ["bag/bag5"]  # 2017-18 and 2018-19: bag2 is "Deficit Statistics"
        else:
            names = ["Budget_at_Glance/bag5"]
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
        urls += [f"{site}/bag/bag1.xls"]
    return urls


BUDGETS = list(range(FIRST_BUDGET, LATEST_BUDGET + 1))

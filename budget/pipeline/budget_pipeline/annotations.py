"""Known problems in the official source files, each reviewed by hand.

Nothing here changes a number. Entries either (a) let a check pass because
the mismatch is explained (checks.EXCEPTIONS: the report lists each such case
under its reason and counts it as allowed), or (b) attach a note to a
published figure so the website can show it. Every entry says what was found
and how it was checked.
"""

SIX_POINT_ONE = (
    "Budget 2000-01 deducts Rs 1,000 crore of disinvestment proceeds earmarked for redeeming public debt "
    "(item 6.1). The document's own formulas are 'Capital Receipts (5+6-6.1+7)' and "
    "'Fiscal Deficit = (7-6.1)', so the figures are consistent once this item is included."
)
BE_2015_16_RESTATED = (
    "Budget 2016-17 restated the 2015-16 Budget Estimate for grants for capital assets from 1,10,551 to "
    "1,32,472 crore (its footnote: 'Deviation in BE 2015-16 is due to better capture of information'), "
    "but printed the effective revenue deficit as 2,68,000 crore, which matches neither figure "
    "(3,94,472 - 1,32,472 = 2,62,000). PDF and Excel copies agree, so this is in the source. "
    "The Budget Estimate shown on the site comes from Budget 2015-16, which is internally consistent."
)
CAPITAL_RECEIPTS_2015_16 = (
    "Budget 2017-18 prints 2015-16 actual capital receipts as 5,95,748 crore, but its parts "
    "(20,835 + 42,132 + 5,32,791) and its printed total receipts (17,90,783 = 11,95,025 + 5,95,758) "
    "both imply 5,95,758 crore, and the Excel copy of the same table prints 5,95,758. "
    "Shown as printed in the PDF, with this note."
)

# (check, start of the check's message) -> reason. Checks (checks.py): "identity" (accounting rules), "pct"
# (% of GDP) and "cross" (the same figure in two budgets). Where several entries match, the longest wins.
KNOWN_EXCEPTIONS: dict[tuple[str, str], str] = {
    ("identity", "Budget 2000-01, BE 2000-01: capital receipts = loan recoveries + other receipts + borrowings —"):
        SIX_POINT_ONE,
    ("identity", "Budget 2000-01, BE 2000-01: fiscal deficit = borrowings —"): SIX_POINT_ONE,
    ("identity", "Budget 2001-02, BE 2000-01: capital receipts = loan recoveries + other receipts + borrowings —"):
        SIX_POINT_ONE,
    ("identity", "Budget 2001-02, BE 2000-01: fiscal deficit = borrowings —"): SIX_POINT_ONE,
    ("identity", "Budget 2016-17, BE 2015-16: effective revenue deficit = revenue deficit - capital grants —"):
        BE_2015_16_RESTATED,
    ("pct", "Budget 2016-17, BE 2015-16: effective_revenue_deficit printed"): BE_2015_16_RESTATED,
    ("cross", "BE 2015-16 grants_capital_assets:"): BE_2015_16_RESTATED,
    ("cross", "BE 2015-16 effective_revenue_deficit:"): BE_2015_16_RESTATED,
    ("identity",
     "Budget 2017-18, Actual 2015-16: capital receipts = loan recoveries + other receipts + borrowings —"):
        CAPITAL_RECEIPTS_2015_16,
    ("identity", "Budget 2017-18, Actual 2015-16: total receipts = revenue receipts + capital receipts —"):
        CAPITAL_RECEIPTS_2015_16,
}

# Notes attached to published figures: (source budget, fiscal year, kind, field) -> note
SOURCE_NOTES: dict[tuple[str, str, str, str], str] = {
    ("2000-01", "2000-01", "BE", "capital_receipts"): SIX_POINT_ONE,
    ("2000-01", "2000-01", "BE", "fiscal_deficit"): SIX_POINT_ONE,
    ("2016-17", "2015-16", "BE", "grants_capital_assets"): BE_2015_16_RESTATED,
    ("2016-17", "2015-16", "BE", "effective_revenue_deficit"): BE_2015_16_RESTATED,
    ("2017-18", "2015-16", "Actual", "capital_receipts"): CAPITAL_RECEIPTS_2015_16,
}

# Secondary copies (Excel/HTML) that disagree with the official PDF. The PDF is used.
KNOWN_FORMAT_ISSUES: dict[tuple[str, str], str] = {
    ("2004-05", "htm"): (
        "The HTML page differs from the PDF in 21 of 60 values. The PDF's 2004-05 Budget Estimates match "
        "those reprinted in Budget 2005-06, so the HTML page is not used."
    ),
    ("2005-06", "htm"): (
        "The HTML page has 2005-06 column headings but the numbers of Budget 2003-04 (its page title also "
        "says 2002-2003). Not used."
    ),
    ("2023-24", "xls"): (
        "The Excel file has typos absent from the PDF (e.g. 2021-22 non-tax revenue 36,51,132 instead of "
        "3,65,113) and several 2023-24 estimates off by 3,800 crore; the PDF matches the figures reprinted "
        "in Budget 2024-25. Not used."
    ),
    ("2025-26", "xlsx"): (
        "The Excel file differs from the PDF for 2025-26 BE grants for capital assets (4,25,231.56 vs "
        "4,27,192) and two figures derived from it; the PDF matches the figures reprinted in Budget 2026-27."
    ),
}

KNOWN_FORMAT_ISSUES[("2017-18", "xlsx")] = (
    "The Excel copy has 2015-16 actual capital receipts as 5,95,758 (the PDF's 5,95,748 is the typo, see "
    "the note on that figure) and prints the 2016-17 RE fiscal deficit as 3.2% of GDP, where the PDF and "
    "Budget 2018-19 show 3.5%."
)

# Typos in a file's column headings, fixed before reading: (budget, format) -> [(printed, corrected)]
HEADER_FIXES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("2017-18", "xlsx"): [("2016-2016", "2015-2016")],  # the Actuals column is 2015-16, as in the PDF
}


# ----- Differences from the RBI Handbook series (independent reference) ---------

NSSF = (
    "For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and "
    "State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not "
    "investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the "
    "difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the "
    "amounts in RBI's note. Comparing capital spending across years? Treat these three years with care."
)
FINAL_ACCOUNTS = (
    "Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses "
    "the audited Finance Accounts. Small differences (up to 0.1% and Rs 500 crore) are expected for this reason; "
    "larger ones are listed with their own reason."
)
RBI_2004_05_FD = (
    "RBI's 2004-05 fiscal deficit is Rs 592 crore higher (1,25,794 vs 1,25,202 in Budget 2006-07); the "
    "primary deficit differs by the same amount. Consistent with final audited accounts vs provisional actuals."
)

RBI_2000_01 = (
    "Budget 2002-03's 2000-01 actuals have Rs 258 crore more tax revenue and Rs 239 crore less non-tax revenue "
    "than RBI's series (a different split of the same receipts, net Rs 19 crore), and Rs 19 crore more revenue "
    "receipts, revenue expenditure and total expenditure. Every deficit agrees exactly."
)
RBI_2002_03 = (
    "Budget 2004-05's 2002-03 actuals have Rs 914 crore more revenue receipts (Rs 881 crore of it tax) and Rs 915 "
    "crore more revenue expenditure than RBI's series, and the deficits agree (to Rs 1 crore): the same amount is "
    "counted on both sides in one series and on neither in the other. Total expenditure differs by this plus the "
    "NSSF repayment (see that note)."
)
RBI_2005_06 = (
    "Budget 2007-08's 2005-06 actuals have Rs 385 crore more non-tax revenue, revenue receipts, revenue "
    "expenditure and total expenditure than RBI's series, and the deficits agree (to Rs 1 crore): the same amount "
    "is counted on both sides in one series and on neither in the other."
)

# (fiscal year, field, kind, our figure, RBI's figure) -> reason for a difference from the RBI series larger than
# checks.RBI_SHARE_TOL or checks.RBI_CRORE_TOL. The figures are part of the key, so any other difference for the same
# cell (a parser regression, a revised RBI table) fails until a person looks at it. For a year listed with its own
# reason, every field that differs is listed under it.
KNOWN_REFERENCE_DIFFS: dict[tuple[str, str, str, int, int], str] = {
    ("2000-01", "non_tax_revenue", "actual", 55708, 55947): RBI_2000_01,
    ("2000-01", "revenue_expenditure", "actual", 277858, 277839): RBI_2000_01,
    ("2000-01", "revenue_receipts", "actual", 192624, 192605): RBI_2000_01,
    ("2000-01", "tax_revenue_net", "actual", 136916, 136658): RBI_2000_01,
    ("2000-01", "total_expenditure", "actual", 325611, 325592): RBI_2000_01,
    ("2002-03", "capital_expenditure", "actual", 74535, 60769): NSSF,
    ("2002-03", "total_expenditure", "actual", 414162, 399482): NSSF,
    ("2002-03", "non_tax_revenue", "actual", 72323, 72290): RBI_2002_03,
    ("2002-03", "revenue_expenditure", "actual", 339628, 338713): RBI_2002_03,
    ("2002-03", "revenue_receipts", "actual", 231748, 230834): RBI_2002_03,
    ("2002-03", "tax_revenue_net", "actual", 159425, 158544): RBI_2002_03,
    ("2003-04", "capital_expenditure", "actual", 109228, 62918): NSSF,
    ("2003-04", "total_expenditure", "actual", 471368, 424992): NSSF,
    ("2004-05", "capital_expenditure", "actual", 113331, 81248): NSSF,
    ("2004-05", "total_expenditure", "actual", 497682, 465577): NSSF,
    ("2004-05", "fiscal_deficit", "actual", 125202, 125794): RBI_2004_05_FD,
    ("2004-05", "primary_deficit", "actual", -1732, -1140): RBI_2004_05_FD,
    ("2005-06", "non_tax_revenue", "actual", 77198, 76813): RBI_2005_06,
    ("2005-06", "revenue_expenditure", "actual", 439761, 439376): RBI_2005_06,
    ("2005-06", "revenue_receipts", "actual", 347462, 347077): RBI_2005_06,
    ("2005-06", "total_expenditure", "actual", 506123, 505738): RBI_2005_06,
}

# Actuals for year Y come from Budget Y+2.
SOURCE_NOTES.update({
    ("2004-05", "2002-03", "Actual", "capital_expenditure"): NSSF,
    ("2004-05", "2002-03", "Actual", "total_expenditure"): NSSF,
    ("2005-06", "2003-04", "Actual", "capital_expenditure"): NSSF,
    ("2005-06", "2003-04", "Actual", "total_expenditure"): NSSF,
    ("2006-07", "2004-05", "Actual", "capital_expenditure"): NSSF,
    ("2006-07", "2004-05", "Actual", "total_expenditure"): NSSF,
})

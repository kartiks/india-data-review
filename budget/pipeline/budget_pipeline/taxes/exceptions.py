"""Reviewed exceptions: differences the checks allow, each with its reason, and fixes to column headings."""

# (budget, fiscal year, kind, check name) -> reason. Each was checked against the
# source file, its footnotes and the other copy of the table.
KNOWN_EXCEPTIONS: dict[tuple[str, str, str, str], str] = {
    ("cross", "2010-11", "BE", "income_tax"): (
        "Budget 2011-12 restated the 2010-11 Budget Estimate: Budget 2010-11 printed income tax 1,20,566 and "
        "'Other taxes and duties' 8,103; Budget 2011-12 has no 'Other taxes' row and prints income tax 1,28,066 "
        "(+7,500) and wealth tax 603 (= 8,103 - 7,500). Gross tax is 7,46,651 in both, so this is a "
        "reclassification, not a change in the estimate."
    ),
}
# (budget, format) -> reason for a secondary copy that disagrees with the primary.
KNOWN_FORMAT_ISSUES: dict[tuple[str, str], str] = {
    ("2004-05", "htm"): (
        "The HTML page's 2004-05 Budget Estimates differ from the PDF in 13 values (e.g. corporation tax "
        "79,546 vs 88,436). The PDF's figures are the ones Budget 2005-06 reprints as BE 2004-05, so the "
        "HTML page is not used (same problem as its headline-table page)."
    ),
    ("2005-06", "htm"): (
        "The HTML page carries the numbers of Budget 2003-04 under 2005-06 headings (e.g. 2005-06 BE "
        "corporation tax 51,499, which is BE 2003-04). Not used (same problem as its headline-table page)."
    ),
    ("2023-24", "xls"): (
        "The Excel copy prints RE 2022-23 states' share as 9,48,406, which already includes the prior-year "
        "adjustment of 32,607 that it also lists separately, so its own net tax does not add up "
        "(30,43,067 - 8,000 - 9,48,406 - 32,607 = 20,54,054, printed 20,86,662). The PDF prints 9,15,798 "
        "+ 32,607 = 9,48,405, which reconciles to the same net tax and to the headline table. PDF used."
    ),
    ("2025-26", "xlsx"): (
        "The Excel copy is an earlier classification: no 'Other Taxes' row (its 5,000 crore is inside union "
        "excise: 3,24,000 vs 3,19,000 for BE 2024-25, which Budget 2024-25 prints as 3,19,000), wealth tax "
        "without commodity transaction tax (7.43 vs 422), RE 2024-25 states' share with the 12,764 "
        "prior-year adjustment folded in, and a 2023-24 actual gross tax that is 415 crore more than its "
        "parts. The PDF adds up exactly and is used."
    ),
}
KNOWN_FORMAT_ISSUES[("2017-18", "xlsx")] = (
    "The Excel copy shows wealth tax as 0 where the PDF prints '...' (nil; wealth tax was abolished from "
    "2015-16) for BE/RE 2016-17 and BE 2017-18. All other values agree. Its header also mislabels the "
    "Actuals column '2016-2016' (fixed via HEADER_FIXES)."
)

# Typos in a copy's column headings, fixed before reading: (budget, format) -> [(printed, corrected)]
HEADER_FIXES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("2017-18", "xlsx"): [("2016-2016", "2015-2016")],  # Actuals column is 2015-16, as in the PDF
}

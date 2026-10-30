# Data validation report

Headline figures, taxes, ministries and schemes. Every allowed exception lists its reason.

**Result: PASSED** (117270 checks, 0 failures)

## ✅ Accounting rules hold in every source column
1066 checks, 0 failures.

- Allowed: Budget 2000-01, BE 2000-01: capital receipts = loan recoveries + other receipts + borrowings — printed 134,814, components give 135,814 (off by -1,000). Reason: Budget 2000-01 deducts Rs 1,000 crore of disinvestment proceeds earmarked for redeeming public debt (item 6.1). The document's own formulas are 'Capital Receipts (5+6-6.1+7)' and 'Fiscal Deficit = (7-6.1)', so the figures are consistent once this item is included.
- Allowed: Budget 2000-01, BE 2000-01: fiscal deficit = borrowings — printed 111,275, components give 112,275 (off by -1,000). Reason: Budget 2000-01 deducts Rs 1,000 crore of disinvestment proceeds earmarked for redeeming public debt (item 6.1). The document's own formulas are 'Capital Receipts (5+6-6.1+7)' and 'Fiscal Deficit = (7-6.1)', so the figures are consistent once this item is included.
- Allowed: Budget 2001-02, BE 2000-01: capital receipts = loan recoveries + other receipts + borrowings — printed 134,814, components give 135,814 (off by -1,000). Reason: Budget 2000-01 deducts Rs 1,000 crore of disinvestment proceeds earmarked for redeeming public debt (item 6.1). The document's own formulas are 'Capital Receipts (5+6-6.1+7)' and 'Fiscal Deficit = (7-6.1)', so the figures are consistent once this item is included.
- Allowed: Budget 2001-02, BE 2000-01: fiscal deficit = borrowings — printed 111,275, components give 112,275 (off by -1,000). Reason: Budget 2000-01 deducts Rs 1,000 crore of disinvestment proceeds earmarked for redeeming public debt (item 6.1). The document's own formulas are 'Capital Receipts (5+6-6.1+7)' and 'Fiscal Deficit = (7-6.1)', so the figures are consistent once this item is included.
- Allowed: Budget 2016-17, BE 2015-16: effective revenue deficit = revenue deficit - capital grants — printed 268,000, components give 262,000 (off by 6,000). Reason: Budget 2016-17 restated the 2015-16 Budget Estimate for grants for capital assets from 1,10,551 to 1,32,472 crore (its footnote: 'Deviation in BE 2015-16 is due to better capture of information'), but printed the effective revenue deficit as 2,68,000 crore, which matches neither figure (3,94,472 - 1,32,472 = 2,62,000). PDF and Excel copies agree, so this is in the source. The Budget Estimate shown on the site comes from Budget 2015-16, which is internally consistent.
- Allowed: Budget 2017-18, Actual 2015-16: capital receipts = loan recoveries + other receipts + borrowings — printed 595,748, components give 595,758 (off by -10). Reason: Budget 2017-18 prints 2015-16 actual capital receipts as 5,95,748 crore, but its parts (20,835 + 42,132 + 5,32,791) and its printed total receipts (17,90,783 = 11,95,025 + 5,95,758) both imply 5,95,758 crore, and the Excel copy of the same table prints 5,95,758. Shown as printed in the PDF, with this note.
- Allowed: Budget 2017-18, Actual 2015-16: total receipts = revenue receipts + capital receipts — printed 1,790,783, components give 1,790,773 (off by 10). Reason: Budget 2017-18 prints 2015-16 actual capital receipts as 5,95,748 crore, but its parts (20,835 + 42,132 + 5,32,791) and its printed total receipts (17,90,783 = 11,95,025 + 5,95,758) both imply 5,95,758 crore, and the Excel copy of the same table prints 5,95,758. Shown as printed in the PDF, with this note.

## ✅ Same figure agrees across documents (BE restated in the next budget)
423 checks, 0 failures.

- Restated: BE 2001-02 capital_expenditure: 64,657 in budget 2001-02 vs 64,656 in budget 2002-03 (-1, 0.0%)
- Restated: BE 2013-14 effective_revenue_deficit: 205,182 in budget 2013-14 vs 205,205 in budget 2014-15 (+23, 0.0%)
- Restated: BE 2013-14 grants_capital_assets: 174,656 in budget 2013-14 vs 174,633 in budget 2014-15 (-23, 0.0%)
- Restated: BE 2015-16 effective_revenue_deficit: 283,921 in budget 2015-16 vs 268,000 in budget 2016-17 (-15,921, 5.6%). Explained: Budget 2016-17 restated the 2015-16 Budget Estimate for grants for capital assets from 1,10,551 to 1,32,472 crore (its footnote: 'Deviation in BE 2015-16 is due to better capture of information'), but printed the effective revenue deficit as 2,68,000 crore, which matches neither figure (3,94,472 - 1,32,472 = 2,62,000). PDF and Excel copies agree, so this is in the source. The Budget Estimate shown on the site comes from Budget 2015-16, which is internally consistent.
- Restated: BE 2015-16 grants_capital_assets: 110,551 in budget 2015-16 vs 132,472 in budget 2016-17 (+21,921, 19.8%). Explained: Budget 2016-17 restated the 2015-16 Budget Estimate for grants for capital assets from 1,10,551 to 1,32,472 crore (its footnote: 'Deviation in BE 2015-16 is due to better capture of information'), but printed the effective revenue deficit as 2,68,000 crore, which matches neither figure (3,94,472 - 1,32,472 = 2,62,000). PDF and Excel copies agree, so this is in the source. The Budget Estimate shown on the site comes from Budget 2015-16, which is internally consistent.
- Restated: BE 2017-18 borrowings: 546,532 in budget 2017-18 vs 546,531 in budget 2018-19 (-1, 0.0%)
- Restated: BE 2017-18 fiscal_deficit: 546,532 in budget 2017-18 vs 546,531 in budget 2018-19 (-1, 0.0%)
- Restated: BE 2017-18 primary_deficit: 23,454 in budget 2017-18 vs 23,453 in budget 2018-19 (-1, 0.0%)
- Restated: BE 2017-18 recoveries_of_loans: 11,932 in budget 2017-18 vs 11,933 in budget 2018-19 (+1, 0.0%)

## ✅ % of GDP figures agree with the amounts
376 checks, 0 failures.


## ✅ Other copies of the same table (Excel/HTML) agree with the primary file
16 checks, 0 failures.

- Budget 2004-05: HTM differs from PDF in 21 values (known): The HTML page differs from the PDF in 21 of 60 values. The PDF's 2004-05 Budget Estimates match those reprinted in Budget 2005-06, so the HTML page is not used.
- Budget 2005-06: HTM differs from PDF in 60 values (known): The HTML page has 2005-06 column headings but the numbers of Budget 2003-04 (its page title also says 2002-2003). Not used.
- Budget 2006-07: HTM copy could not be read (2006-07: could not find the 'Revenue Receipts' row).
- Budget 2007-08: HTM copy could not be read (2007-08: could not find the 'Revenue Receipts' row).
- Budget 2011-12: PDF and XLS agree on all 68 values.
- Budget 2012-13: PDF and XLS agree on all 68 values.
- Budget 2013-14: PDF and XLS agree on all 68 values.
- Budget 2014-15: PDF and XLS agree on all 68 values.
- Budget 2015-16: PDF and XLS agree on all 68 values.
- Budget 2016-17: PDF and XLS agree on all 68 values.
- Budget 2017-18: XLSX differs from PDF in 2 values (known): The Excel copy has 2015-16 actual capital receipts as 5,95,758 (the PDF's 5,95,748 is the typo, see the note on that figure) and prints the 2016-17 RE fiscal deficit as 3.2% of GDP, where the PDF and Budget 2018-19 show 3.5%.
- Budget 2018-19: PDF and XLSX agree on all 68 values.
- Budget 2019-20: PDF and XLSX agree on all 68 values.
- Budget 2020-21: PDF and XLSX agree on all 68 values.
- Budget 2021-22: PDF and XLS agree on all 68 values.
- Budget 2022-23: PDF and XLS agree on all 72 values.
- Budget 2023-24: XLS differs from PDF in 15 values (known): The Excel file has typos absent from the PDF (e.g. 2021-22 non-tax revenue 36,51,132 instead of 3,65,113) and several 2023-24 estimates off by 3,800 crore; the PDF matches the figures reprinted in Budget 2024-25. Not used.
- Budget 2025-26: XLSX differs from PDF in 3 values (known): The Excel file differs from the PDF for 2025-26 BE grants for capital assets (4,25,231.56 vs 4,27,192) and two figures derived from it; the PDF matches the figures reprinted in Budget 2026-27.

## ✅ Every year has the figures it should
1092 checks, 0 failures.

- Not yet published: RE for 2026-27 (Budget 2027-28), Actuals for 2025-26 and 2026-27.

## ✅ Matches the RBI Handbook of Statistics (independent series)
270 checks, 0 failures.

- 236 of 270 figures match the RBI series exactly (within Rs 5 crore).
- Actual 2000-01 non_tax_revenue: ours 55,708 vs RBI 55,947 (-239, 0.43%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2000-01 revenue_expenditure: ours 277,858 vs RBI 277,839 (+19, 0.01%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2000-01 revenue_receipts: ours 192,624 vs RBI 192,605 (+19, 0.01%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2000-01 tax_revenue_net: ours 136,916 vs RBI 136,658 (+258, 0.19%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2000-01 total_expenditure: ours 325,611 vs RBI 325,592 (+19, 0.01%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2001-02 non_tax_revenue: ours 67,787 vs RBI 67,774 (+13, 0.02%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2001-02 revenue_expenditure: ours 301,611 vs RBI 301,468 (+143, 0.05%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2001-02 revenue_receipts: ours 201,449 vs RBI 201,306 (+143, 0.07%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2001-02 tax_revenue_net: ours 133,662 vs RBI 133,532 (+130, 0.10%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2001-02 total_expenditure: ours 362,453 vs RBI 362,310 (+143, 0.04%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2002-03 capital_expenditure: ours 74,535 vs RBI 60,769 (+13,766, 22.65%). Explained: For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the amounts in RBI's note. Comparing capital spending across years? Treat these three years with care.
- Actual 2002-03 non_tax_revenue: ours 72,323 vs RBI 72,290 (+33, 0.05%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2002-03 revenue_expenditure: ours 339,628 vs RBI 338,713 (+915, 0.27%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2002-03 revenue_receipts: ours 231,748 vs RBI 230,834 (+914, 0.40%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2002-03 tax_revenue_net: ours 159,425 vs RBI 158,544 (+881, 0.56%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2002-03 total_expenditure: ours 414,162 vs RBI 399,482 (+14,680, 3.67%). Explained: For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the amounts in RBI's note. Comparing capital spending across years? Treat these three years with care.
- Actual 2003-04 capital_expenditure: ours 109,228 vs RBI 62,918 (+46,310, 73.60%). Explained: For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the amounts in RBI's note. Comparing capital spending across years? Treat these three years with care.
- Actual 2003-04 non_tax_revenue: ours 76,896 vs RBI 76,831 (+65, 0.08%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2003-04 revenue_expenditure: ours 362,140 vs RBI 362,074 (+66, 0.02%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2003-04 revenue_receipts: ours 263,878 vs RBI 263,813 (+65, 0.02%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2003-04 total_expenditure: ours 471,368 vs RBI 424,992 (+46,376, 10.91%). Explained: For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the amounts in RBI's note. Comparing capital spending across years? Treat these three years with care.
- Actual 2004-05 capital_expenditure: ours 113,331 vs RBI 81,248 (+32,083, 39.49%). Explained: For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the amounts in RBI's note. Comparing capital spending across years? Treat these three years with care.
- Actual 2004-05 fiscal_deficit: ours 125,202 vs RBI 125,794 (-592, 0.47%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2004-05 non_tax_revenue: ours 81,215 vs RBI 81,193 (+22, 0.03%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2004-05 primary_deficit: ours -1,732 vs RBI -1,140 (-592, 51.93%). Explained: RBI's 2004-05 fiscal deficit is Rs 592 crore higher (1,25,794 vs 1,25,202 in Budget 2006-07); the primary deficit differs by the same amount. Consistent with final audited accounts vs provisional actuals.
- Actual 2004-05 revenue_expenditure: ours 384,351 vs RBI 384,329 (+22, 0.01%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2004-05 revenue_receipts: ours 306,013 vs RBI 305,991 (+22, 0.01%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2004-05 total_expenditure: ours 497,682 vs RBI 465,577 (+32,105, 6.90%). Explained: For 2002-03 to 2004-05 the Budget at a Glance counts repayments to the National Small Savings Fund and State Debt Swap Scheme transactions inside capital expenditure. These are debt transactions, not investment, and the RBI Handbook series (Table 89, note 2) treats them differently: for 2002-03 the difference is exactly the Rs 13,766 crore NSSF repayment; for 2003-04 and 2004-05 it is close to the amounts in RBI's note. Comparing capital spending across years? Treat these three years with care.
- Actual 2005-06 non_tax_revenue: ours 77,198 vs RBI 76,813 (+385, 0.50%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2005-06 revenue_expenditure: ours 439,761 vs RBI 439,376 (+385, 0.09%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2005-06 revenue_receipts: ours 347,462 vs RBI 347,077 (+385, 0.11%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2005-06 total_expenditure: ours 506,123 vs RBI 505,738 (+385, 0.08%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2014-15 non_tax_revenue: ours 197,857 vs RBI 197,766 (+91, 0.05%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.
- Actual 2014-15 revenue_receipts: ours 1,101,472 vs RBI 1,101,381 (+91, 0.01%). Small difference: Budget documents print actuals about two years later, sometimes still provisional; RBI's series uses the audited Finance Accounts. Differences under 1% are expected for this reason.

## ✅ Large year-on-year changes (for review, not failures)
0 checks, 0 failures.

- revenue_receipts: 2009-10 → 2010-11 changed +38% (572,811 → 788,471)
- capital_expenditure: 2002-03 → 2003-04 changed +47% (74,535 → 109,228)
- capital_expenditure: 2004-05 → 2005-06 changed -41% (113,331 → 66,362)
- capital_expenditure: 2006-07 → 2007-08 changed +72% (68,778 → 118,238)
- capital_expenditure: 2009-10 → 2010-11 changed +39% (112,678 → 156,605)
- capital_expenditure: 2020-21 → 2021-22 changed +39% (426,317 → 592,874)
- fiscal_deficit: 2007-08 → 2008-09 changed +166% (126,912 → 336,992)
- fiscal_deficit: 2010-11 → 2011-12 changed +38% (373,591 → 515,990)
- fiscal_deficit: 2018-19 → 2019-20 changed +44% (649,418 → 933,651)
- fiscal_deficit: 2019-20 → 2020-21 changed +95% (933,651 → 1,818,291)

## ✅ Taxes: totals equal their printed parts
434 checks, 0 failures.


## ✅ Taxes: net tax, non-tax and revenue receipts match the headline table
297 checks, 0 failures.


## ✅ Taxes: same figure agrees across budgets
480 checks, 0 failures.

- Restated: BE 2000-01 other_taxes: 830 in budget 2000-01 vs 1,305 in budget 2001-02 (+475, 57.2%)
- BE 2010-11 income_tax: 120,566 in budget 2010-11 vs 128,066 in budget 2011-12 (+7,500, 6.2%). Explained: Budget 2011-12 restated the 2010-11 Budget Estimate: Budget 2010-11 printed income tax 1,20,566 and 'Other taxes and duties' 8,103; Budget 2011-12 has no 'Other taxes' row and prints income tax 1,28,066 (+7,500) and wealth tax 603 (= 8,103 - 7,500). Gross tax is 7,46,651 in both, so this is a reclassification, not a change in the estimate.
- Restated: BE 2025-26 other_taxes: 5,000 in budget 2025-26 vs 5,100 in budget 2026-27 (+100, 2.0%)

## ✅ Taxes: other copies (Excel/HTML) agree with the primary file
15 checks, 0 failures.

- Budget 2004-05: HTM differs in 13 values (known): The HTML page's 2004-05 Budget Estimates differ from the PDF in 13 values (e.g. corporation tax 79,546 vs 88,436). The PDF's figures are the ones Budget 2005-06 reprints as BE 2004-05, so the HTML page is not used (same problem as its headline-table page).
- Budget 2005-06: HTM differs in 52 values (known): The HTML page carries the numbers of Budget 2003-04 under 2005-06 headings (e.g. 2005-06 BE corporation tax 51,499, which is BE 2003-04). Not used (same problem as its headline-table page).
- Budget 2006-07: HTM copy could not be read (2006-07: gross_tax_revenue not found).
- Budget 2007-08: HTM copy could not be read (2007-08: gross_tax_revenue not found).
- Budget 2011-12: PDF and XLS agree on all 72 values.
- Budget 2012-13: PDF and XLS agree on all 72 values.
- Budget 2013-14: PDF and XLS agree on all 72 values.
- Budget 2014-15: PDF and XLS agree on all 72 values.
- Budget 2015-16: PDF and XLS agree on all 72 values.
- Budget 2016-17: PDF and XLS agree on all 72 values.
- Budget 2017-18: XLSX differs in 3 values (known): The Excel copy shows wealth tax as 0 where the PDF prints '...' (nil; wealth tax was abolished from 2015-16) for BE/RE 2016-17 and BE 2017-18. All other values agree. Its header also mislabels the Actuals column '2016-2016' (fixed via HEADER_FIXES).
- Budget 2019-20: PDF and XLSX agree on all 88 values.
- Budget 2020-21: PDF and XLSX agree on all 88 values.
- Budget 2021-22: PDF and XLS agree on all 88 values.
- Budget 2022-23: PDF and XLS agree on all 88 values.
- Budget 2023-24: XLS differs in 1 values (known): The Excel copy prints RE 2022-23 states' share as 9,48,406, which already includes the prior-year adjustment of 32,607 that it also lists separately, so its own net tax does not add up (30,43,067 - 8,000 - 9,48,406 - 32,607 = 20,54,054, printed 20,86,662). The PDF prints 9,15,798 + 32,607 = 9,48,405, which reconciles to the same net tax and to the headline table. PDF used.
- Budget 2025-26: XLSX differs in 13 values (known): The Excel copy is an earlier classification: no 'Other Taxes' row (its 5,000 crore is inside union excise: 3,24,000 vs 3,19,000 for BE 2024-25, which Budget 2024-25 prints as 3,19,000), wealth tax without commodity transaction tax (7.43 vs 422), RE 2024-25 states' share with the 12,764 prior-year adjustment folded in, and a 2023-24 actual gross tax that is 415 crore more than its parts. The PDF adds up exactly and is used.

## ✅ Taxes (Receipt Budget actuals 2000-01..2007-08): totals equal their printed parts
72 checks, 0 failures.


## ✅ Taxes (Receipt Budget actuals): net tax, non-tax, revenue receipts match the headline table's Actuals
24 checks, 0 failures.


## ✅ Taxes (Receipt Budget): its RE/BE columns match the Budget at a Glance Receipts table
192 checks, 0 failures.


## ✅ Taxes (Receipt Budget): actuals present for 2000-01..2007-08
64 checks, 0 failures.


## ✅ Ministries: plan + non_plan = total on every line
15803 checks, 0 failures.


## ✅ Ministries: revenue + capital = total on every line
14689 checks, 0 failures.

- Allowed: Budget 2023-24: Actual 2021-22 'Grand Total' / central_sector_schemes: 74188.47 + 468061.12 != 1209949.59. Reason: Budget 2023-24's grand-total block prints Central Sector Schemes revenue for 2021-22 as 74188.47; the demands add to 741,888.47 and its own total minus capital (12,09,949.59 - 4,68,061.12) is 741,888.47 (confirmed on the page image). A dropped digit in the source.
- Allowed: Budget 2023-24: RE 2022-23 'Grand Total' / other_transfers: 192262.62 + 86911.42 != 279138.04. Reason: Budget 2023-24's grand-total block prints Other Transfers revenue for RE 2022-23 as 192262.62; the demands add to 1,92,226.62 and total minus capital (2,79,138.04 - 86,911.42) is 1,92,226.62. Two digits transposed in the source.

## ✅ Ministries: Revenue line + Capital line = department line
18039 checks, 0 failures.

- Allowed: Budget 2011-12: RE 2010-11 'III. UNION TERRITORIES (A + B)' non_plan: revenue + capital = 7584.89, printed 3925.1. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2011-12: RE 2010-11 'III. UNION TERRITORIES (A + B)' total: revenue + capital = 11018.40, printed 7358.61. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2012-13: RE 2011-12 'III. UNION TERRITORIES (A + B)' non_plan: revenue + capital = 7976.54, printed 4242.04. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2012-13: RE 2011-12 'III. UNION TERRITORIES (A + B)' total: revenue + capital = 12070.11, printed 8335.61. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2013-14: RE 2012-13 'III. UNION TERRITORIES (A + B)' non_plan: revenue + capital = 8726.93, printed 4580.1. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2013-14: RE 2012-13 'III. UNION TERRITORIES (A + B)' total: revenue + capital = 13582.23, printed 9435.4. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2014-15: RE 2013-14 'III. UNION TERRITORIES (A + B)' non_plan: revenue + capital = 9379.40, printed 4937.03. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2014-15: RE 2013-14 'III. UNION TERRITORIES (A + B)' total: revenue + capital = 14846.22, printed 10403.85. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2015-16: RE 2014-15 'III. UNION TERRITORIES (A + B)' non_plan: revenue + capital = 9849.51, printed 5224.24. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2015-16: RE 2014-15 'III. UNION TERRITORIES (A + B)' total: revenue + capital = 16293.66, printed 11668.39. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2016-17: RE 2015-16 'III. UNION TERRITORIES (A + B)' non_plan: revenue + capital = 10900.71, printed 5791.66. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.
- Allowed: Budget 2016-17: RE 2015-16 'III. UNION TERRITORIES (A + B)' total: revenue + capital = 18421.76, printed 13312.71. Reason: The Union Territories subtotal's Capital line prints a wrong Non-Plan figure in the Revised Estimates column (e.g. Budget 2012-13: 3,679.04 where the subtotal and its Revenue line imply -55.46; confirmed on the page image). The same cell is wrong in every statement from 2011-12 to 2016-17. Only that subtotal's revenue/capital split is affected; each UT's own lines add up.

## ✅ Ministries: sub-lines add up to the demand
12132 checks, 0 failures.


## ✅ Ministries: 'Total:' line repeats the demand total
328 checks, 0 failures.


## ✅ Ministries: departments add up to the grand total
291 checks, 0 failures.

- Allowed: Budget 2000-01: Actual 1998-99 plan: lines add to 66871.22, grand total 66817.77. Reason: Budget 2000-01's 1998-99 Actuals: the departments' Plan figures add to 53.45 crore more than the printed Central Ministries total (37,107.43, confirmed on the page image), while the printed totals agree with each other and with the Budget at a Glance. Revenue/capital split of the grand total also differs from the Budget at a Glance by 932.79 crore (totals agree). 1998-99 is before the published range (2000-01 onwards).
- Allowed: Budget 2000-01: Actual 1998-99 total: lines add to 279418.92, grand total 279365.3. Reason: Budget 2000-01's 1998-99 Actuals: the departments' Plan figures add to 53.45 crore more than the printed Central Ministries total (37,107.43, confirmed on the page image), while the printed totals agree with each other and with the Budget at a Glance. Revenue/capital split of the grand total also differs from the Budget at a Glance by 932.79 crore (totals agree). 1998-99 is before the published range (2000-01 onwards).

## ✅ Ministries: each spending category adds up across demands
648 checks, 0 failures.

- Allowed: Budget 2023-24: Actual 2021-22 central_sector_schemes revenue: demands add to 741888.47, grand total line 74188.47. Reason: Budget 2023-24's grand-total block prints Central Sector Schemes revenue for 2021-22 as 74188.47; the demands add to 741,888.47 and its own total minus capital (12,09,949.59 - 4,68,061.12) is 741,888.47 (confirmed on the page image). A dropped digit in the source.
- Allowed: Budget 2023-24: RE 2022-23 other_transfers revenue: demands add to 192226.62, grand total line 192262.62. Reason: Budget 2023-24's grand-total block prints Other Transfers revenue for RE 2022-23 as 192262.62; the demands add to 1,92,226.62 and total minus capital (2,79,138.04 - 86,911.42) is 1,92,226.62. Two digits transposed in the source.

## ✅ Ministries: grand total = Budget at a Glance
291 checks, 0 failures.

- Allowed: Budget 2000-01: Actual 1998-99 revenue: ministries grand total 216,486.21 vs Budget at a Glance revenue_expenditure 217,419. Reason: Budget 2000-01's 1998-99 Actuals: the departments' Plan figures add to 53.45 crore more than the printed Central Ministries total (37,107.43, confirmed on the page image), while the printed totals agree with each other and with the Budget at a Glance. Revenue/capital split of the grand total also differs from the Budget at a Glance by 932.79 crore (totals agree). 1998-99 is before the published range (2000-01 onwards).
- Allowed: Budget 2000-01: Actual 1998-99 capital: ministries grand total 62,879.09 vs Budget at a Glance capital_expenditure 61,947. Reason: Budget 2000-01's 1998-99 Actuals: the departments' Plan figures add to 53.45 crore more than the printed Central Ministries total (37,107.43, confirmed on the page image), while the printed totals agree with each other and with the Budget at a Glance. Revenue/capital split of the grand total also differs from the Budget at a Glance by 932.79 crore (totals agree). 1998-99 is before the published range (2000-01 onwards).

## ✅ Ministries: same line agrees in both budgets that print it
1712 checks, 0 failures.

- Restated: BE 2010-11 state_plans:bodoland_package: 50.0 in Budget 2010-11 vs None in Budget 2011-12 (moved within doner: the ministry total is the same in both)
- Restated: BE 2010-11 state_plans:north_eastern_region: 700.0 in Budget 2010-11 vs 750.0 in Budget 2011-12 (moved within doner: the ministry total is the same in both)
- Restated: BE 2015-16 aids_control: 857.0 in Budget 2015-16 vs None in Budget 2016-17 (moved within health_family_welfare: the ministry total is the same in both)
- Restated: BE 2015-16 defence_civil: 63352.6 in Budget 2015-16 vs 91644.55 in Budget 2016-17 (moved within defence: the ministry total is the same in both)
- Restated: BE 2015-16 defence_services: 246727.0 in Budget 2015-16 vs 218435.05 in Budget 2016-17 (moved within defence: the ministry total is the same in both)
- Restated: BE 2015-16 economic_affairs: 17239.56 in Budget 2015-16 vs 17064.56 in Budget 2016-17 (moved within finance: the ministry total is the same in both)
- Restated: BE 2015-16 economic_affairs_centralised: 565159.57 in Budget 2015-16 vs 565334.57 in Budget 2016-17 (moved within finance: the ministry total is the same in both)
- Restated: BE 2015-16 external_affairs: 14966.83 in Budget 2015-16 vs 15085.0 in Budget 2016-17 (moved within external_affairs: the ministry total is the same in both)
- Restated: BE 2015-16 health_family_welfare: 11358.0 in Budget 2015-16 vs 12215.0 in Budget 2016-17 (moved within health_family_welfare: the ministry total is the same in both)
- Restated: BE 2015-16 overseas_indian_affairs: 118.17 in Budget 2015-16 vs None in Budget 2016-17 (moved within external_affairs: the ministry total is the same in both)
- Restated: BE 2015-16 state_plans:aids_control: 500.0 in Budget 2015-16 vs None in Budget 2016-17 (moved within health_family_welfare: the ministry total is the same in both)
- Restated: BE 2015-16 state_plans:health_family_welfare: 18000.0 in Budget 2015-16 vs 18500.0 in Budget 2016-17 (moved within health_family_welfare: the ministry total is the same in both)
- Restated: BE 2016-17 agriculture: 23228.83 in Budget 2016-17 vs 35983.69 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 animal_husbandry_dairying: 1339.51 in Budget 2016-17 vs 1881.51 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ayush: 926.2 in Budget 2016-17 vs 1326.2 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 cabinet: None in Budget 2016-17 vs 419.64 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 central_vigilance_commission: None in Budget 2016-17 vs 27.68 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 defence_capital_outlay: None in Budget 2016-17 vs 78586.68 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 defence_civil: 118465.84 in Budget 2016-17 vs 36133.18 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 defence_pensions: None in Budget 2016-17 vs 82332.66 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 defence_services: 222456.14 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 defence_services_revenue: None in Budget 2016-17 vs 143869.46 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 direct_taxes: None in Budget 2016-17 vs 5387.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 doner: 830.01 in Budget 2016-17 vs 2430.01 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 drinking_water_sanitation: 1471.2 in Budget 2016-17 vs 14009.7 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 economic_affairs_centralised: 603316.31 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 environment: 1393.32 in Budget 2016-17 vs 2250.34 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 expenditure: 34961.38 in Budget 2016-17 vs 226.65 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 health_family_welfare: 16371.08 in Budget 2016-17 vs 37061.55 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 higher_education: 27585.0 in Budget 2016-17 vs 28840.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 home_affairs: 73406.37 in Budget 2016-17 vs 4630.9 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 hupa: 588.0 in Budget 2016-17 vs 5411.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 indian_audit_accounts: None in Budget 2016-17 vs 3664.73 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 indirect_taxes: None in Budget 2016-17 vs 5340.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 interest_payments: None in Budget 2016-17 vs 492669.95 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 labour_employment: 6131.35 in Budget 2016-17 vs 6242.6 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 land_resources: 230.51 in Budget 2016-17 vs 1709.36 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 law_justice: 4564.99 in Budget 2016-17 vs 5100.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 lok_sabha: None in Budget 2016-17 vs 624.29 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 minority_affairs: 2824.0 in Budget 2016-17 vs 3827.25 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 pensions: None in Budget 2016-17 vs 31070.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 personnel: 1477.68 in Budget 2016-17 vs 1450.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 police: None in Budget 2016-17 vs 70184.58 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 president_parliament_upsc_vp: 1275.7 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 president_staff: None in Budget 2016-17 vs 52.59 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 rajya_sabha: None in Budget 2016-17 vs 377.21 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 revenue: 22271.48 in Budget 2016-17 vs 11544.48 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 road_transport_highways: 46983.0 in Budget 2016-17 vs 57976.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 rural_development: 7671.4 in Budget 2016-17 vs 86055.8 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 school_education: 8466.5 in Budget 2016-17 vs 43554.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 social_justice: 1934.35 in Budget 2016-17 vs 6565.95 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:agriculture: 12739.96 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:animal_husbandry_dairying: 540.23 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:ayush: 394.0 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:drinking_water_sanitation: 12537.0 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:economic_affairs_centralised: 14850.0 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:environment: 856.42 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:health_family_welfare: 20510.59 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:higher_education: 1180.0 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:home_affairs: 1813.11 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:hupa: 4795.92 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:labour_employment: 111.25 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:land_resources: 1477.85 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:law_justice: 460.01 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:minority_affairs: 991.75 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:north_eastern_region: 1600.0 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:road_transport_highways: 10833.0 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:rural_development: 78298.05 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:school_education: 34807.28 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:social_justice: 4617.1 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:statistics: 3980.01 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:tribal_affairs: 4427.22 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:urban_development: 6668.4 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:water_resources: 1625.27 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 state_plans:women_child: 14257.93 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 statistics: 772.82 in Budget 2016-17 vs 4752.83 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 transfers_to_states: None in Budget 2016-17 vs 125496.36 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 tribal_affairs: 399.28 in Budget 2016-17 vs 4826.5 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 upsc: None in Budget 2016-17 vs 217.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 urban_development: 17461.6 in Budget 2016-17 vs 24523.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_andaman_nicobar: 4072.02 in Budget 2016-17 vs 4045.02 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_chandigarh: 3544.54 in Budget 2016-17 vs 3534.54 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_dadra_nagar_haveli: 1060.84 in Budget 2016-17 vs 1055.84 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_daman_diu: 766.72 in Budget 2016-17 vs 762.72 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_delhi: 853.0 in Budget 2016-17 vs 758.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_puducherry: 1409.0 in Budget 2016-17 vs 1390.0 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 ut_schemes_others: 1248.95 in Budget 2016-17 vs None in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 vice_president_secretariat: None in Budget 2016-17 vs 4.61 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 water_resources: 4566.8 in Budget 2016-17 vs 6201.21 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2016-17 women_child: 3094.32 in Budget 2016-17 vs 17408.12 in Budget 2017-18 (restated under the 2017-18 structure; grand totals agree)
- Restated: BE 2017-18 housing_urban_affairs: None in Budget 2017-18 vs 40617.84 in Budget 2018-19 (moved within housing_urban_affairs: the ministry total is the same in both)
- Restated: BE 2017-18 hupa: 6406.0 in Budget 2017-18 vs None in Budget 2018-19 (moved within housing_urban_affairs: the ministry total is the same in both)
- Restated: BE 2017-18 urban_development: 34211.84 in Budget 2017-18 vs None in Budget 2018-19 (moved within housing_urban_affairs: the ministry total is the same in both)
- Restated: BE 2019-20 ut_dadra_nagar_haveli: 1177.99 in Budget 2019-20 vs None in Budget 2020-21 (moved within home_affairs: the ministry total is the same in both)
- Restated: BE 2019-20 ut_daman_diu: 821.48 in Budget 2019-20 vs None in Budget 2020-21 (moved within home_affairs: the ministry total is the same in both)
- Restated: BE 2019-20 ut_dnh_dd: None in Budget 2019-20 vs 1999.47 in Budget 2020-21 (moved within home_affairs: the ministry total is the same in both)

## ✅ Ministries: Excel copies agree with the PDF
12 checks, 0 failures.

- Budget 2011-12: XLS matches PDF exactly.
- Budget 2012-13: XLS matches PDF exactly.
- Budget 2013-14: XLS matches PDF exactly.
- Budget 2017-18: 24 values in only one copy: the Excel copy mislabels the six category lines under Grand Total (all read "Centre's expenditure" / "Transfers to ..."), so they cannot be matched; the PDF labels them correctly.
- Budget 2017-18: XLSX matches PDF exactly.
- Budget 2019-20: XLSX matches PDF exactly.
- Budget 2020-21: XLSX matches PDF exactly.
- Budget 2021-22: XLS matches PDF exactly.
- Budget 2022-23: XLS matches PDF exactly.
- Budget 2023-24: XLS matches PDF exactly.
- Budget 2024-25: XLSX matches PDF exactly.
- Budget 2025-26: 24 values in only one copy: the PDF has no category lines under Grand Total; the Excel copy adds them.
- Budget 2025-26: XLSX matches PDF exactly.
- Budget 2026-27: XLSX matches PDF exactly.

## ✅ Schemes: revenue + capital = total in every row
32912 checks, 0 failures.

- Budget 2025-26 css: 'Grand Total' BE 2025-26: 536826.78 + 23.43 != 541850.21. Explained: Budget 2025-26 Statement 4A Grand Total, BE 2025-26: printed revenue 5,36,826.78 (read from the page image; the row is missing from the text layer) but printed total 5,41,850.21 = 5,41,826.78 + 23.43, and the Demand subtotals add to 5,41,826.78 revenue. The printed revenue figure is 5,000 crore short; shown as printed.

## ✅ Schemes add up to their subtotals and the Grand Total
9468 checks, 0 failures.

- Budget 2017-18 central_sector demand_subtotal 48 (Police) Actual 2015-16 revenue: schemes sum to 782.54, subtotal 779.37. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 67 (Ministry of New and Renewable Energy) Actual 2015-16 revenue: schemes sum to 4,064.72, subtotal 74.86. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) Actual 2015-16 capital: schemes sum to 99,995.74, subtotal 35,007.87. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 81 (Ministry of Road Transport and Highways) Actual 2015-16 capital: schemes sum to 27,532.65, subtotal 4,612.56. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) Actual 2015-16 total: schemes sum to 8,934.91, subtotal 8,931.68. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 67 (Ministry of New and Renewable Energy) Actual 2015-16 total: schemes sum to 4,064.72, subtotal 74.86. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) Actual 2015-16 total: schemes sum to 99,995.74, subtotal 35,007.87. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 81 (Ministry of Road Transport and Highways) Actual 2015-16 total: schemes sum to 30,188.74, subtotal 7,268.65. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) BE 2016-17 revenue: schemes sum to 1,096.94, subtotal 1,018.06. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 31 (Department of Financial Services) BE 2016-17 capital: schemes sum to 29,620.00, subtotal 27,840.00. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) BE 2016-17 capital: schemes sum to 7,753.92, subtotal 7,682.80. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) BE 2016-17 capital: schemes sum to 106,795.95, subtotal 45,000.00. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 81 (Ministry of Road Transport and Highways) BE 2016-17 capital: schemes sum to 24,953.00, subtotal 5,300.00. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 31 (Department of Financial Services) BE 2016-17 total: schemes sum to 33,561.79, subtotal 31,781.79. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) BE 2016-17 total: schemes sum to 8,850.86, subtotal 8,700.86. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) BE 2016-17 total: schemes sum to 106,795.95, subtotal 45,000.00. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 81 (Ministry of Road Transport and Highways) BE 2016-17 total: schemes sum to 27,990.57, subtotal 8,337.57. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) RE 2016-17 revenue: schemes sum to 1,013.75, subtotal 777.27. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 31 (Department of Financial Services) RE 2016-17 capital: schemes sum to 33,206.38, subtotal 28,081.38. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) RE 2016-17 capital: schemes sum to 8,319.80, subtotal 8,306.28. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) RE 2016-17 capital: schemes sum to 107,861.12, subtotal 46,155.00. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 31 (Department of Financial Services) RE 2016-17 total: schemes sum to 36,450.50, subtotal 31,325.50. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) RE 2016-17 total: schemes sum to 9,333.55, subtotal 9,083.55. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) RE 2016-17 total: schemes sum to 107,861.12, subtotal 46,155.00. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) BE 2017-18 revenue: schemes sum to 1,237.45, subtotal 946.84. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 31 (Department of Financial Services) BE 2017-18 capital: schemes sum to 16,886.02, subtotal 14,718.02. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) BE 2017-18 capital: schemes sum to 9,581.98, subtotal 9,559.29. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) BE 2017-18 capital: schemes sum to 120,341.46, subtotal 55,000.00. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 31 (Department of Financial Services) BE 2017-18 total: schemes sum to 19,426.99, subtotal 17,258.99. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 48 (Police) BE 2017-18 total: schemes sum to 10,819.43, subtotal 10,506.13. Explained: Budget 2017-18 Statement 4B: for this Demand the scheme rows add to more than the printed Demand subtotal in some columns (the old Actual 2015-16 / BE 2016-17 columns were recast from the Plan/Non-plan budget, and some rows appear at gross outlay, e.g. amounts met from dedicated funds). The statement does not itemise the difference. Subtotals were checked on the page image (Demand 67: 74.86); rows shown as printed.
- Budget 2017-18 central_sector demand_subtotal 80 (Ministry of Railways) BE 2017-18 total: schemes sum to 120,341.46, subtotal 55,000.00. Explained: Budget 2017-18 (the first budget with this statement, and the first with Railways merged into the Union Budget) lists Railways' scheme rows at their full outlay, including spending financed from the Railways' internal and extra-budgetary resources, while the Demand subtotal is the budgetary support only (BE 2017-18: 55,000 crore). Checked on the page image: the subtotal is printed as parsed. Rows shown as printed.
- Budget 2018-19 central_sector demand_subtotal 56 (Ministry of Housing and Urban Affairs) Actual 2016-17 revenue: schemes sum to 2,084.76, subtotal 2,398.76. Explained: Budget 2018-19 Statement 4B, Ministry of Housing and Urban Affairs, Actual 2016-17: the schemes' total matches the Demand subtotal, but 314.00 crore is classed as capital in the subtotal and as revenue in the scheme rows. Shown as printed.
- Budget 2018-19 central_sector demand_subtotal 56 (Ministry of Housing and Urban Affairs) Actual 2016-17 capital: schemes sum to 16,823.15, subtotal 16,509.15. Explained: Budget 2018-19 Statement 4B, Ministry of Housing and Urban Affairs, Actual 2016-17: the schemes' total matches the Demand subtotal, but 314.00 crore is classed as capital in the subtotal and as revenue in the scheme rows. Shown as printed.
- Budget 2024-25 central_sector BE 2024-25 revenue: Grand Total equals the sum of all scheme rows (750,579.03) but not of the group subtotals (742,579.03).
- Budget 2024-25 central_sector demand_subtotal 71 (Ministry of New and Renewable Energy) BE 2024-25 revenue: schemes sum to 20,852.76, subtotal 18,852.76. Explained: Budget 2024-25 Statement 4B: MNRE and Road Transport scheme rows include transfers to funds (2,000 and 6,000 crore) that the Demand subtotals leave out; the statement's last row 'Others (including amount met from & transfer to various funds)' carries the offsetting -8,000 crore. The scheme rows add up exactly to the Grand Total. Budget 2025-26, which reprints these BE 2024-25 figures, keeps the Demands gross.
- Budget 2024-25 central_sector demand_subtotal 86 (Ministry of Road Transport and Highways) BE 2024-25 revenue: schemes sum to 11,591.85, subtotal 5,591.85. Explained: Budget 2024-25 Statement 4B: MNRE and Road Transport scheme rows include transfers to funds (2,000 and 6,000 crore) that the Demand subtotals leave out; the statement's last row 'Others (including amount met from & transfer to various funds)' carries the offsetting -8,000 crore. The scheme rows add up exactly to the Grand Total. Budget 2025-26, which reprints these BE 2024-25 figures, keeps the Demands gross.
- Budget 2024-25 central_sector BE 2024-25 total: Grand Total equals the sum of all scheme rows (1,516,175.75) but not of the group subtotals (1,508,175.75).
- Budget 2024-25 central_sector demand_subtotal 71 (Ministry of New and Renewable Energy) BE 2024-25 total: schemes sum to 20,852.76, subtotal 18,852.76. Explained: Budget 2024-25 Statement 4B: MNRE and Road Transport scheme rows include transfers to funds (2,000 and 6,000 crore) that the Demand subtotals leave out; the statement's last row 'Others (including amount met from & transfer to various funds)' carries the offsetting -8,000 crore. The scheme rows add up exactly to the Grand Total. Budget 2025-26, which reprints these BE 2024-25 figures, keeps the Demands gross.
- Budget 2024-25 central_sector demand_subtotal 86 (Ministry of Road Transport and Highways) BE 2024-25 total: schemes sum to 283,830.09, subtotal 277,830.09. Explained: Budget 2024-25 Statement 4B: MNRE and Road Transport scheme rows include transfers to funds (2,000 and 6,000 crore) that the Demand subtotals leave out; the statement's last row 'Others (including amount met from & transfer to various funds)' carries the offsetting -8,000 crore. The scheme rows add up exactly to the Grand Total. Budget 2025-26, which reprints these BE 2024-25 figures, keeps the Demands gross.
- Budget 2025-26 css BE 2025-26 revenue: groups sum to 541,826.78, Grand Total 536,826.78. Explained: Budget 2025-26 Statement 4A Grand Total, BE 2025-26: printed revenue 5,36,826.78 (read from the page image; the row is missing from the text layer) but printed total 5,41,850.21 = 5,41,826.78 + 23.43, and the Demand subtotals add to 5,41,826.78 revenue. The printed revenue figure is 5,000 crore short; shown as printed.

## ✅ Same scheme figure agrees across the two budgets that print it
5915 checks, 0 failures.

- 100 scheme rows not compared: the same name appears twice under one department in that budget, so they cannot be matched across budgets by name.
- Restated: central_sector 'Grand Total' BE 2017-18: 666,644.02 in budget 2017-18 vs 663,663.02 in budget 2018-19
- Restated (reorganised schemes): central_sector 'National AIDS and STD Control Programme' BE 2022-23: 2,622.75 in budget 2022-23 vs 3,027.02 in budget 2023-24
- Restated: css 'National Health Mission' BE 2022-23: 37,800.23 in budget 2022-23 vs 37,159.73 in budget 2023-24
- Restated (reorganised schemes): css 'Others (including amount Met from & Transfer to va' BE 2024-25: -8,634.42 in budget 2024-25 vs -8,034.42 in budget 2025-26
- Restated (reorganised schemes): css 'Pradhan Mantri Krishi Sinchai Yojna' BE 2023-24: 10,787.23 in budget 2023-24 vs 8,587.23 in budget 2024-25
- Restated (reorganised schemes): css 'Pradhan Mantri Krishi Sinchai Yojna' BE 2024-25: 9,339.37 in budget 2024-25 vs 8,249.80 in budget 2025-26

## ✅ Scheme tables: other copies agree with the PDF
12 checks, 0 failures.

- Budget 2019-20 css: XLSX agrees with the PDF.
- Budget 2021-22 css: XLSX differs in 15 values (known): An earlier version: about 25,786 crore of BE 2021-22 sits in item 36 'Others' (26,446.35) instead of the named Core schemes (e.g. Saksham Anganwadi and Poshan 2.0, 20,105), so the Core and Others subtotals differ. The PDF's rows add up to its subtotals and Grand Total.
- Budget 2021-22 central_sector: XLS agrees with the PDF.
- Budget 2022-23 css: XLS agrees with the PDF.
- Budget 2022-23 central_sector: XLS agrees with the PDF.
- Budget 2023-24 css: XLS differs in 4 values (known): The Excel copy leaves BE 2023-24 blank for 'Assistance to States Agencies for Intra-State Movement of Foodgrains...' (the PDF and its page image show 7,424.60) and numbers two rows '58', so 'Others (Recoveries)' cannot be matched.
- Budget 2023-24 central_sector: XLS agrees with the PDF.
- Budget 2024-25 css: XLSX agrees with the PDF.
- Budget 2024-25 central_sector: XLSX differs in 87 values (known): A BE-2024-25-only copy that leaves out 8 Demands (5, 9, 43, 44, 45, 78, 92, 95) and their 79 schemes; every row it does have matches the PDF.
- Budget 2025-26 css: XLSX differs in 1 values (known): Has no Grand Total row, like the PDF's text layer (apparently converted from the PDF); every other row matches.
- Budget 2025-26 central_sector: XLSX copy could not be read (2025-26 central_sector xlsx p0 '530. Bridge Works, Turnnel Works and Approaches': cannot read value '... 2137.46 2137.46').
- Budget 2026-27 css: XLSX agrees with the PDF.
- Budget 2026-27 central_sector: XLSX agrees with the PDF.

## ✅ Scheme spending as a share of total expenditure (context only)
0 checks, 0 failures.

- Budget 2017-18, BE 2017-18: share of total expenditure: css 13.0%, central_sector 31.1%
- Budget 2018-19, BE 2018-19: share of total expenditure: css 12.5%, central_sector 29.0%
- Budget 2019-20, BE 2019-20: share of total expenditure: css 11.9%, central_sector 31.3%
- Budget 2020-21, BE 2020-21: share of total expenditure: css 11.2%, central_sector 27.3%
- Budget 2021-22, BE 2021-22: share of total expenditure: css 10.9%, central_sector 30.2%
- Budget 2022-23, BE 2022-23: share of total expenditure: css 11.2%, central_sector 29.9%
- Budget 2023-24, BE 2023-24: share of total expenditure: css 10.6%, central_sector 32.6%
- Budget 2024-25, BE 2024-25: share of total expenditure: css 10.5%, central_sector 31.5%
- Budget 2025-26, BE 2025-26: share of total expenditure: css 10.7%, central_sector 32.0%
- Budget 2026-27, BE 2026-27: share of total expenditure: css 10.3%, central_sector 33.1%

## ✅ Schemes: grand totals match the scheme lines of the ministries statement
80 checks, 0 failures.


## ✅ Matches PRS Legislative Research, Union Budget 2026-27 Analysis (independent)
117 checks, 0 failures.

- 117 of 117 published figures match to the crore: headline totals, taxes by type, five ministries and Defence, four schemes.

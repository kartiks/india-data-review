# Union Budget data

The Budget area of [India Data Review](../README.md): India's Union Budget, 2000-01
to today, built only from official budget documents and checked automatically.
This folder holds the data pipeline (`pipeline/`), the verified datasets
(`data/`) and the downloaded source files (`sources/`). The website is in `../site/`
(pages under `/budget/`).

## Data pipeline

Verified data on the Union Budget of India, **2000-01 to 2026-27**, taken
straight from official budget documents and checked automatically:

- **Headline figures:** receipts, spending, deficits (all 27 budgets).
- **Taxes by type:** corporation tax, income tax, GST, customs, excise, states' share, non-tax revenue (2000-01 onward).
- **Spending by ministry/department** (2000-01 onward).
- **Spending by scheme:** every Centrally Sponsored and Central Sector scheme (from Budget 2017-18).

The website that presents this data is in `../site/` (see `../site/README.md`); it can only be built when every data check passes.

## Run it

```bash
cd pipeline
uv run python -m budget_pipeline            # parse saved sources, build data, run all checks (~3 min)
uv run python -m budget_pipeline --fetch    # also download anything missing
uv run pytest                               # parser tests + end-to-end checks (~6 min)
```

The command exits with an error if any check fails, so it can gate a website build.
Current result: **117,270 checks, 0 failures** (see `data/validation_report.md`).

## What's in `data/`

| File | What it is |
|---|---|
| `fiscal.json` | Headline figures: one value per year × line item × estimate type, with source and any note. |
| `taxes.json` | Taxes and non-tax revenue by type. |
| `ministries.json` | Spending per department (with its ministry), Plan/Non-plan or Revenue/Capital split, and from 2017-18 the split into schemes/establishment/transfers. |
| `schemes.json` | Spending per scheme (Revenue/Capital/Total), with demand subtotals and grand totals. |
| `*.csv` / `observations.csv` | Every number read from every document (most figures appear in two budgets), with the label as printed and the source URL. |
| `validation_report.md` | Result of every check, and the reason for each allowed exception. |
| `format_comparison.json` | Where PDF, Excel and HTML copies of the headline table agree or differ. |

Values are in ₹ crore. A missing figure is left out, never stored as 0.

### Which number is used

Each budget prints four columns: Actuals (two years back), Budget Estimate
(BE) and Revised Estimate (RE) for last year, and BE for the new year.

- **BE** for year Y comes from Budget Y — what was announced.
- **RE** for Y comes from Budget Y+1.
- **Actual** for Y comes from Budget Y+2.
- If Budget Y+1 restates the BE, that version is kept as `be_restated`.

Not published yet: RE 2026-27 (due in Budget 2027-28) and Actuals for
2025-26 and 2026-27.

## Sources

All from indiabudget.gov.in, with URL and SHA-256 of every file in
`sources/manifest.json`. The printed PDF is the primary copy; Excel/HTML
copies are parsed too and must agree (several don't — see below).

| Data | Document |
|---|---|
| Headline | Budget at a Glance, Table 1 |
| Taxes | Budget at a Glance, "Receipts". Actuals 2000-01 to 2007-08: Receipt Budget, Annex 7 (the Receipts table had no Actuals column then) |
| Ministries | Expenditure Budget Vol. 1, Statement 2 (to 2016-17); Expenditure Profile, Statement 3/3A (from 2017-18) |
| Schemes | Expenditure Profile, Statements 4A (Centrally Sponsored) and 4B (Central Sector), from 2017-18 |

Independent references in `sources/reference/`: the RBI *Handbook of
Statistics on Indian Economy* (tables 86, 87, 89) and PRS Legislative
Research's *Union Budget 2026-27 Analysis*.

## How the data is verified

1. **Accounting rules in every column of every document.** For example: totals equal their parts; net tax = gross tax − states' share − NCCD; Revenue + Capital = Total for every ministry and scheme line.
2. **Tables tie to each other.** For every budget and column:
   - net tax and non-tax revenue in the Receipts table equal the headline table;
   - ministry spending adds up to total expenditure in the headline table (within ₹1 crore, all 27 budgets);
   - scheme grand totals equal the scheme lines of the ministries statement.
3. **Same figure, two documents.** A figure printed in two budgets must agree, or the restatement is explained.
4. **Other copies agree.** Excel/HTML copies are compared with the PDF.
5. **Independent publishers.**
   - RBI: 235 of 270 headline figures match exactly; the rest are explained.
   - PRS: all 117 figures match to the crore, covering headline totals, taxes by type, six ministries and four schemes.
6. **Every exception is written down with its reason** (`annotations.py`, and `KNOWN_EXCEPTIONS` in `taxes.py`, `ministries.py`, `schemes.py`). Nothing changes a number; notes are attached to affected figures instead.

### Problems found in the official files (examples)

- **Wrong HTML pages.** The 2005-06 HTML pages carry the 2003-04 numbers (headline and receipts). The 2004-05 HTML differs from its PDF.
- **Excel copies that differ from their PDFs:**
  - 2023-24 headline and receipts, 2025-26 headline/receipts/scheme tables;
  - 2021-22 and 2023-24 scheme tables;
  - 2024-25 Central Sector Excel leaves out 79 schemes.
- **Typos in the printed documents:**
  - Budget 2017-18, capital receipts 2015-16.
  - Budget 2023-24 ministries grand-total block (two transposed figures).
  - The Union Territories subtotal in every Statement 2 from 2011-12 to 2016-17.
  - Budget 2025-26 Statement 4A Grand Total (revenue ₹5,000 crore short of its own total).
- **Gaps in the PDF text layer.** Four values in two statements (2025-26 4A, 2017-18 4B) are missing from the text layer, so they were read from the page image. They carry a note. The 2025-26 4A Grand Total read this way equals the sum of 25 departments' scheme lines in a different statement.
- **2002-03 to 2004-05 capital expenditure includes debt repayments** to the National Small Savings Fund, so those three years aren't comparable with the rest. Their figures carry a note.

### Comparability notes for the website

- **Ministries.** Department ids stay the same through renames (`pipeline/budget_pipeline/data_maps/ministry_names.csv`). Splits and mergers keep separate ids, with notes.
  - Up to 2016-17, State Plan assistance routed through a department is listed separately (`state_plans:<id>`); from 2017-18 it's inside the department.
  - Union Territory demands are grouped under Home Affairs, as in the Demands for Grants.
- **Schemes** start in 2017-18. Before that, schemes appear only as "Plan outlays", which aren't comparable. Renamed schemes keep one id when the same figure is printed under both names (`data_maps/scheme_names.csv`).
- **"% of GDP"** is available only for the deficits, as printed in the budgets.

## Layout

```
pipeline/budget_pipeline/
  sources.py      where each table lives, per year and document type
  fetch.py        downloads every format, records checksums, checks the title
  readers.py      HTML / XLS / XLSX / PDF -> rows of cells
  parse.py        headline table
  taxes.py        Receipts table + Receipt Budget Annex 7
  ministries.py   Statement 2 / 3A (own position-based PDF reader)
  schemes.py      Statements 4A / 4B (own position-based PDF reader)
  build.py        headline dataset
  datasets.py     detailed datasets, scheme↔ministry and PRS cross-checks
  checks.py       all checks -> data/validation_report.md
  reference.py    RBI Handbook download and reader
  annotations.py  reviewed exceptions and notes for the headline data
  data_maps/      reviewed name maps for ministries and schemes
sources/raw/        the downloaded official files (kept for reproducibility)
sources/reference/  RBI tables and PRS reference values
```

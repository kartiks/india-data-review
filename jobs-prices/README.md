# Jobs, prices and household spending

The jobs and prices area of [India Data Review](../README.md): India's rural and urban indicators from MoSPI's
surveys, checked automatically. This folder holds the data pipeline (`pipeline/`), the datasets (`data/`) and the
downloaded source files (`sources/`). The website pages are under `/jobs-prices/` in `../site/`.

## What's covered

All from MoSPI's official data service (api.mospi.gov.in, behind esankhyiki.mospi.gov.in; no key):

- **Jobs: Periodic Labour Force Survey (PLFS)**, `/api/plfs/getData`
  - participation, worker ratio and unemployment by state, sex, age, area, education, religion and social group:
    annual (calendar years 2022 onward), quarterly (urban from April–June 2018, rural too from 2025), monthly (from 2025);
  - workers by type of work, industry, employer and occupation; job conditions of regular employees (July–June
    years from 2017-18); average earnings (regular, casual, self-employed).
- **Consumer Price Index**, base 2012, `/api/cpi/getCPIIndex`: January 2013 to December 2025. Every group and item
  group for All India; the general index for every state.
- **Consumer Price Index, base 2024** (from January 2026), from MoSPI's monthly press releases on PIB, listed by hand
  in `sources.CPI2024_RELEASES` (add each new month's page). The API lists base-2024 filters but returns no figures
  yet. The pipeline keeps each release's content (title to end, without the page's visitor counter) and its PDF where
  one is attached, and reads the HTML tables (`cpi2024.py`): 12 divisions, 43 groups, 36 states, and the All-India
  series from January 2025. The first release also gives the linking factors and old vs new weights.
- **CPI for agricultural and rural labourers** (Labour Bureau), `/api/cpialrl/getCpialrlRecords`: base 1986-87 and,
  from June 2025, base 2019.
- **Household Consumption Expenditure Survey** (HCES) 2022-23 and 2023-24, `/api/hces/getHcesRecords`. MoSPI publishes
  rural and urban figures only; for an overall (rural + urban) average the pipeline also downloads Table A2 of MoSPI's
  full 2023-24 report (`sources.HCES_REPORT_TABLES`), the survey's estimated number of persons in each state's rural and
  urban areas, and weights the two averages by it (`build.hces_overall`). The 2022-23 report's tables are not online
  as files, so overall figures are for 2023-24.

## Run it

```bash
cd pipeline
uv run python -m jobs_prices_pipeline             # build data from saved sources and run all checks
uv run python -m jobs_prices_pipeline --fetch     # also download anything missing
uv run python -m jobs_prices_pipeline --refresh   # re-download everything (after a MoSPI release)
uv run pytest
```

A full download is about 1,100 API pages (some 40 minutes). The API keeps only the latest figures, so when a
re-download differs, the old file is kept in `sources/snapshots/<date>/`.

## Keeping it up to date

### Each month

**Consumer prices (12th of the month).** MoSPI's data service does not yet return the base-2024 index, so:

1. Find the release on PIB: search pib.gov.in for "Press Release of Consumer Price Index on Base 2024=100 for
   <Month>, <year>", and copy the address of the English page
   (`https://www.pib.gov.in/PressReleasePage.aspx?PRID=…&reg=3&lang=1`).
2. Add it to `CPI2024_RELEASES` in `pipeline/jobs_prices_pipeline/sources.py`, keyed by the index month
   (`"2026-10": "…"`).
3. Run `uv run python -m jobs_prices_pipeline --fetch`. It downloads only the new release (page content and PDF),
   reads it, and checks it against its PDF and the earlier releases. The previous month's figures move from
   provisional to final.

**Jobs (PLFS monthly bulletin, mid-month; quarterly bulletin each quarter) and farm and rural labourers' prices
(end of the month).** Run `--refresh`. It re-downloads everything (about 40 minutes); files that changed are kept in
`sources/snapshots/`.

### When MoSPI's data service carries the base-2024 index

Check now and then with `https://api.mospi.gov.in/api/cpi/getCPIIndex?base_year=2024&series=Current&year=2026&Format=JSON&limit=5`
(the base-2024 series numbers states differently: All India is `state_code=1`). When it returns rows, add base-2024
queries to `queries()` in `sources.py`, read them in `build.py` beside the base-2012 ones, and compare them with
the press-release figures before switching the site over; the release reader can then be retired.

### New survey rounds

New PLFS years, CPI months and HCES rounds arrive through `--refresh` with no code change. A new indicator, a new
breakdown or a renamed field needs code: the field names are listed in `build.py` (`PLFS_FIELDS`, `HCES_SITE`) and the
checks will fail on anything they cannot read.

### When a check fails

Every allowed exception is in `pipeline/jobs_prices_pipeline/checks.py`, as a reason (`LEFT_OUT`, `ALL_INDIA_STATUS`,
`HCES_MISMATCH`, `BACKTICK` …) and the rule that applies it. Figures the site must not show are flagged in `build.py`
(`flag_rates` for jobs, `hces` for spending), with the reason kept in the CSV's `left_out` column. Read the failure
in `data/validation_report.md`, compare the figure with MoSPI's own publication, and only then add a rule.

## What's in `data/`

| File | What it is |
|---|---|
| `jobs_prices.json` | What the site shows, in compact form (text columns stored once in `labels`) |
| `plfs_rates.csv` | Participation, worker ratio and unemployment; `left_out` gives the reason where a combination is not shown |
| `plfs_workers.csv`, `plfs_conditions.csv`, `plfs_earnings.csv` | Workers by breakdown, job conditions, earnings |
| `cpi.csv`, `cpialrl.csv` | Price indices and inflation |
| `cpi2024.csv` | Every figure read from the base-2024 releases, with the release it came from |
| `hces.csv` | Household spending; `left_out` as above |
| `hces_overall.csv` | Rural + urban spending per person and food share, with the persons used as weights |
| `sources.csv` | Every downloaded file: key, URL, SHA-256, date. Each CSV row names its source key |
| `validation_report.md` | Every check and the reason for every allowed exception |

Columns ending `_as_printed` are filled only where MoSPI's text is not simply the number (`NaN`, `l0.8` …).

## Checks

- **Jobs**: worker ratio = participation × (1 − unemployment rate) within rounding; persons between men and
  women, rural + urban between rural and urban; shares of workers add up to 100%.
- **Prices**: every inflation rate reproduced from the index a year earlier; combined between rural and urban;
  no missing months.
- **New price series**: headline sentence, summary table and annexures agree; page tables match the PDF; later
  releases revise only the previous month's provisional figures; linking factor = 2025 average new ÷ old.
- **Spending**: the 12 spending classes reproduce the average; item categories add up to the food and non-food
  totals, and those to the average. Table A2's averages match the data service's; its states' persons add up to All
  India; every overall average lies between the rural and urban averages.

### Problems found in MoSPI's data (each left out and listed in the report)

- PLFS figures with transcription errors, mostly quarterly: letters for digits (`l0.8`, `IN.4`, `20J`) and
  combinations that break the identities above (April–June 2019 urban unemployment shows 21.6%; the bulletin says 8.9%).
  The build leaves such combinations out whole (`build.flag_rates`).
- All-India shares of workers by type of work do not add up to 100%; states' do.
- About 6,000 "distribution of workers" rows with no breakdown named.
- 2025 current-weekly-status self-employment shares whose parts do not add up.
- HCES 2022-23 rural spending by item category for six states (Goa, Gujarat, Haryana, Himachal Pradesh,
  Jharkhand, Karnataka) that adds up to other states' averages.
- Delhi's farm labourers' index (base 2019) published as 0.00.
- The July 2026 CPI release page prints one food index as `109.\`39`; the next release's final figure is used.

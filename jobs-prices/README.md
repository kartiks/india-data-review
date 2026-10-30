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
  group for All India; the general index for every state. The new base-2024 series is not in the API yet.
- **CPI for agricultural and rural labourers** (Labour Bureau), `/api/cpialrl/getCpialrlRecords`: base 1986-87 and,
  from June 2025, base 2019.
- **Household Consumption Expenditure Survey** (HCES) 2022-23 and 2023-24, `/api/hces/getHcesRecords`.

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

## What's in `data/`

| File | What it is |
|---|---|
| `jobs_prices.json` | What the site shows, in compact form (text columns stored once in `labels`) |
| `plfs_rates.csv` | Participation, worker ratio and unemployment; `left_out` gives the reason where a combination is not shown |
| `plfs_workers.csv`, `plfs_conditions.csv`, `plfs_earnings.csv` | Workers by breakdown, job conditions, earnings |
| `cpi.csv`, `cpialrl.csv` | Price indices and inflation |
| `hces.csv` | Household spending; `left_out` as above |
| `sources.csv` | Every downloaded file: key, URL, SHA-256, date. Each CSV row names its source key |
| `validation_report.md` | Every check and the reason for every allowed exception |

Columns ending `_as_printed` are filled only where MoSPI's text is not simply the number (`NaN`, `l0.8` …).

## Checks

- **Jobs**: worker ratio = participation × (1 − unemployment rate) within rounding; persons between men and
  women, rural + urban between rural and urban; shares of workers add up to 100%.
- **Prices**: every inflation rate reproduced from the index a year earlier; combined between rural and urban;
  no missing months.
- **Spending**: the 12 spending classes reproduce the average; item categories add up to the food and non-food
  totals, and those to the average.

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

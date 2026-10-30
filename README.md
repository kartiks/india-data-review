# India Data Review

**Live site: https://india-data-review.k4tech.in**

India's economy, public finances, jobs and prices from official data, checked automatically. One website with an area per
type of data, and a shared home page with charts that use more than one area.

| Folder | What |
|---|---|
| [`budget/`](budget/README.md) | Union Budget 2000-01 to today: pipeline, verified data, source documents |
| [`gdp/`](gdp/README.md) | GDP and national accounts (MoSPI), the Budget's GDP assumption, Economic Survey and RBI forecasts |
| [`jobs-prices/`](jobs-prices/README.md) | Jobs (PLFS), consumer prices (CPI, CPI-AL/RL) and household spending (HCES), from MoSPI |
| [`site/`](site/README.md) | The website: `/` home, `/budget/…`, `/gdp/…`, `/jobs-prices/…`, `/about/` |

Each data area is self-contained: its own `pipeline/` (a Python package run with uv), `data/` (the verified
datasets the site reads) and `sources/` (every downloaded file, listed in `sources/manifest.json` with its
URL and SHA-256). The site refuses to build unless every area's `data/validation_report.md` says PASSED.

> This repository previously held an Android app (Expo/React Native), preserved at the tag
> `android-app-final`. The GDP area was developed in a separate repository; its history is merged here.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for the pipelines. Each pipeline needs Python 3.14 or later; uv installs it and the
  packages on first run.
- Node.js 22.23.4 or later and npm for the site.

## Run it

```bash
(cd budget/pipeline && uv run python -m budget_pipeline)   # ~3 min; --fetch downloads anything missing
(cd gdp/pipeline && uv run python -m gdp_pipeline)         # --refresh after each MoSPI release
(cd jobs-prices/pipeline && uv run python -m jobs_prices_pipeline)  # --refresh after each MoSPI release
(cd site && npm install && npm run build)                  # or: npm run dev
```

Each pipeline command builds its area's `data/` from the files already in `sources/` and runs every check;
`--fetch` downloads anything missing first, and `--refresh` (GDP, jobs and prices) re-downloads everything.
Tests: `uv run pytest` in each `pipeline/` folder, and `npm run check` (type check) in `site/`.

## Updating the data

Vercel only builds the site. It never runs a pipeline: it reads the `data/` folders committed to this repository.
So every update is done locally:

1. Make any hand edits the release needs (see the calendar below and each area's README).
2. Run that area's pipeline with `--fetch` or `--refresh`. It must end with every check passing; if a check fails,
   look at the failure in `data/validation_report.md` before allowing anything (each area's README says where
   exceptions are written down, always with a reason).
3. Build the site (`npm run build` in `site/`) and look at the pages that changed.
4. Commit the area's `data/` and `sources/` (the downloaded files and `manifest.json`) together with any code changes,
   and push. A branch gets a Vercel preview; `main` deploys the live site.

| When | Release | Area | What to do |
|---|---|---|---|
| Late January | Economic Survey | GDP | Add the survey's growth projection to `forecast_sources/economic_survey.json` ([GDP README](gdp/README.md#adding-a-forecast)) |
| 1 February (or after an election) | Union Budget | Budget, GDP | Move to the new budget year ([Budget README](budget/README.md#adding-a-new-budget)) |
| Every two months | RBI monetary policy statement | GDP | Add the RBI's growth projection to `forecast_sources/rbi.json` |
| Early January, end of February, May, August, November | MoSPI GDP estimates | GDP | `--refresh` |
| 12th of every month | MoSPI Consumer Price Index | Jobs and prices | Add the release page, then `--fetch` ([Jobs and prices README](jobs-prices/README.md#each-month)) |
| Mid-month, and each quarter | MoSPI Periodic Labour Force Survey bulletins | Jobs and prices | `--refresh` |
| End of each month | Labour Bureau CPI for farm and rural labourers | Jobs and prices | `--refresh` |
| When published | MoSPI household spending survey, new survey rounds | Jobs and prices | `--refresh`; new indicators may need code |

The dates are MoSPI's and the Finance Ministry's usual pattern; MoSPI's advance release calendar on mospi.gov.in has
the exact dates.

## Adding a new area

1. Create `<area>/` with `pipeline/`, `data/` and `sources/`, following `gdp/` (fetch → build → checks,
   writing `data/validation_report.md`).
2. Add the area to `AREAS` in `site/scripts/copy-data.mjs`, a data module in `site/src/lib/<area>/`, pages in
   `site/src/pages/<area>/`, and a tab and sub-navigation in `site/src/layouts/Base.astro`.
3. Charts that combine areas go on the home page (`site/src/pages/index.astro`).

## Deployment

Vercel, project Root Directory `site` (it reads each area's `data/` folder, so "Include files
outside the root directory" must stay on).

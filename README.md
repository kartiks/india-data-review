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
| [`shared/pipeline/`](shared/pipeline/) | `pipeline_common`, the Python code the three pipelines share (a uv path dependency of each) |

Each data area is self-contained: its own `pipeline/` (a Python package run with uv), `data/` (the verified
datasets the site reads) and `sources/` (every downloaded file, listed in `sources/manifest.json` with its
URL and SHA-256). Each pipeline's checks write `data/validation_report.md` for people and
`data/validation_summary.json` for the site, which refuses to build unless every area's summary says PASSED. Code
the pipelines share (the validation report, downloading) is in `shared/pipeline/` (package `pipeline_common`).

> This repository previously held an Android app (Expo/React Native), preserved at the tag
> `android-app-final`. The GDP area was developed in a separate repository; its history is merged here.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for the pipelines. Each pipeline needs Python 3.14 or later; uv installs it and the
  packages on first run.
- Node.js 22.23.4 or later and npm for the site.

## Run it

```bash
(cd budget/pipeline && uv run python -m budget_pipeline)   # ~3 min; --fetch downloads anything missing
(cd gdp/pipeline && uv run python -m gdp_pipeline)         # refreshed weekly; see below
(cd jobs-prices/pipeline && uv run python -m jobs_prices_pipeline)  # refreshed weekly; see below
(cd site && npm install && npm run build)                  # or: npm run dev
```

Each pipeline command builds its area's `data/` from the files already in `sources/` and runs every check;
`--fetch` downloads anything missing first, and `--refresh` re-downloads everything (GDP and jobs and prices keep
changed files in `sources/snapshots/`; the budget overwrites its files, so compare them with the committed copies).
`--refresh-nas` (GDP) and `--refresh-api` (jobs and prices) re-download only the sources that are revised in place;
the weekly refresh runs them. `--help` lists an area's options; any other option is refused.
Tests: `uv run pytest` in each `pipeline/` folder (including `shared/pipeline/`), and `npm run check` (type check) in
`site/`.

## Keeping the data up to date

Vercel only builds the site. It never runs a pipeline: it reads the `data/` folders committed to this repository.
Data reaches the site in two ways: a **weekly GitHub Action** re-downloads the sources that are published as data and
revised in place, and everything else is **updated by hand** when it is released. Data added to the site later gets the
same decision: see [Adding data](#adding-data).

### What refreshes itself, and what doesn't

| Data on the site | Source | How it is kept up to date | Source changes |
|---|---|---|---|
| GDP and national accounts (base 2011-12 and 2022-23; annual and quarterly) | MoSPI national accounts API | **Weekly refresh** | Early January, end of February, May, August, November |
| State GDP (GDP › States): GSDP, NSDP, income per person, growth, value added by industry (base 2011-12) | MoSPI national accounts API (state accounts) | **Weekly refresh**; the new 2022-23 base is queried too, and the validation report says when it appears (the site then needs switching over) | When states publish their estimates, at different times through the year |
| Jobs: PLFS participation, worker ratio, unemployment, workers, job conditions, earnings | MoSPI API | **Weekly refresh** | Monthly bulletin mid-month; quarterly bulletin each quarter |
| Consumer prices, base 2012 (to December 2025) | MoSPI API | **Weekly refresh** (the series has ended, so it no longer changes) | No longer |
| CPI for farm and rural labourers | Labour Bureau, through MoSPI API | **Weekly refresh** | End of each month |
| Household spending (HCES): new rounds with the same indicators | MoSPI API | **Weekly refresh**; a new indicator or breakdown needs code ([Jobs and prices README](jobs-prices/README.md#new-survey-rounds)) | When a survey is published |
| States: unemployment, income per person, state GDP, state inflation, rural wages | RBI Handbook of Statistics on Indian States (tables 8–9, 19–22, 108, 112–115) | **Weekly refresh**: a new edition is picked up from RBI's page automatically; if RBI renumbers a table, it needs code ([Jobs and prices README](jobs-prices/README.md#each-december-a-new-rbi-handbook-edition)) | Each December |
| Consumer prices, base 2024 (from January 2026) | MoSPI monthly press releases on PIB | **By hand**: add the release's address, then `--fetch`; MoSPI's API does not serve this series yet ([Jobs and prices README](jobs-prices/README.md#each-month)) | 12th of each month |
| GDP per person (GDP › Per person): GDP, national income and household spending per person | MoSPI national accounts API, divided by population: the official 2019 projections, then MoSPI's own figures from its press notes (cross-checked with the RBI's Handbook of Statistics on the Indian Economy) | **Weekly refresh** of the totals. The population is **by hand**: add each new year from MoSPI's press note, and each year's *National Accounts Statistics* per-capita statement, downloaded from MoSPI's site in a browser ([GDP README](gdp/README.md#adding-a-years-population)); until then the report lists the year, it has no per-person figures, and the Per person page stays on the year before | Population for a new year: early January (First Advance Estimates); National Accounts Statistics: August or September |
| Union Budget: headline figures, taxes, ministries, schemes | Budget documents on indiabudget.gov.in | **By hand**: move to the new budget year ([Budget README](budget/README.md#adding-a-new-budget)) | 1 February, or the full budget after an election |
| The Budget's GDP assumption (GDP pages) | Budget at a Glance | **By hand**, with the new budget (step 5 of the Budget README) | 1 February |
| Economic Survey growth projection (GDP forecasts page) | Economic Survey | **By hand**: quote it in `forecast_sources/economic_survey.json` ([GDP README](gdp/README.md#adding-a-forecast)) | Late January |
| RBI growth projection (GDP forecasts page) | RBI monetary policy statements | **By hand**: quote it in `forecast_sources/rbi.json` ([GDP README](gdp/README.md#adding-a-forecast)) | Every two months |
| Overall (rural + urban) household spending 2023-24 | MoSPI's HCES 2023-24 report, Table A2 | Fixed: a published report | Never |
| Budget cross-checks (used by the checks, described in the Budget pages' notes) | RBI Handbook of Statistics on Indian Economy; PRS budget analysis | **By hand** (step 4 of the Budget README) | RBI: yearly, second half of the year; PRS: after each budget |
| India map | DataMeet state boundaries | Fixed | Never |

The release dates are MoSPI's and the Finance Ministry's usual pattern; MoSPI's advance release calendar on
mospi.gov.in has the exact dates.

### The weekly refresh

[`.github/workflows/data-refresh.yml`](.github/workflows/data-refresh.yml) runs every **Sunday at 02:00 IST**
(Saturday 20:30 UTC; GitHub often starts scheduled runs a little late). A run takes about 65 minutes, most of it the
1,400 pages of MoSPI's jobs and prices data (about an hour from GitHub's servers), plus the local CI when something
changed. It:

1. Re-downloads the GDP sources (`gdp_pipeline --refresh-nas`) and the jobs and prices sources
   (`jobs_prices_pipeline --refresh-api`), then rebuilds each area's `data/` and runs every check. Each area has its
   own time limit (30 and 150 minutes), so a slow source fails only its own area. Fixed documents
   (budget papers, press releases, report tables, forecast documents) are not downloaded again; a document that is
   listed in the code but missing is downloaded.
2. Keeps history. These sources hold only their latest figures, so when a download differs from the saved file, the
   pipeline keeps the old file under `<area>/sources/snapshots/<date it was fetched>/` and records it in the
   manifest's `history`. This is how the revision history of each release builds up.
3. Commits an area only if its sources changed **and** its download finished with every check passing. An area with
   no change is left alone, so a quiet week makes no commit. The commit is named `Data refresh <date>: <areas>`.
4. Runs the local CI (`scripts/ci.sh`, below) on that commit, and pushes it to `main` only if it passes. Vercel then
   deploys the live site. If both areas changed, they go in one commit, so a CI failure holds back both. If `main`
   moved during the run (a PR was merged), the commit is replayed on top of it and checked again before the push.
5. If anything failed, the run fails and GitHub emails whoever last changed the workflow's schedule (or started the
   run by hand). The run then keeps an artifact (`data-refresh-<run id>`, for 90 days) with each area's validation
   report and every changed file that was not pushed.

Only a run on `main` pushes. A run started by hand on another branch does everything else and keeps its downloads
as an artifact. The push is made as `github-actions[bot]` straight to `main`, so `main` must not get branch
protection or a ruleset that requires a pull request; if it does, every refresh with new data fails at the push.

**When it passes**, nothing is needed. Look over the `Data refresh` commit on `main` now and then: the
"Large revisions to growth" section of `gdp/data/validation_report.md` lists big revisions for review.

**When it fails:**

1. Open the run from the email (or the Actions tab) and read the failed step's log. The artifact has each area's
   `data/validation_report.md` and any new downloads.
2. Reproduce it locally: run the same command in the area's `pipeline/` folder (`--refresh-nas` for GDP,
   `--refresh-api` for jobs and prices). It downloads the same files.
3. Fix it: compare the failing figure with the source's own publication, then fix the code or add an allowed exception
   with its reason (each area's README says where). A message saying a query returned no rows although it had data
   before usually means the source is having trouble; the saved file is kept, so wait and run again.
4. Commit the area's `sources/` and `data/` with the fix, run `scripts/ci.sh`, and push (or open a pull request).

Nothing is lost while a failure waits, unless a source publishes twice before it is fixed: the previous version is
still on `main`, and the next successful download keeps it as a snapshot. The artifact holds anything in between.

**Run it now:** "Run workflow" on the workflow's page in the Actions tab, or `gh workflow run data-refresh.yml`.

**If it stops running:** GitHub turns off scheduled workflows in a public repository after 60 days with no activity in
it. If that happens, turn it back on from the workflow's page in the Actions tab.

### Updating by hand

For everything marked "by hand" above, or to refresh a source outside the schedule:

1. Make the edits the release needs (see the table above and each area's README).
2. Run that area's pipeline with `--fetch` (download what is missing) or `--refresh` (download everything again). It
   must end with every check passing; if a check fails, look at the failure in `data/validation_report.md` before
   allowing anything (each area's README says where exceptions are written down, always with a reason).
3. Build the site (`npm run build` in `site/`) and look at the pages that changed.
4. Commit the area's `data/` and `sources/` (the downloaded files and `manifest.json`) together with any code changes.
   Open a pull request and run the local CI on it before merging. A branch gets a Vercel preview; `main` deploys the
   live site.

## Local CI

Pull requests have no hosted CI. Before merging one, run the local CI on its branch:

```bash
scripts/ci.sh <branch>
```

It checks out that commit in a temporary folder (your working folder is not touched) and passes only if:

- every area's pipeline rebuilds `data/` from the committed sources with every check passing;
- the rebuilt `data/` matches what is committed, apart from the build time (`generated_at`);
- the build changes no committed file in `sources/` and writes no new files;
- every area's tests pass, and the shared pipeline code's;
- the site type-checks and builds.

It downloads no data (npm and uv may download packages) and takes about six minutes, most of it the budget tests.
The weekly refresh runs the same script on its own commit before pushing.

## Adding data

### Decide how it will be kept up to date

Every time data is added to the site, whether a new area or a new source in an existing one, decide whether the
weekly refresh will cover it, and record the decision with its reason in the table under
[What refreshes itself](#what-refreshes-itself-and-what-doesnt) and in the area's README.

- **Weekly**, if the source is published as data and revised in place: an API, or a spreadsheet re-issued at the same
  address. These lose their old figures when revised, so only a regular download keeps the history.
- **By hand**, if it is a document published once per release (PDFs, press releases, budget papers), or the site
  blocks automated downloads. Say in the area's README when to update it and how.
- **Fixed**, if it will never change (a one-off report table, a map).

Also check the time budget: a weekly run allows each area its own limit (30 minutes for GDP, 150 for jobs and prices,
which takes about an hour on GitHub) and 240 minutes in all.

### A new source in an existing area

1. Add it to the area's `sources.py` and `fetch.py`, read it in `build.py`, and add checks for it.
2. If it is refreshed weekly, make the area's refresh option (`--refresh-nas` for GDP, `--refresh-api` for jobs and
   prices) re-download it, with the area's `save()` (`pipeline_common.download.save`, which keeps the old file as a
   snapshot) and the same guard against data that vanishes, and extend `tests/test_fetch.py`. If its download is
   slow, raise the area's `timeout` in `.github/workflows/data-refresh.yml`.
3. Update the table and the area's README, as above.

### A new area

1. Create `<area>/` with `pipeline/`, `data/` and `sources/`, following `gdp/` (fetch → build → checks). Add
   `pipeline-common` to the pipeline's dependencies as a path dependency (copy `[tool.uv.sources]` from
   `gdp/pipeline/pyproject.toml`), and write the checks with its `Report`, which writes `data/validation_report.md`
   and the `data/validation_summary.json` the site reads. Code that more than one area needs goes in
   `shared/pipeline/pipeline_common/`, with tests in `shared/pipeline/tests/`; area-specific code stays in the area.
2. Add the area to `AREAS` in `site/scripts/copy-data.mjs`, a data module in `site/src/lib/<area>/`, pages in
   `site/src/pages/<area>/`, and a tab and sub-navigation in `site/src/layouts/Base.astro`.
3. Charts that combine areas go on the home page (`site/src/pages/index.astro`).
4. Add the area to `AREAS` in `scripts/ci.sh`.
5. If any of its sources are refreshed weekly, give its pipeline an option that re-downloads only those (with tests in
   `tests/test_fetch.py`), add a step for it to `.github/workflows/data-refresh.yml` with its own `timeout`, and add
   the area wherever the workflow names `gdp` and `jobs-prices` (the commit step's `env` and list of areas, the
   artifact paths and conditions, the final failure check).
6. Add its datasets to the table, as above.

## Deployment

Vercel, project Root Directory `site` (it reads each area's `data/` folder, so "Include files
outside the root directory" must stay on).

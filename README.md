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
URL and SHA-256; the manifest has the same layout in every area, described in
[`download.py`](shared/pipeline/pipeline_common/download.py)). Each pipeline's checks write `data/validation_report.md` for people and
`data/validation_summary.json` for the site, which refuses to build unless every area's summary says PASSED and
records the SHA-256 of every data file as it is now (so data changed after its checks ran cannot deploy). Code
the pipelines share (the validation report, downloading, reading Budget at a Glance, fiscal-year labels, ids and
number parsing) is in `shared/pipeline/` (package `pipeline_common`). Abbreviations (NAS, GVA, BE/RE, PLFS …) are
explained under [Terms](#terms).

> This repository previously held an Android app (Expo/React Native), preserved at the tag
> `android-app-final`. The GDP area was developed in a separate repository; its history is merged here.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for the pipelines: install it first ([installation](https://docs.astral.sh/uv/getting-started/installation/)).
  Each pipeline needs Python 3.14 or later; uv installs it and the packages on first run.
- Node.js 22.23.4 or later and npm for the site.

## Run it

```bash
(cd budget/pipeline && uv run python -m budget_pipeline)   # ~3 min; --fetch downloads anything missing
(cd gdp/pipeline && uv run python -m gdp_pipeline)         # refreshed weekly; see below
(cd jobs-prices/pipeline && uv run python -m jobs_prices_pipeline)  # refreshed weekly; see below
(cd site && npm ci && npm run build)                       # or: npm run dev
(cd site && npm run preview)                               # serve the built site from dist/
```

The source files are committed, so a fresh clone needs no download. `uv run --locked` (what `scripts/ci.sh` and the
weekly refresh use) stops with an error if `uv.lock` is out of date instead of updating it.

Each pipeline command builds its area's `data/` from the files already in `sources/` and runs every check;
`--fetch` downloads anything missing first, and `--refresh` re-downloads everything (a changed file's previous copy is
kept in `sources/snapshots/`).
`--refresh-api` (GDP, and jobs and prices; the budget has no such sources) re-downloads only the sources that are
revised in place; the weekly refresh runs it. The options are the same in every area (`pipeline_common/cli.py`):
`--help` lists them; an option renamed since (`--refresh-nas`, `--force`…) is refused with its new name, and any
other is refused too. Output is plain lines: progress and check results on stdout, warnings and errors on stderr
(`pipeline_common/log.py`).
Tests: `uv run pytest` in each `pipeline/` folder (including `shared/pipeline/`), and `npm run check` (type check) in
`site/`.

## Keeping the data up to date

Vercel only builds the site. It never runs a pipeline: it reads the `data/` folders committed to this repository.
Data reaches the site in two ways: a **weekly GitHub Action** re-downloads the sources that are published as data and
revised in place, and everything else is **updated by hand** when it is released; for a new budget, an Economic Survey,
an RBI policy statement and a year's population, the weekly refresh also checks whether one is probably out and not
yet added, and fails its run with a line saying what to add. Data added to the site later gets the
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
| GDP per person (GDP › Per person): GDP, national income and household spending per person | MoSPI national accounts API, divided by population: the official 2019 projections, then MoSPI's own figures from its press notes (cross-checked with the RBI's Handbook of Statistics on the Indian Economy) | **Weekly refresh** of the totals. The population is **by hand**: add each new year from MoSPI's press note, and each year's *National Accounts Statistics* per-capita statement, downloaded from MoSPI's site in a browser ([GDP README](gdp/README.md#adding-a-years-population)); the weekly refresh fails its run when a year is missing (`gdp_pipeline.due`), and until then the report lists the year, it has no per-person figures, and the Per person page stays on the year before | Population for a new year: early January (First Advance Estimates); National Accounts Statistics: August or September |
| Union Budget: headline figures, taxes, ministries, schemes | Budget documents on indiabudget.gov.in | **By hand**: move to the new budget year ([Budget README](budget/README.md#adding-a-new-budget)); the weekly refresh fails its run once a newer budget is on indiabudget.gov.in (`budget_pipeline.due`) | 1 February, or the full budget after an election |
| The Budget's GDP assumption (GDP pages) | Budget at a Glance | **By hand**, with the new budget (step 5 of the Budget README) | 1 February |
| Economic Survey growth projection (GDP forecasts page) | Economic Survey | **By hand**: quote it in `gdp/pipeline/gdp_pipeline/forecast_sources/economic_survey.json` ([GDP README](gdp/README.md#adding-a-forecast)); the weekly refresh fails its run when one is probably out (`gdp_pipeline.due`) | Late January |
| RBI growth projection (GDP forecasts page) | RBI monetary policy statements | **By hand**: quote it in `gdp/pipeline/gdp_pipeline/forecast_sources/rbi.json` ([GDP README](gdp/README.md#adding-a-forecast)); the weekly refresh fails its run when the latest is over 66 days old (`gdp_pipeline.due`) | Every two months |
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

1. Re-downloads the GDP sources (`gdp_pipeline --refresh-api`) and the jobs and prices sources
   (`jobs_prices_pipeline --refresh-api`), then rebuilds each area's `data/` and runs every check. Each area has its
   own time limit (30 and 150 minutes), so a slow source fails only its own area. Fixed documents
   (budget papers, press releases, report tables, forecast documents) are not downloaded again; a document that is
   listed in the code but missing is downloaded. It also runs `budget_pipeline.due` and `gdp_pipeline.due`, which
   say whether a release added by hand is probably out and not yet added: a new budget (from indiabudget.gov.in), an
   Economic Survey, an RBI policy statement, a year's population or National Accounts Statistics (from dates). These
   never hold back the data; step 6 fails the run with one line per release, saying what to add and where.
2. Keeps history. These sources hold only their latest figures, so when a download differs from the saved file, the
   pipeline keeps the old file under `<area>/sources/snapshots/<time it was fetched>/` (UTC, `2026-11-06T093000Z`; folders from before
   are named by date only) and records it in the
   manifest's `history`. This is how the revision history of each release builds up.
3. Commits an area only if its sources changed **and** its download finished with every check passing. An area with
   no change is left alone, so a quiet week makes no commit. The commit is named `Data refresh <date>: <areas>`.
4. Runs the local CI (`scripts/ci.sh`, below) on that commit. If both areas changed, they go in one commit, so a CI
   failure holds back both. If `main` moved during the run (a PR was merged), the commit is replayed on top of it and
   checked again.
5. Pushes the commit to `main` if the data has only new figures; Vercel then deploys the live site. If the data has
   **new text** (a new state, item, unit, note or source address, anything but figures, dates, months, quarters and
   years: [`labels.py`](shared/pipeline/pipeline_common/labels.py) says exactly what counts), it pushes the branch
   `data-refresh/<date>` and opens a pull request listing the new text, for you to review and merge. If `main` moved
   again between the checks and the push, the commit also goes to a pull request (run `scripts/ci.sh` on it before
   merging).
6. If anything failed, or a release added by hand is due, the run fails (after the data is published) and GitHub
   emails whoever last changed the workflow's schedule (or started the run by hand). The due releases are also listed
   in the run's summary and in any pull request it opens. Every run keeps an artifact (`data-refresh-<run id>`, for 90 days) with each area's validation report
   and refresh output, the refresh commit (`refresh.bundle`), the new text (`labels.md`) and every changed file that
   was not committed.

The work is split in two jobs so that no token that can write to the repository exists while packages are installed
and code runs: the `refresh` job (steps 1 to 4, and the artifact) has a read-only token, and the `publish` job
(step 5) installs and builds nothing: it fetches the commit from the artifact, checks that it changes only the
areas' `sources/` and `data/`, and pushes it. The shell they run is in `scripts/refresh/`; `scripts/ci.sh` lints it
and dry-runs it against a local repository (`scripts/test-refresh.sh`).

Only a run on `main` publishes. A run started by hand on another branch does everything else and keeps its
downloads in the artifact. The push is made as `github-actions[bot]` straight to `main`, so `main` must not get
branch protection or a ruleset that requires a pull request; if it does, every refresh with new data fails at the
push. The pull request for new text needs **Settings › Actions › General › "Allow GitHub Actions to create and
approve pull requests"**; while that is off, the run pushes the branch and fails with a link to open the pull request
yourself.

**When it passes**, nothing is needed, unless it opened a pull request: look at the new text it lists (and the
pages that show it, on the branch's Vercel preview) and merge it. Look over the `Data refresh` commit on `main` now
and then: the "Large revisions to growth" section of `gdp/data/validation_report.md` lists big revisions for review.

**When it fails:**

1. Open the run from the email (or the Actions tab) and read the failed step's log. The artifact has each area's
   `data/validation_report.md` and any new downloads (under `files/`).
2. Reproduce it locally: run the same command in the area's `pipeline/` folder (`--refresh-api`). It downloads the same files.
3. Fix it: compare the failing figure with the source's own publication, then fix the code or add an allowed exception
   with its reason (each area's README says where). A message saying a query returned no rows although it had data
   before usually means the source is having trouble; the saved file is kept, so wait and run again.
4. Commit the area's `sources/` and `data/` with the fix on a branch, and open a pull request ([Local CI](#local-ci)).

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
4. Commit the area's `data/` and `sources/` (the downloaded files and `manifest.json`) together with any code changes
   on a branch, and open a pull request ([Local CI](#local-ci)). A branch gets a Vercel preview; `main` deploys the
   live site.

## Local CI

There is no CI on GitHub. Every change goes through a branch and a pull request, and you run `scripts/ci.sh` on the
branch before merging it into `main`:

```bash
scripts/ci.sh <branch>
```

It checks out that commit in a temporary folder (your working folder is not touched) and passes only if:

- every area's pipeline rebuilds `data/` from the committed sources with every check passing;
- the rebuilt `data/` matches what is committed, apart from the build time (`generated_at`);
- the build changes no committed file in `sources/` and writes no new files;
- the Python code passes `ruff check` (`ruff.toml`; to run it yourself: `uvx ruff@0.17.4 check .`);
- the workflow passes actionlint and every `.sh` file ShellCheck (versions pinned in `scripts/ci.sh`), and the
  weekly refresh's scripts pass their dry run (`scripts/test-refresh.sh`: a local repository, `gh` stubbed, no
  network);
- every area's tests pass, and the shared pipeline code's;
- the site type-checks, passes its tests (`npm test`, if `site/package.json` has one) and builds. The build's own
  gate (`site/scripts/copy-data.mjs`) also checks every area's `validation_summary.json`: it must say PASSED, and
  each data file's SHA-256, with its `generated_at` left out, must match the one the checks recorded.

Running a pipeline's tests rewrites its `data/` files with only a new `generated_at`; discard those changes rather
than committing them (the hashes leave `generated_at` out, so they never trip the gate).

It downloads no data (npm and uv may download packages) and takes about 10 to 15 minutes, most of it the budget
tests. Only the weekly refresh pushes to `main` directly, and it runs the same script on its commit first.

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
2. If it is refreshed weekly, make the area's `--refresh-api` re-download it, with the area's `save()`
   (`pipeline_common.download.save`, which keeps the old file as a snapshot) and the same guard against data that vanishes, and extend `tests/test_fetch.py`. If its download is
   slow, raise the area's `timeout` in `.github/workflows/data-refresh.yml`.
3. Update the table and the area's README, as above.

### A new area

1. Create `<area>/` with `pipeline/`, `data/` and `sources/`, following `gdp/` (fetch → build → checks). Add
   `pipeline-common` to the pipeline's dependencies as a path dependency (copy `[tool.uv.sources]` from
   `gdp/pipeline/pyproject.toml`), and write the checks with its `Report`, which writes `data/validation_report.md`
   and the `data/validation_summary.json` the site reads. Code that more than one area needs goes in
   `shared/pipeline/pipeline_common/`, with tests in `shared/pipeline/tests/`; area-specific code stays in the area.
2. In the site: add the area to `AREAS` in `site/scripts/copy-data.mjs` and its `data/` folder to `PATHS` in
   `site/scripts/vercel-ignore-build.sh`; a data module in `site/src/lib/<area>/`;
   pages in `site/src/pages/<area>/`, including a sources page listing its downloads and check results (copy
   `site/src/pages/gdp/sources/index.astro`). In `site/src/layouts/Base.astro`, add it to the `AREAS` list that
   works out the area from the URL, to `tabs` and `subnav`, to `AREA_LABEL`, and give it a footer paragraph like
   the other areas'. Add it to the `areas` list in `site/src/pages/about/index.astro` (its check results), to the
   links on `site/src/pages/404.astro` and the home page's area sections (`site/src/pages/index.astro`), to the
   default page description in `Base.astro`, and to the Pages table and data folders in `site/README.md`.
3. Charts that combine areas go on the home page (`site/src/pages/index.astro`).
4. Add the area to `AREAS` in `scripts/ci.sh`, and to the folder table at the top of this README.
5. Give its `__main__.py` the shared options (`pipeline_common.cli.parser`) and call `pipeline_common.log.setup()`
   first. If any of its sources are refreshed weekly, its `--refresh-api` re-downloads only those (with tests in
   `tests/test_fetch.py`); add a step for it to `.github/workflows/data-refresh.yml` that runs it with
   `scripts/refresh/run-area.sh` and its own time limit, and add the area wherever the workflow names `gdp` and
   `jobs-prices` (the commit step's `env` and arguments, the pack step's arguments, the final failure check).
6. Add its datasets to the table, as above.

## Deployment

Vercel, project Root Directory `site` (it reads each area's `data/` folder, so "Include files
outside the root directory" must stay on).

Each deployment stores a full copy of the built site (about 100 MB, mostly the download files in `data/`), so
`site/vercel.json` skips the ones that would change nothing: Dependabot branches never deploy, and
`site/scripts/vercel-ignore-build.sh` skips a commit when nothing in `site/` or any area's `data/` folder changed
since the branch's last deployment. A new area's `data/` folder must be added to that script's list.

## Terms

| Term | Meaning |
|---|---|
| MoSPI | Ministry of Statistics and Programme Implementation, which publishes the national accounts, PLFS, CPI and HCES |
| NAS | National Accounts Statistics: MoSPI's GDP and related accounts (`gdp_pipeline --refresh-api` re-downloads them), and its yearly publication of that name |
| Base year | The year whose prices the constant-price figures use; MoSPI moves it every decade or so (2011-12, now 2022-23), and series on different bases are never mixed |
| GVA, GSVA | Gross value added (output less inputs) for India, and for a state; GDP = GVA + taxes − subsidies on products |
| GSDP, NSDP | Gross and net state domestic product: a state's GDP, and its GDP less depreciation |
| BE, RE, Actuals | A budget's Budget Estimate for the coming year, the Revised Estimate a year later, and the Actuals two years later |
| PLFS | Periodic Labour Force Survey, MoSPI's survey of jobs and unemployment |
| Usual status, CWS | PLFS's two ways of counting work: usual status is activity over the past year (annual figures); current weekly status (CWS) is the past seven days (quarterly and monthly figures) |
| CPI, CPI-AL/RL | Consumer Price Index; the Labour Bureau's CPI for agricultural and rural labourers |
| HCES | Household Consumption Expenditure Survey |

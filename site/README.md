# India Data Review — website

Live: https://india-data-review.k4tech.in

A static, mobile-first website built from the verified datasets in `../budget/data`, `../gdp/data` and `../jobs-prices/data`
(produced by each area's pipeline). Every page is pre-rendered; charts are SVG drawn at build time, with a
small script for hover/touch/keyboard readouts and a table view under every chart.

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # static site in dist/ (refuses to build unless every area's checks passed)
npm run check    # type check
```

## Pages

| Path | What |
|---|---|
| `/` | Home: headline figures from each area; the Centre's budget as % of GDP; tax growth vs GDP growth; consumer inflation vs the GDP deflator; Budget GDP assumption vs outcome |
| `/budget/` and `/budget/years/<year>/` | One budget year: headline figures, where each rupee comes from and goes, announced vs outcome, largest schemes |
| `/budget/trends/` | 2000-01 to today: borrowing, spending vs revenue, interest burden, capital spending |
| `/budget/taxes/` | Tax mix over time, income vs corporation tax, states' share, latest budget in detail |
| `/budget/ministries/`, `/budget/ministries/<id>/` | Spending by ministry; each ministry's history, departments and schemes |
| `/budget/schemes/`, `/budget/schemes/<slug>/` | Searchable list of ~1,400 schemes; each scheme's history with links to the source PDFs |
| `/budget/sources/` | Budget sources, checks, problems found in official files, downloads |
| `/gdp/` | Latest growth, GDP, latest quarter; real growth since 1951-52 |
| `/gdp/growth/`, `/gdp/revisions/`, `/gdp/forecasts/` | Growth since 2000-01; every estimate stage; forecasts vs outcome |
| `/gdp/sectors/`, `/gdp/spending/`, `/gdp/quarters/` | GVA by sector; spending, investment and saving; quarterly growth |
| `/gdp/sources/` | GDP sources, checks, problems found in the official data, downloads |
| `/jobs-prices/` | Unemployment, women in work, inflation, spending per person; monthly inflation |
| `/jobs-prices/jobs/`, `/jobs-prices/work/` | PLFS: participation and unemployment by sex, age, area, education, group, state; industry, type of work, job conditions, earnings |
| `/jobs-prices/prices/`, `/jobs-prices/spending/` | CPI inflation on both series (base 2012 to Dec 2025, base 2024 from Jan 2026) by month, year, group, division and state; CPI-AL/RL; HCES spending by state, class, item, group |
| `/jobs-prices/states/`, `/jobs-prices/sources/` | All states side by side; sources, checks, problems found, downloads |
| `/about/` | What the site is, principles, every area's check results |

Code layout: `src/lib/budget/`, `src/lib/gdp/` and `src/lib/jobs-prices/` read each area's data; `src/components/` holds the shared
charts (`components/budget/` the budget-only ones; `DotRows.astro` compares two or three values per row, such as
rural vs urban by state); `src/layouts/Base.astro` has the tabs and sub-navigation, and works out the area from
the URL. A new area also needs adding to `AREAS` in `scripts/copy-data.mjs`, which copies each area's checked
data into `public/data/<area>/` for download and stops the build if a validation report does not say PASSED.

## How numbers are chosen

The data modules only pick, add up, divide and label published values; they never change a number.
Budget: a year shows Actual figures if published, else Revised, else Budget Estimates. GDP: levels from
MoSPI's 2011-12 and 2022-23 series are never mixed; long-run charts use the 2011-12 base. Home-page ratios
divide a budget figure by MoSPI's GDP (2011-12 base) for the same year, and say so. Jobs and prices: annual job
figures use usual status for people aged 15 and over, quarterly and monthly ones current weekly status, never mixed
in one chart; figures the pipeline left out (failed checks) are gaps, not zeros; the two Consumer Price Index series
are shown side by side and never joined; yearly inflation is the change in the average of twelve monthly indices,
and earnings "after inflation" divide by the same year's average index; household spending excludes items
received free unless a chart says otherwise.

Note for editing `.astro` files: avoid a non-null `!` directly before a division (`x! / y`) in frontmatter —
the type checker's converter reads it as the start of a regular expression and loses the end of the
frontmatter.

## Deployment

Hosted on Vercel (project Root Directory: `site`). The build reads each area's `data/` folder, so
Vercel's "Include files outside the root directory" setting must stay on (the default).
Every push to `main` deploys; other branches get preview URLs (behind Vercel's login). Vercel runs no
pipeline: it builds from the `data/` folders committed to the repository, so data updates are run locally and
committed (see the root README).

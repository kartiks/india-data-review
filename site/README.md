# India Data Review — website

Live: https://india-data-review.k4tech.in

A static, mobile-first website built from the verified datasets in `../budget/data` and `../gdp/data`
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
| `/` | Home: headline figures from each area; the Centre's budget as % of GDP; tax growth vs GDP growth; Budget GDP assumption vs outcome |
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
| `/about/` | What the site is, principles, both areas' check results |

Code layout: `src/lib/budget/` and `src/lib/gdp/` read each area's data; `src/components/` holds the shared
charts (`components/budget/` the budget-only ones); `src/layouts/Base.astro` has the tabs and sub-navigation,
and works out the area from the URL.

## How numbers are chosen

The data modules only pick, add up, divide and label published values; they never change a number.
Budget: a year shows Actual figures if published, else Revised, else Budget Estimates. GDP: levels from
MoSPI's 2011-12 and 2022-23 series are never mixed; long-run charts use the 2011-12 base. Home-page ratios
divide a budget figure by MoSPI's GDP (2011-12 base) for the same year, and say so.

Note for editing `.astro` files: avoid a non-null `!` directly before a division (`x! / y`) in frontmatter —
the type checker's converter reads it as the start of a regular expression and loses the end of the
frontmatter.

## Deployment

Hosted on Vercel (project Root Directory: `site`). The build reads `../budget/data` and `../gdp/data`, so
Vercel's "Include files outside the root directory" setting must stay on (the default). `vercel.json`
redirects the old domain (india-budget-review.k4tech.in) path-for-path to `/budget/…` on the new one.
Every push to `main` deploys; other branches get preview URLs.

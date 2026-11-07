# India Data Review — website

Live: https://india-data-review.k4tech.in

A static, mobile-first website built from the verified datasets in `../budget/data`, `../gdp/data` and `../jobs-prices/data`
(produced by each area's pipeline). Every page is pre-rendered; charts are SVG drawn at build time, with a
small script for hover/touch/keyboard readouts and a table view under every chart.

```bash
npm ci
npm run dev      # http://localhost:4321
npm run build    # static site in dist/ (refuses to build unless every area's checks passed on its current data)
npm run preview  # serve dist/ locally
npm run check    # type check
```

## Pages

| Path | What |
|---|---|
| `/` | Home: headline figures from each area; the Centre's budget as % of GDP; tax growth vs GDP growth; consumer inflation vs the GDP deflator; Budget GDP assumption vs outcome |
| `/budget/` and `/budget/years/<year>/` | One budget year: headline figures, where each rupee comes from and goes, announced vs outcome, largest schemes |
| `/budget/years/` | Every budget year, and where the year picker lands without JavaScript |
| `/budget/trends/` | 2000-01 to today: borrowing, spending vs revenue, interest burden, capital spending |
| `/budget/taxes/` | Tax mix over time, income vs corporation tax, states' share, latest budget in detail |
| `/budget/ministries/`, `/budget/ministries/<id>/` | Spending by ministry; each ministry's history, departments and schemes |
| `/budget/schemes/`, `/budget/schemes/<slug>/` | Searchable list of ~1,400 schemes; each scheme's history with links to the source PDFs |
| `/budget/schemes-index.json` | The schemes page's search index, one compact row per scheme (not a page) |
| `/budget/sources/` | Budget sources, checks, problems found in official files, downloads |
| `/gdp/` | Latest growth, GDP, latest quarter; real growth since 1951-52 |
| `/gdp/growth/`, `/gdp/revisions/`, `/gdp/forecasts/` | Growth since 2000-01; every estimate stage; forecasts vs outcome |
| `/gdp/sectors/`, `/gdp/spending/`, `/gdp/quarters/` | GVA by sector; spending, investment and saving; quarterly growth |
| `/gdp/per-person/` | GDP, GNI, net national income and household spending per person, both series, with the population used |
| `/gdp/states/` | State accounts: GSDP, growth, income per person and sector shares by state, with an India map and the full table |
| `/gdp/sources/` | GDP sources, checks, problems found in the official data, downloads |
| `/jobs-prices/` | Unemployment, women in work, inflation, spending per person; monthly inflation |
| `/jobs-prices/jobs/`, `/jobs-prices/work/` | PLFS: participation and unemployment by sex, age, area, education, group, state; industry, type of work, job conditions, earnings |
| `/jobs-prices/prices/`, `/jobs-prices/spending/` | CPI inflation on both series (base 2012 to Dec 2025, base 2024 from Jan 2026) by month, year, group, division and state; CPI-AL/RL; HCES spending by state, class, item, group |
| `/jobs-prices/states/`, `/jobs-prices/sources/` | India map coloured by a chosen measure, with the full table below; sources, checks, problems found, downloads |
| `/about/` | What the site is, principles, every area's check results |
| `/404.html` | Page not found, with links into each area (`src/pages/404.astro`) |

Code layout: the areas are listed once, in `src/data/areas.json` (id, tab label, full name), which the tabs, the
About page, the build gate, `scripts/vercel-ignore-build.sh` and the root `scripts/ci.sh` all read;
`src/lib/area-data.ts` gives the list and reads a file from an area's `data/` folder. `src/lib/budget/`,
`src/lib/gdp/` and `src/lib/jobs-prices/` read each area's data (`src/lib/gdp/data.ts` the
national accounts in `gdp.json`, `src/lib/gdp/states.ts` the state accounts in `states.json` and India's figures on
the same base); `src/lib/format.ts`, `chart.ts`, `line-plot.ts` and `url.ts` are shared helpers (`link()` adds the
site's base path to internal links); `src/components/` holds the shared
charts (`components/budget/` the budget-only ones; `DotRows.astro` compares two or three values per row, such as
rural vs urban by state; `OrDash.astro` shows "–", read as "no data", for an empty cell); `src/lib/slots.ts` fixes
the colour slot of the old and new GDP and CPI series, so each keeps one colour on every page; `src/lib/states.ts`
turns state names into keys the same way as the jobs-prices pipeline (both are tested against
`shared/fixtures/state-names.json`); `src/layouts/Base.astro` has the tabs and sub-navigation, and works out the area from
the URL. Each area's Sources page is a `SourcesPage.astro` (check results, the full report, downloads) with the
area's own text in its slots. Shared page parts are styled once in `src/styles/global.css` (`.lede`, `.card`,
`.note-card`, `.link-card` via `LinkCard.astro`, `details.table-view`, `.source`). Page logic that is more than
picking figures goes in `src/lib/` with tests in `test/`, and browser scripts longer than a few lines in
`src/scripts/`, imported from a `<script>` so Astro bundles them. `StateMap.astro` draws the India map from `src/data/india-states.json`: DataMeet's state boundaries
(CC BY 4.0, following the Survey of India's map) simplified by `scripts/make-india-map.py`, whose header says how to
redo it; the page must credit DataMeet.

`scripts/copy-data.mjs` (run before every `dev` and `build`) copies each area's checked data into
`public/data/<area>/` for download. It stops the build if an area's `data/validation_summary.json` is missing or
does not say PASSED, or if any data file differs from the SHA-256 the summary recorded when the checks ran (so data
edited or rebuilt without its checks cannot go live); it names the file. The hashes leave out each file's
`generated_at` (the build time), so rebuilding the same data, as the tests do, never trips it. Pages and the gate read
the check results through `src/lib/validation.ts`, never by parsing `validation_report.md`. Adding an area: see the
root README's checklist.

## How numbers are chosen

The data modules only pick, add up, divide and label published values; they never change a number.
Budget: a year shows Actual figures if published, else Revised, else Budget Estimates. GDP: levels from
MoSPI's 2011-12 and 2022-23 series are never mixed; long-run charts use the 2011-12 base. Home-page ratios
divide a budget figure by MoSPI's GDP (2011-12 base) for the same year, and say so. GDP per person: MoSPI's totals
(the latest estimate of each year) divided by India's population on 1 October of the year, as MoSPI does; the
headline year is the latest of the 2022-23 series whose population is known, and growth per person comes from
constant-price levels in the same series. States: MoSPI's state accounts, on the 2011-12 base only, compared with
India's national accounts on that same base; every comparison uses one year, the latest in which the states that
have published made up at least 97% of the states' economy the year before; GSDP that MoSPI does not publish for a
state is worked out as GSVA + taxes − subsidies and marked, as is growth worked out from the levels; average growth
is from constant-price GSDP; income per person is NSDP per person at current prices. Jobs and prices: annual job
figures use usual status (activity over the past year) for people aged 15 and over, quarterly and monthly ones
current weekly status (the past seven days), never mixed
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
Every push to `main` deploys; other branches get preview URLs (behind Vercel's login). Two exceptions, to keep
deployment storage down (each deployment is a ~100 MB copy): Dependabot branches never deploy (`git.deploymentEnabled`
in `vercel.json`), and `scripts/vercel-ignore-build.sh` skips a commit that changed nothing in `site/` or any area's
`data/` since the branch's last deployment (it takes the areas from `src/data/areas.json`). Vercel runs no
pipeline: it builds from the `data/` folders committed to the repository, so data updates are run locally and
committed (see the root README). `vercel.json` also sets security headers on every page (no framing, no MIME
sniffing, a strict referrer policy, and browser features such as the camera turned off).

Content-Security-Policy: `security.csp` in `astro.config.mjs` puts a CSP `<meta>` tag on every page, with the hash
of every script and stylesheet Astro emits; only the site's own origin may load anything. A script that must run
inline, unbundled (before first paint, say), goes in `src/scripts/inline/` and is rendered with
`InlineScript.astro`, which adds its hash; a plain `<script is:inline>` would be blocked. Style attributes are
allowed (charts set sizes and colours with them). `frame-ancestors`, which a `<meta>` tag cannot set, is in the
`vercel.json` header. The policy is not applied by `npm run dev`: check it with `npm run build` and
`npm run preview` (violations show in the browser console).

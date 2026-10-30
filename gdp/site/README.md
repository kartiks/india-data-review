# India GDP Review — website

A static, mobile-first website built from the verified datasets in `../data` (produced by `../pipeline`).
Every page is pre-rendered; charts are SVG drawn at build time, with a small script for hover/touch/keyboard
readouts and a table view under every chart. Components and styles are shared in spirit with the budget site
(`../../web/site`).

```bash
npm install
npm run dev      # http://localhost:4321 (or --port 4322 alongside the budget site)
npm run build    # static site in dist/ (refuses to build if the data checks did not pass)
npm run check    # type check
```

## Pages

| Path | What |
|---|---|
| `/` | Latest growth, GDP, latest quarter, Budget assumption; real growth since 1951-52 |
| `/growth/` | Real and nominal growth since 2000-01, GDP size in both series, every year's figure |
| `/revisions/` | Each year's growth from first estimate to latest, every estimate stage |
| `/forecasts/` | Economic Survey and RBI forecasts vs outcome; RBI's path within each year; Budget GDP assumption vs outcome |
| `/sectors/` | Shares of GVA by sector since 2000-01, latest growth by sector, sub-sectors, sector growth over time |
| `/spending/` | Household, government, investment and net exports as % of GDP; saving rate; investment and saving by sector |
| `/quarters/` | Quarterly growth in both series; latest quarter by sector |
| `/about/` | Sources, checks, problems found in the official data, downloads |

## How numbers are chosen

`src/lib/data.ts` only picks, adds up and labels published values. Levels from the 2011-12 and 2022-23 series
are never mixed; long-run charts use the 2011-12 base (back series to 2010-11, then the latest estimate).
Growth rates are as MoSPI published them, except the back series, whose growth is worked out from its levels.

Note for editing `.astro` files: avoid a non-null `!` directly before a division (`x! / y`) in frontmatter —
the type checker's converter reads it as the start of a regular expression and loses the end of the
frontmatter. Use `share()` or optional chaining instead.

## Deployment

Same setup as the budget site: Vercel with Root Directory `site`, reading `../data` at build time.
`astro.config.mjs` defaults the site URL to `https://india-gdp-review.k4tech.in` (a placeholder; set
`SITE_URL` to the real address).

# India Budget Review — website

Live: https://india-budget-review.k4tech.in

A static, mobile-first website built from the verified datasets in `../data`
(produced by `../pipeline`). Every page is pre-rendered; charts are SVG drawn
at build time, with a small script for hover/touch/keyboard readouts and a
table view under every chart.

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # static site in dist/ (refuses to build if the data checks did not pass)
npm run check    # type check
```

## Pages

| Path | What |
|---|---|
| `/` and `/years/<year>/` | One budget year: headline figures, where each rupee comes from and goes, announced vs outcome, largest schemes |
| `/trends/` | 2000-01 to today: borrowing, spending vs revenue, interest burden, capital spending |
| `/taxes/` | Tax mix over time, income vs corporation tax, states' share, latest budget in detail |
| `/ministries/`, `/ministries/<id>/` | Spending by ministry; each ministry's history, departments and schemes |
| `/schemes/`, `/schemes/<slug>/` | Searchable list of ~1,400 schemes; each scheme's history with links to the source PDFs |
| `/about/` | Sources, how the data is checked, problems found in official files, downloads |

## How numbers are chosen

`src/lib/data.ts` only picks, sums and labels published values; it never
changes a number. A year shows Actual figures if published, else Revised,
else Budget Estimates, and all figures on a year page come from the same
estimate type. Notes attached to figures in the data (e.g. image-read values,
one-off debt transactions) are shown next to them.

Charts use the validated categorical palette (light and dark), thin marks,
legends for 2+ series, hollow markers for estimates, and a table view.

## Deployment

Hosted on Vercel (project Root Directory: `site`). `vercel.json` sets the
build; the build reads `../data`, so Vercel's "Include files outside the root
directory" setting must stay on (the default). Every push to `main` deploys;
other branches get preview URLs. For a host that serves under a sub-path (e.g.
GitHub Pages), set `SITE_BASE=/<repo>` and `SITE_URL` when building.

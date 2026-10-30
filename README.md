# India Data Review

**Live site: https://india-data-review.k4tech.in** (formerly India Budget Review, india-budget-review.k4tech.in;
old links redirect)

India's economy and public finances from official data, checked automatically. One website with an area per
type of data, and a shared home page with charts that use more than one area.

| Folder | What |
|---|---|
| [`budget/`](budget/README.md) | Union Budget 2000-01 to today: pipeline, verified data, source documents |
| [`gdp/`](gdp/README.md) | GDP and national accounts (MoSPI), the Budget's GDP assumption, Economic Survey and RBI forecasts |
| [`site/`](site/README.md) | The website: `/` home, `/budget/…`, `/gdp/…`, `/about/` |

Each data area is self-contained: its own `pipeline/` (a Python package run with uv), `data/` (the verified
datasets the site reads) and `sources/` (every downloaded file, listed in `sources/manifest.json` with its
URL and SHA-256). The site refuses to build unless every area's `data/validation_report.md` says PASSED.

> This repository previously held an Android app (Expo/React Native), preserved at the tag
> `android-app-final`. The GDP area was developed in a separate repository; its history is merged here.

## Run it

```bash
(cd budget/pipeline && uv run python -m budget_pipeline)   # ~3 min; --fetch downloads anything missing
(cd gdp/pipeline && uv run python -m gdp_pipeline)         # --refresh after each MoSPI release
(cd site && npm install && npm run build)                  # or: npm run dev
```

## Adding a new area

1. Create `<area>/` with `pipeline/`, `data/` and `sources/`, following `gdp/` (fetch → build → checks,
   writing `data/validation_report.md`).
2. Add the area to `AREAS` in `site/scripts/copy-data.mjs`, a data module in `site/src/lib/<area>/`, pages in
   `site/src/pages/<area>/`, and a tab and sub-navigation in `site/src/layouts/Base.astro`.
3. Charts that combine areas go on the home page (`site/src/pages/index.astro`).

## Deployment

Vercel, project Root Directory `site` (it reads `../budget/data` and `../gdp/data`, so "Include files
outside the root directory" must stay on). `site/vercel.json` redirects every path on the old domain
india-budget-review.k4tech.in to the same page under `/budget/` on india-data-review.k4tech.in.

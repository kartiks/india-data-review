# GDP data

The GDP area of [India Data Review](../README.md): India's GDP and national accounts from official
sources, checked automatically. This folder holds the data pipeline (`pipeline/`), the datasets (`data/`)
and the downloaded source files (`sources/`). The website is in `../site/` (pages under `/gdp/`).

## What's covered

- **National accounts** from MoSPI's official data service (api.mospi.gov.in, behind esankhyiki.mospi.gov.in):
  - 2011-12 base, 2011-12 to 2025-26, **every estimate stage** (first and second advance, provisional,
    first/second/third revised, final), annual and quarterly;
  - MoSPI's **back series** on the 2011-12 base, 1950-51 to 2011-12;
  - the **new 2022-23 base** (released 27 Feb 2026), latest estimates only.
  - GDP, GVA by industry and sub-industry, spending components, national income, investment and saving by
    institutional sector.
- **Union Budget GDP assumption**, Budgets 2011-12 to 2026-27 (Budget at a Glance).
- **Forecasts**: the Economic Survey's projection for each year 2011-12 to 2026-27, and every RBI monetary
  policy projection for the same years (93 statements), each with the sentence it was quoted from.

## Run it

```bash
cd pipeline
uv run python -m gdp_pipeline             # build data from saved sources and run all checks
uv run python -m gdp_pipeline --fetch     # also download anything missing
uv run python -m gdp_pipeline --refresh   # re-download everything (run after each MoSPI release)
uv run pytest
```

The command exits with an error if any check fails, and the website (`../site/`) refuses to build unless
`data/validation_report.md` says PASSED.

**Run `--refresh` after every MoSPI release.** MoSPI's data service keeps only the latest estimate for the
new 2022-23 series and for quarters. When a re-download differs, the old file is kept in
`sources/snapshots/<date>/`, so the revision history of the new series builds up over time.

## What's in `data/`

| File | What it is |
|---|---|
| `gdp.json` | Everything the site uses: national accounts by series → frequency → year → estimate stage; the long-run series; Budget assumptions; forecasts; build notes |
| `national_accounts.csv` | Every row MoSPI published, one value per line, names as printed plus our ids, source URL and SHA-256 |
| `validation_report.md` | Every check, and the reason for every allowed exception |

Values are ₹ crore; growth rates are %. `cur` = current prices (nominal), `con` = constant prices (real).

## Checks

Accounting identities in every estimate (industries add up to GVA, GDP = GVA + net taxes, NDP, GNI, GNDI,
investment and saving by sector), published growth rates against levels, quarters against years, the back
series against the current series, the Budget's stated growth, and every forecast quote found in its
downloaded document. Problems found in the official data are documented in the report and on the site's
Sources page: a ₹ lakh unit label on figures that are in ₹ crore, a row labelled "1999", duplicate
"Additional Revision" rows, inconsistent early net-tax figures, and the back series' non-additivity before 2004-05.

## Forecast sources

`pipeline/gdp_pipeline/forecast_sources/*.json` are listed by hand, each with the exact sentence, the URL and
the page. The pipeline downloads each document and fails if the sentence or its numbers are not there. The
IMF's historical WEO forecasts are not included yet: imf.org refuses automated downloads, so that file would
need to be downloaded by hand into `sources/`.

## Not yet covered

- A rural/urban split (MoSPI does not publish GDP by rural/urban area each year; rural/urban CPI, PLFS and
  HCES indicators are the planned substitute).
- Revision history for 2000-01 to 2010-11 (earlier base years, from press releases).
- State GDP (MoSPI's API indicators 23-34).

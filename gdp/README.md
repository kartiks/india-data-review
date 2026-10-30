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

### Adding a forecast

**After each RBI monetary policy statement** (about every two months), add a record to `rbi.json` for every year
it projects:

```json
{
 "fiscal_year": "2026-27",
 "statement": "Monetary Policy Statement, 2026-27 – Resolution of the MPC, October 5 to 7, 2026",
 "date": "2026-10-07",
 "measure": "GDP",
 "value": 7.1,
 "quote": "real GDP growth for 2026-27 is projected at 7.1 per cent",
 "url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63742",
 "is_first": false,
 "is_last": false,
 "notes": "Anything a reader needs: other documents, why a flag is set."
}
```

- `quote` is copied exactly from the document at `url`; the numbers in it must be the numbers in the record.
- `measure` is `GDP` or `GVA`, as the statement says.
- `value` is a single projection; use `low` and `high` for a range, and `value_text` with `value: null` for words
  such as "a little below 5 per cent".
- `is_first` marks a year's first projection; `is_first_april_policy` the first one in the April policy, which the
  site uses as the year's starting forecast.
- `is_last` marks the final projection before the year's outcome. While a year is still running, its latest
  record has `is_last: false` and `is_latest_available: true`; move that flag when a newer statement comes.

**After each Economic Survey** (late January), add a record to `economic_survey.json` with `fiscal_year`, `survey`,
`published_date`, `kind` (`point` or `range`), `low` and `high` (the same number for a point), `quote`, `url`,
`pdf_page`, the nominal fields (`nominal_low`, `nominal_high`, `nominal_quote`, or `null`) and `notes`. A projection
stated in two places can add `quote_2`, with `quote_2_url` and `quote_2_pdf_page` if it is in another document.
The survey's chapters move from `indiabudget.gov.in/economicsurvey/` to `indiabudget.gov.in/budget<year>/economicsurvey/`
when the next survey comes out; the downloaded copy is kept, so the record's `url` only needs updating if the file
is downloaded again.

Then run `uv run python -m gdp_pipeline --fetch`: it downloads the new documents and checks every quote.

### When a check fails after a refresh

Allowed exceptions are written in `pipeline/gdp_pipeline/checks.py`: one-off cases in `KNOWN_EXCEPTIONS` and whole
families of known differences in `KNOWN_RULES`, each with its reason. Errors found in MoSPI's rows themselves
(unit labels, odd years, duplicate rows) are handled in `build.py` and listed on the site's Sources page.

## Not yet covered

- A rural/urban split. MoSPI does not publish GDP by rural/urban area each year; the rural and urban indicators it
  does publish (consumer prices, jobs, household spending) are in the [jobs and prices area](../jobs-prices/README.md).
- Revision history for 2000-01 to 2010-11 (earlier base years, from press releases).
- State GDP (MoSPI's API indicators 23-34).

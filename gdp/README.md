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
- **State accounts** from the same service: for each state and union territory, 2011-12 to 2025-26 on the
  2011-12 base (latest estimate only; MoSPI publishes no state figures on the 2022-23 base yet): GSDP and NSDP,
  income per person, growth, and value added by industry and sub-industry. Shown on the site's GDP › States page.
- **Union Budget GDP assumption**, Budgets 2011-12 to 2026-27 (Budget at a Glance).
- **Forecasts**: the Economic Survey's projection for each year 2011-12 to 2026-27, and every RBI monetary
  policy projection for the same years (93 statements), each with the sentence it was quoted from.

## Run it

```bash
cd pipeline
uv run python -m gdp_pipeline             # build data from saved sources and run all checks
uv run python -m gdp_pipeline --fetch     # also download anything missing
uv run python -m gdp_pipeline --refresh   # re-download everything, including budget and forecast documents
uv run python -m gdp_pipeline --refresh-nas  # re-download only MoSPI's API files (what the weekly refresh runs)
uv run pytest
```

The command exits with an error if any check fails, and the website (`../site/`) refuses to build unless
`data/validation_report.md` says PASSED.

**MoSPI's national and state accounts are refreshed every week** by a GitHub Action that runs `--refresh-nas`, commits what
changed and pushes it to `main` once every check and the local CI pass (see
[Keeping the data up to date](../README.md#keeping-the-data-up-to-date)). MoSPI's data service keeps only the latest
estimate for the new 2022-23 series and for quarters. When a re-download differs, the old file is kept in
`sources/snapshots/<date>/`, so the revision history of the new series builds up over time.

Not refreshed by it, and updated by hand: the Budget's GDP assumption (with each new budget) and the Economic Survey
and RBI growth projections ([Adding a forecast](#adding-a-forecast)).

## What's in `data/`

| File | What it is |
|---|---|
| `gdp.json` | Everything the site uses: national accounts by series → frequency → year → estimate stage; the long-run series; Budget assumptions; forecasts; build notes |
| `national_accounts.csv` | Every row MoSPI published, one value per line, names as printed plus our ids, source URL and SHA-256 |
| `states.json` | The state accounts the site uses: base → state → year, levels in ₹ crore, per-person figures in ₹ |
| `state_accounts.csv` | Every state-accounts row MoSPI published, one value per line, as printed, with our ids and the source URL; rows left out are marked |
| `validation_report.md` | Every check, and the reason for every allowed exception |

Values are ₹ crore; growth rates are %. `cur` = current prices (nominal), `con` = constant prices (real).

## Checks

Accounting identities in every estimate (industries add up to GVA, GDP = GVA + net taxes, NDP, GNI, GNDI,
investment and saving by sector), published growth rates against levels, quarters against years, the back
series against the current series, the Budget's stated growth, and every forecast quote found in its
downloaded document. Problems found in the official data are documented in the report and on the site's
Sources page: a ₹ lakh unit label on figures that are in ₹ crore, a row labelled "1999", duplicate
"Additional Revision" rows, inconsistent early net-tax figures, and the back series' non-additivity before 2004-05.

### State accounts

`pipeline/gdp_pipeline/states.py` builds and checks them. For every state, year and price basis: GSDP and NSDP add
up from value added, taxes and subsidies on products; industries add up to total value added and sub-industries to
their industry; every published growth rate follows from the levels (allowing for the levels' rounding, which
matters for small states); the two tables of income per person agree, and GSDP and NSDP per person imply the same
population; every state is one of the 34 in `KNOWN_STATES` and each appears on the 2011-12 base (a newer base may
fill up state by state: the report lists who is not on it yet); no row is published twice with
different values; and a state with value added always gets a GSDP. These checks fail the run.

For review only (listed in the report, never a failure): the states' GSDP against India's GDP on the same base, in
each year whose national figure is at least provisional and whose reporting states made up 97% of the states'
economy the year before (98-103% so far). It is not a hard check because the national 2011-12 series stopped in
February 2026 while the states keep revising theirs, so the two will drift apart. The report also lists any
known exception that is no longer needed.

What MoSPI publishes, and what is done with it:

- Value added, taxes and subsidies are labelled ₹ lakh (correctly, unlike the national table) and divided by 100.
- There is no All-India row; the site compares the states with the national accounts on the same base.
- MoSPI's GSDP table leaves out Assam, Haryana, Ladakh and Nagaland, which its value-added table covers. Their
  GSDP is worked out as GSVA + taxes - subsidies (MoSPI's definition; for every other state the two agree) and
  marked `derived`; their growth is worked out from those levels and marked `published: false`. These derived
  figures match the RBI's Handbook of Statistics on Indian States, which compiles the same state accounts. As there
  is no published total to check them against, the population they imply with MoSPI's GSDP per person must move by
  less than 8% a year (MoSPI's own per-person figures can move a few percent when population projections change; a
  missing tax figure or a lakh/crore slip moves it far more).
- Jammu & Kashmir's figures up to 2018-19 include Ladakh (a separate union territory from October 2019; the implied
  population falls 1.4% in 2019-20). The site marks J&K's growth since 2011-12 (`BOUNDARY` in
  `site/src/lib/gdp/states.ts`).
- A net figure that is not below the gross one is a copying error and is left out. MoSPI's net value added table
  repeats Karnataka's gross value added, and its second table of income per person repeats Karnataka's GSDP per
  person; both are listed, with reasons, in `KNOWN_EXCEPTIONS` in `states.py`. A new case fails the checks until it
  is looked at.
- Chhattisgarh publishes no subsidies on products; its GSDP equals value added plus taxes (and would be worked out
  that way if its GSDP were ever missing).

The site shows the 2011-12 base (`STATE_BASE` in `site/src/lib/gdp/states.ts`), for the latest year whose
reporting states made up 97% of the states' economy the year before, and names any state missing from it. When MoSPI publishes state accounts
on the 2022-23 base, the weekly refresh downloads them and the validation report says so; switch the site over
then, after checking the new figures.

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
- Revisions to state GDP before November 2026: MoSPI keeps only the latest state estimates, so the history starts
  with the weekly refresh.

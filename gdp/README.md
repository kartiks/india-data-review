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
- **Figures per person**: GDP, GNI, net national income and household spending per person, at current and constant
  prices, for the latest estimate of every year of both series from 2011-12 ([Population](#population)). Shown on
  GDP › Per person.
- **Union Budget GDP assumption**, Budgets 2011-12 to 2026-27 (Budget at a Glance).
- **Forecasts**: the Economic Survey's projection for each year 2011-12 to 2026-27, and every RBI monetary
  policy projection for the same years, each with the sentence it was quoted from (counts in
  [`data/validation_report.md`](data/validation_report.md)).

## Run it

In `pipeline/`:

```bash
uv run python -m gdp_pipeline        # build data/ and run every check; options below
uv run python -m gdp_pipeline.due    # which releases added by hand are probably out (exit 11 if any)
uv run pytest
```

The options are the same in every area ([Run it](../README.md#run-it)). Here `--refresh-api` re-downloads MoSPI's API
files, and `--refresh` also the budget, forecast and population documents (not the National Accounts Statistics
statements, which are [added by hand](#adding-a-years-population)).

**MoSPI's national and state accounts are refreshed every week**
([The weekly refresh](../README.md#the-weekly-refresh)); figures per person are worked out again from the refreshed
totals. MoSPI's data service keeps only the latest estimate for the new 2022-23 series and for quarters, so the
revision history of the new series builds up from the earlier files kept in `sources/snapshots/`: the build reads an
estimate stage (say a year's Provisional Estimate) from the newest saved file that has it once the current file no
longer does, and lists those estimates in `gdp.json` (`earlier_releases`) and the validation report. Quarters have no
stage of their own, so only their latest figures are used.

Updated by hand: the Budget's GDP assumption (step 5 of [Adding a new budget](../budget/README.md#adding-a-new-budget)),
the Economic Survey and RBI growth projections ([Adding a forecast](#adding-a-forecast)), and the population
([Adding a year's population](#adding-a-years-population)). `gdp_pipeline.due`, which the weekly refresh runs, works
out from dates which of these are probably out and not yet added; when each one counts as due is in
`pipeline/gdp_pipeline/due.py`.

## What's in `data/`

| File | What it is |
|---|---|
| `gdp.json` | Everything the site uses: national accounts by series → frequency → year → estimate stage (the latest estimate of each year has `per_person` figures in ₹); the population used and the years whose per-person figures reproduce a published one (`population.checked`); the long-run series; Budget assumptions; forecasts; build notes |
| `national_accounts.csv` | Every row MoSPI published, one value per line, names as printed plus our ids, source URL and SHA-256 |
| `per_person.csv` | GDP, GNI, net national income and household spending per person (₹, current and constant prices), with the population used, by series and year (latest estimate; earlier estimates were divided by the population known at the time, which is not kept) |
| `states.json` | The state accounts the site uses: base → state → year, levels in ₹ crore, per-person figures in ₹ |
| `state_accounts.csv` | Every state-accounts row MoSPI published, one value per line, as printed, with our ids and the source URL; rows left out are marked |
| `validation_report.md` | Every check, and the reason for every allowed exception |
| `validation_summary.json` | The same results for programs (the site reads it): PASSED or FAILED, and checks, failures and allowed exceptions per group of checks |

Levels are ₹ crore, per-person figures ₹ and growth rates %. `cur` = current prices (nominal), `con` = constant prices (real).

## Checks

Accounting identities in every estimate (industries add up to GVA, GDP = GVA + net taxes, NDP, GNI, GNDI,
investment and saving by sector), published GDP and industry growth rates against levels (exactly for the 2022-23
series), quarters against years, the back series against the current series, the Budget's stated growth, and every
forecast quote found in its downloaded document. Problems found in the official data are documented in the report
and on the site's Sources page: a ₹ lakh unit label on figures that are in ₹ crore, a row labelled "1999", duplicate
"Additional Revision" rows, inconsistent early net-tax figures, the back series' non-additivity before 2004-05, and
one mistyped GVA growth rate (2019-20, Second Advance Estimates). Every row must be in the unit its indicator is
published in (`UNITS` in `build.py`); a row in any other unit is left out and fails the checks. The back series
writes one year "1999-2000"; it is stored as "1999-00", like every other year.

### State accounts

`pipeline/gdp_pipeline/states.py` builds them and `states_checks.py` checks them. For every state, year and price basis: GSDP and NSDP add
up from value added, taxes and subsidies on products; industries add up to total value added and sub-industries to
their industry; every published growth rate follows from the levels (allowing for the levels' rounding, which
matters for small states); the two tables of income per person agree, and GSDP and NSDP per person imply the same
population; every state is in `KNOWN_STATES` and each appears on the 2011-12 base (a newer base may fill up state by
state: the report lists who is not on it yet); no row is published twice with different values; and a state with value added always gets a GSDP. These checks fail the run.

For review only (listed in the report, never a failure): the states' GSDP against India's GDP on the same base, in
each year whose national figure is at least provisional and whose reporting states made up 97% of the states'
economy the year before (the report lists each year's share). It is not a hard check because the national 2011-12
series stopped in February 2026 while the states keep revising theirs, so the two will drift apart. The report also lists any
known exception that is no longer needed.

What MoSPI publishes, and what is done with it:

- Value added, taxes and subsidies are labelled ₹ lakh (correctly, unlike the national table) and divided by 100.
- There is no All-India row; the site compares the states with the national accounts on the same base.
- MoSPI's GSDP table leaves out Assam, Haryana, Ladakh and Nagaland, which its value-added table covers. Their
  GSDP is worked out as GSVA (gross state value added) + taxes - subsidies (MoSPI's definition; for every other state the two agree) and
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
  person; both are listed, with reasons, in `KNOWN_EXCEPTIONS` in `states_checks.py`. A new case fails the checks until it
  is looked at.
- Chhattisgarh publishes no subsidies on products; its GSDP equals value added plus taxes (and would be worked out
  that way if its GSDP were ever missing).

The site shows the 2011-12 base (`STATE_BASE` in `site/src/lib/gdp/states.ts`), for the latest year whose
reporting states made up 97% of the states' economy the year before, and names any state missing from it. When MoSPI publishes state accounts
on the 2022-23 base, the weekly refresh downloads them and the validation report says so; switch the site over
then, after checking the new figures.

## Population

Figures per person divide MoSPI's totals by India's population on 1 October of the year, as MoSPI does. MoSPI's
population is not in its API, and it differs a little between the two series, so it is kept per series and year,
from:

- the official 2019 projections (*Population Projections for India and States 2011-2036*), for the 2011-12 series up
  to 2021-22;
- MoSPI's own population after that and in the 2022-23 series: printed in its yearly *National Accounts Statistics*
  per-capita statement (downloaded by hand), or implied by the per-person figures in its press notes (rows quoted in
  `pipeline/gdp_pipeline/population_sources/mospi_press_notes.json`), or else from the RBI's *Handbook of Statistics
  on the Indian Economy*, which reprints it and is also used to check it.

Which document gives each year's population, how it is chosen and how the figures are worked out: the docstring of
`pipeline/gdp_pipeline/population.py`; the
documents and how they are read: `population_read.py`; the checks ("Population and figures per person" in the
report): `population_checks.py`. A year in the API with no population yet has no per-person figures; the report
lists it (not a failure), and the site's Per person page stays on the year before and says which year is waiting.

### Adding a year's population

Each January MoSPI's First Advance Estimates add a new year. To add its population:

1. In the new press note's statement at **constant prices**, copy five rows exactly as printed, without the growth
   rates at the end: population, GDP, net national income (NNI), per capita GDP and per capita NNI.
2. Add a record to `pipeline/gdp_pipeline/population_sources/mospi_press_notes.json` like the ones there:
   `document`, `date`, `base`, `url`, `years` (the statement's columns), and a `tables` entry with `statement`,
   `pdf_page`, `prices` (`con`) and the rows.
   Check that the page's text extracts in reading order (some MoSPI statements do not; quote another one then).
3. Run `uv run python -m gdp_pipeline --fetch`. It downloads the note, checks every row and the implied population,
   and uses the newest document for each year.

**Each August or September**, when MoSPI publishes *National Accounts Statistics* (with revised totals for the
new series), add its per-capita statement, which makes the check cover the revised totals:

1. On MoSPI's page for the publication (mospi.gov.in › Publications & Reports; it needs a browser), download the
   statement *Per Capita Income, Product and Final Consumption* (Statement 1.2 in 2026) as xlsx.
2. Add an entry to `NAS_STATEMENTS` in `pipeline/gdp_pipeline/population_read.py` (`key`, `url` of the publication
   page, `document`, `date`, `base`), as the last entry.
3. Run `uv run python -m gdp_pipeline.population --add ~/Downloads/<file>.xlsx`. It copies the file into
   `sources/raw/population/` and records it in the manifest under the last entry of `NAS_STATEMENTS` (it refuses to
   replace a different file already there unless given `--replace`, which is why the entry comes first).
4. Run `uv run python -m gdp_pipeline`. The newest document gives each year's population; the report shows the
   figures reproduced. The statement is read by its English labels, and a changed layout is a check failure rather
   than a misread (`parse_nas` in `population_read.py`). The weekly refresh never downloads these files; if one is
   missing, `--fetch` says so and the checks fail (so the weekly refresh stops) until it is added.

When the RBI publishes a new *Handbook of Statistics on the Indian Economy* (each July or August), the addresses of
Tables 1 and 2 in `population_read.py` (`RBI_TABLES`) can be updated so that the checks cover the newest years too.

## Forecast sources

`pipeline/gdp_pipeline/forecast_sources/*.json` are listed by hand, each with the exact sentence, the URL and
the page. The pipeline downloads each document and fails if the sentence or its numbers are not there. The
IMF's historical WEO forecasts are not included yet: imf.org refuses automated downloads, so that file would
need to be downloaded by hand into `sources/`.

### Adding a forecast

**After each RBI monetary policy statement** (about every two months), add a record to
`pipeline/gdp_pipeline/forecast_sources/rbi.json` for every year it projects:

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

- `quote` is copied exactly from the document at `url`; the numbers in it must be the numbers in the record, and
  it must name the record's `fiscal_year` (as "2026-27" or "FY27"; the year before may be named too). Years are
  not read as numbers. If the sentence does not name the year, the check fails until the year is confirmed from
  the text around it and added, with that reason, to `KNOWN_EXCEPTIONS` in `checks.py`.
- `measure` is `GDP` or `GVA`, as the statement says.
- `value` is a single projection; use `low` and `high` for a range, and `value_text` with `value: null` for words
  such as "a little below 5 per cent".
- `is_first` marks a year's first projection; `is_first_april_policy` the first one in the April policy, which the
  site uses as the year's starting forecast.
- `is_last` marks the final projection before the year's outcome. While a year is still running, its latest
  record has `is_last: false` and `is_latest_available: true`; move that flag when a newer statement comes.
- The checks work the flags out again from the dates (counting only records with a `value`, `low` or `high`; the
  April policy is the first one dated April or May of the year) and fail if any is on the wrong record.

**After each Economic Survey** (late January), add a record to `pipeline/gdp_pipeline/forecast_sources/economic_survey.json`
with `fiscal_year`, `survey`, `published_date`, `kind` (`point` or `range`), `low` and `high` (the same number for a
point), `quote`, `url`, `pdf_page`, the nominal fields (`nominal_low`, `nominal_high`, `nominal_quote`, or `null`)
and `notes`. Both nominal figures must be in `nominal_quote`. Optional fields:

- `band_low` and `band_high`: the band around a point forecast, such as "9 per cent (+/- 0.25)"; the forecasts page
  shows it. Both must be in `quote` or `quote_2`, or be the projection plus and minus the "(+/- x)" in `quote`.
- `quote_text_layer`: the quote as the PDF's text layer reads it, where that differs from the printed page (a ¾ read
  as `3/4`); the check accepts either.
- `quote_2`, for a projection stated in two places, with `quote_2_url` and `quote_2_pdf_page` if it is in another
  document.

The survey's chapters move from `indiabudget.gov.in/economicsurvey/` to `indiabudget.gov.in/budget<year>/economicsurvey/`
when the next survey comes out; the downloaded copy is kept, so the record's `url` only needs updating if the file
is downloaded again.

Then run `uv run python -m gdp_pipeline --fetch`: it downloads the new documents and checks every quote.

### When a check fails after a refresh

Allowed exceptions are written in `pipeline/gdp_pipeline/checks.py`: one-off cases in `KNOWN_EXCEPTIONS` and whole
families of known differences in `KNOWN_RULES`, each with its reason (state accounts: `states_checks.py`). Errors found in MoSPI's rows themselves
(unit labels, odd years, duplicate rows) are handled in `build.py` and listed on the site's Sources page.

## Not yet covered

- A rural/urban split. MoSPI does not publish GDP by rural/urban area each year; the rural and urban indicators it
  does publish (consumer prices, jobs, household spending) are in the [jobs and prices area](../jobs-prices/README.md).
- Revision history for 2000-01 to 2010-11 (earlier base years, from press releases).
- Revisions to state GDP before November 2026: MoSPI keeps only the latest state estimates, so the history starts
  with the weekly refresh.

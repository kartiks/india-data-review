"""Where every figure comes from.

1. National accounts: MoSPI's official API (api.mospi.gov.in, the service behind
   esankhyiki.mospi.gov.in). Free, no key. Three series:
   - base 2011-12, "Current": 2011-12 onward, annual figures at every official
     estimate stage (First/Second Advance, Provisional, First/Second/Third
     Revised), plus quarterly figures (latest estimate only).
   - base 2011-12, "Back": 1950-51 to 2011-12 recomputed on the 2011-12 base
     (one estimate per year), so long-run growth is on one consistent basis.
   - base 2022-23, "Current": the new series released 27 Feb 2026, 2022-23
     onward (latest estimate per year only, plus quarters).
   Indicator codes 1-22 are national; 23-34 are the state accounts (annual
   only, latest estimate only, published on the 2011-12 base; no All-India row).

2. Union Budget GDP assumption: "GDP for BE ... has been projected at ...",
   printed under the Budget at a Glance headline table (indiabudget.gov.in).

3. Forecasts: the Economic Survey's and the RBI's growth projections, listed
   by hand in forecast_sources/*.json (each with the exact sentence and the
   official document it is quoted from; see forecasts.py).

4. Population, for figures per person: the 2019 population projections,
   MoSPI's press notes and National Accounts Statistics, and the RBI's
   handbook (see population_read.py).
"""

from pipeline_common import budget_glance

NAS_API = "https://api.mospi.gov.in/api/nas/getNASData"
NAS_PAGE_LIMIT = 200  # the API refuses larger pages

# (base year, series, frequency) combinations to download.
NAS_SERIES = [
    ("2011-12", "Current", "Annually"),
    ("2011-12", "Current", "Quarterly"),
    ("2011-12", "Back", "Annually"),
    ("2022-23", "Current", "Annually"),
    ("2022-23", "Current", "Quarterly"),
]
NAS_INDICATORS = range(1, 23)

# State accounts (indicator codes 23-34): GSDP, NSDP, per-capita income, growth, value added by industry, taxes and
# subsidies on products, by state. MoSPI publishes them on the 2011-12 base only. The 2022-23 base is queried too, so
# that a state series on the new base arrives with the weekly refresh (the validation report then says so).
STATE_SERIES = [
    ("2011-12", "Current", "Annually"),
    ("2022-23", "Current", "Annually"),
]
STATE_INDICATORS = range(23, 35)

FIRST_BUDGET = 2011  # 2011-12: first budget whose GDP assumption is on the 2011-12 base's era
LATEST_BUDGET = 2026  # 2026-27


def budget_glance_urls(start: int) -> list[str]:
    """Budget at a Glance headline table (the page that states the GDP assumption)."""
    return [budget_glance.url(start, LATEST_BUDGET)]


BUDGETS = list(range(FIRST_BUDGET, LATEST_BUDGET + 1))

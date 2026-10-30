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
   Indicator codes 1-22 are national; 23-34 are state-level (not used yet).

2. Union Budget GDP assumption: "GDP for BE ... has been projected at ...",
   printed under the Budget at a Glance headline table (indiabudget.gov.in).

3. Forecasts: IMF World Economic Outlook (historical forecasts file), and the
   Economic Survey and RBI projections in forecasts.py (each with the exact
   sentence and the official document it is quoted from).
"""

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

BUDGET_BASE = "https://www.indiabudget.gov.in"
FIRST_BUDGET = 2011  # 2011-12: first budget whose GDP assumption is on the 2011-12 base's era
LATEST_BUDGET = 2026  # 2026-27


def fy(start: int) -> str:
    """2011 -> '2011-12'."""
    return f"{start}-{str(start + 1)[-2:]}"


def budget_glance_urls(start: int) -> list[str]:
    """Budget at a Glance headline table (the page that states the GDP assumption)."""
    y = fy(start)
    if start <= 2018:
        site = f"{BUDGET_BASE}/budget{start}-{start + 1}/ub{y}"
        name = "bag/bag11" if start == 2016 else "bag/bag1"  # 2016-17 names this PDF bag11.pdf
        return [f"{site}/{name}.pdf"]
    site = (BUDGET_BASE if start == LATEST_BUDGET else f"{BUDGET_BASE}/budget{y}") + "/doc"
    return [f"{site}/Budget_at_Glance/bag1.pdf"]


BUDGETS = list(range(FIRST_BUDGET, LATEST_BUDGET + 1))

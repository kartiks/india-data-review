"""Checks that the figures the site shows hang together.

1. Source rows: every value is a number or marked missing ("NaN"); anything
   else is listed and left out.
2. Jobs (PLFS):
   - worker population ratio = participation rate × (1 − unemployment rate),
     within rounding, for every combination the site may show;
   - the figure for persons lies between men's and women's, and the rural +
     urban figure between rural and urban (rates, job conditions, earnings);
   - shares of workers (by type of work, industry, employer) add up to 100%.
   Combinations that break the first two are left out of the site by the build,
   each with its reason; they are listed here.
3. Consumer prices (CPI, CPI-AL/RL):
   - every published inflation rate is reproduced from the index 12 months earlier;
   - the combined index lies between the rural and urban index;
   - no month is missing.
4. Household spending (HCES):
   - the 12 spending classes, averaged with their population shares, give the
     overall average; item categories add up to the food and non-food totals,
     and those to the average (or 100%);
   - Table A2 of the full report agrees with the data service, its states add
     up to All India, and each overall (rural + urban) average lies between
     the rural and urban ones.
5. RBI Handbook of Statistics on Indian States:
   - every table read, in its expected unit and sub-titles;
   - its state inflation agrees with MoSPI's monthly indices;
   - overall unemployment between men's and women's; the All-India wage within
     the states' range;
   - state GDP and income per person agree at current and constant prices.
6. Consumer prices, base 2024 (press releases):
   - every release read in full; headline, summary and annexures agree;
   - inflation reproduced from the index a year earlier; combined between
     rural and urban; only provisional figures revised;
   - the linking factor equals the 2025 average, new base / old base;
   - the release page's tables match its PDF.
7. Text: no '<', '>' or control characters in any key or value of the data files
   (pipeline_common.data_text).

Exceptions are allowed only through the rules in each module (values, jobs, prices, spending, states,
prices2024), each with a reason.
Writes jobs-prices/data/validation_report.md and validation_summary.json; exits non-zero on any failure.
"""

from pipeline_common.data_text import check_data_text
from pipeline_common.report import Report

from ..common import ROOT
from .jobs import check_brackets, check_distribution, check_rates
from .prices import check_cpi_combined, check_cpi_inflation, check_cpi_months, check_cpialrl
from .prices2024 import check_cpi2024
from .spending import check_hces, check_hces_overall
from .states import check_rbi_inflation, check_rbi_income, check_rbi_read, check_rbi_totals
from .values import check_source

DATA = ROOT / "data"
INTRO = ("Jobs (PLFS), consumer prices (CPI, CPI-AL/RL) and household spending (HCES) from MoSPI's official "
         "data service (CPI-AL/RL is the Labour Bureau's), the base-2024 CPI from MoSPI's press releases on PIB, and "
         "state comparisons from the RBI's Handbook of Statistics on Indian States. Every allowed exception lists "
         "its reason.")

# In the order of the report: each adds one group of checks (check_cpi2024 adds the new series' seven).
CHECKS = (check_source, check_rates, check_brackets, check_distribution, check_cpi_inflation, check_cpi_combined,
          check_cpi_months, check_cpialrl, check_hces, check_hces_overall, check_rbi_read, check_rbi_inflation,
          check_rbi_totals, check_rbi_income, check_cpi2024)


def main(ds: dict | None = None) -> int:
    if ds is None:
        from ..build import assemble

        ds = assemble()
    report = Report(INTRO)
    for check in CHECKS:
        check(ds, report)
    check_data_text(DATA, report)
    return report.write(DATA)

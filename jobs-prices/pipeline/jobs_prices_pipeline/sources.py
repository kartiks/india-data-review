"""Where every figure comes from.

Items 1-4 are from MoSPI's official data service (api.mospi.gov.in, the service
behind esankhyiki.mospi.gov.in), free, no key; item 3 is the Labour Bureau's,
served by it. Specs for each dataset:
https://api.mospi.gov.in/layout/swagger_user_<dataset>.yaml
Items 5-7 are documents: MoSPI's press releases on PIB, a table of MoSPI's HCES
report, and the RBI's Handbook of Statistics on Indian States.

1. Jobs: Periodic Labour Force Survey (PLFS), /api/plfs/getData
   - indicators 1-3: labour force participation rate, worker population ratio,
     unemployment rate; 4: distribution of workers (by status, industry ...);
     5: conditions of regular employees (written contract, paid leave, social
     security); 6-8: earnings (regular wage, casual wage, self-employment).
   - annual (calendar years from 2022; job conditions by July-June year from
     2017-18), quarterly (urban from April-June 2018, rural too from 2025)
     and monthly (from 2025).
2. Consumer prices: CPI (base 2012 = 100), /api/cpi/getCPIIndex, Jan 2013 to
   Dec 2025. Every group and subgroup for All India; the general index for
   every state. The new 2024-base series (from Jan 2026) is item 5.
3. CPI for agricultural and rural labourers (Labour Bureau),
   /api/cpialrl/getCpialrlRecords.
4. Household spending: Household Consumption Expenditure Survey (HCES)
   2022-23 and 2023-24, /api/hces/getHcesRecords.
5. Consumer prices, new series (base 2024 = 100), from January 2026: MoSPI's
   monthly press releases on PIB. MoSPI's data service lists the base-2024
   filters but returns no data for them, so the figures are read from the
   tables on each release's page (divisions, groups, states, and the All-India
   series from January 2025) and checked against the release's PDF where it
   has one. Add each new month's release page below.
6. Household spending, overall (rural + urban): Table A2 of MoSPI's full HCES
   2023-24 report (Excel, mospi.gov.in), the estimated persons used as weights.
7. State comparisons: the RBI Handbook of Statistics on Indian States, the
   tables listed in rbi.RBI_STATE_TABLES (Excel, rbi.org.in).
"""

from datetime import date

from pipeline_common.text import slug

API = "https://api.mospi.gov.in/api"
PAGE_LIMIT = 200  # the API refuses larger pages

PLFS_INDICATORS = range(1, 9)
PLFS_FREQUENCIES = {1: "annual", 2: "quarterly", 3: "monthly"}

CPI_YEARS = range(2013, 2026)  # base 2012 series: Jan 2013 to Dec 2025
CPI_ALL_INDIA = 99  # state_code for All India
CPI_GENERAL = 0  # group_code for the general index

CPIALRL_INDICATORS = ["General Index", "Group Index"]

HCES_INDICATORS = {  # file name -> MoSPI's indicator code (as the API spells it)
    "mpce": "Average monthly per capita consumption expenditure (MPCE)",
    "mpce_classes": "Average monthly per capita consumption expenditure (MPCE) Over 12 Fractile Classes",
    "categories_rs": "Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days",
    "categories_share": "Percentage Share of Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days",
    "quantity": "Average Per Capita Monthly Quantity Consumption ",  # trailing space is in MoSPI's code list
    "value_of_consumption": "Average Monthly Per Capita Value of Consumption (Rs.)",
    "mpce_household_type": "Average Monthly Per Capita Consumption Expenditure (MPCE) across different Household Type",
    "mpce_social_group": "Average Monthly Per Capita Consumption Expenditure (MPCE) across different Social Group",
    "gini": "Gini Coefficient for Per Capita Consumption Expenditure",
}


# HCES report tables (Excel), from MoSPI's full survey report. Table A2 gives the survey's estimated number of
# households and persons in each state's rural and urban areas, used to weight rural and urban averages into an
# overall average (MoSPI publishes rural and urban only). The 2022-23 report's tables are not online as files.
HCES_REPORT_TABLES = {
    "2023-24/TableA2": "https://mospi.gov.in/sites/default/files/publication_reports/HCES-23-24/TableA2.xlsx",
}

# Month of the index -> PIB page of MoSPI's press release for it (English).
CPI2024_RELEASES = {
    "2026-01": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2227012&reg=3&lang=1",
    "2026-02": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2238889&reg=3&lang=1",
    "2026-03": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2251519&reg=3&lang=1",
    "2026-04": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2260251&reg=3&lang=1",
    "2026-05": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2272112&reg=3&lang=1",
    "2026-06": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2284125&reg=3&lang=1",
    "2026-07": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2298247&reg=3&lang=1",
    "2026-08": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2310058&reg=3&lang=1",
    "2026-09": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2322244&reg=3&lang=1",
}
CPI2024_RELEASE_DAY = 12  # MoSPI releases each month's CPI on about the 12th of the next month
CPI2024_MAX_AGE_DAYS = 45  # the refresh fails when the latest release is older: the next one is ~2 weeks overdue


def cpi2024_overdue(latest: str | None, today: date) -> str | None:
    """Why the base-2024 CPI is out of date, or None. latest = the latest month read ('2026-09'). Its release came
    out about the 12th of the next month; more than CPI2024_MAX_AGE_DAYS after that, the following month's release
    (due a month later) has been out for about two weeks and has not been added to CPI2024_RELEASES.

    Run only by the weekly refresh (--refresh-api, --refresh), not by the offline build: the committed data must
    keep building and passing its checks however much time passes."""
    if latest is None:
        return "no base-2024 CPI release read"
    y, m = map(int, latest.split("-"))
    released = date(y + m // 12, m % 12 + 1, CPI2024_RELEASE_DAY)
    age = (today - released).days
    if age <= CPI2024_MAX_AGE_DAYS:
        return None
    return (f"the latest base-2024 CPI month is {latest}, released about {released.isoformat()}, {age} days ago "
            f"(more than {CPI2024_MAX_AGE_DAYS}): add the newer monthly releases to CPI2024_RELEASES in sources.py "
            "and run --fetch (see the README, 'Each month')")


def queries() -> list[tuple[str, str, dict]]:
    """(manifest key, endpoint path, parameters) for every file the pipeline downloads."""
    out: list[tuple[str, str, dict]] = []
    for freq, name in PLFS_FREQUENCIES.items():
        for code in PLFS_INDICATORS:
            out.append((f"plfs/{name}/ind{code:02d}", "plfs/getData", {"indicator_code": code, "frequency_code": freq}))
    for year in CPI_YEARS:
        base = {"base_year": "2012", "series": "Current", "year": year}
        out.append((f"cpi/all_india/{year}", "cpi/getCPIIndex", {**base, "state_code": CPI_ALL_INDIA}))
        out.append((f"cpi/states_general/{year}", "cpi/getCPIIndex", {**base, "group_code": CPI_GENERAL}))
    for ind in CPIALRL_INDICATORS:
        out.append((f"cpialrl/{slug(ind)}", "cpialrl/getCpialrlRecords", {"indicator_code": ind}))
    for name, ind in HCES_INDICATORS.items():
        out.append((f"hces/{name}", "hces/getHcesRecords", {"indicator_code": ind}))
    return out

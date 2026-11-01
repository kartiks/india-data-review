"""Where every figure comes from.

All of it is from MoSPI's official data service (api.mospi.gov.in, the service
behind esankhyiki.mospi.gov.in). Free, no key. Specs for each dataset:
https://api.mospi.gov.in/layout/swagger_user_<dataset>.yaml

1. Jobs: Periodic Labour Force Survey (PLFS), /api/plfs/getData
   - indicators 1-3: labour force participation rate, worker population ratio,
     unemployment rate; 4: distribution of workers (by status, industry ...);
     5: conditions of regular employees (written contract, paid leave, social
     security); 6-8: earnings (regular wage, casual wage, self-employment).
   - annual (calendar years from 2022; job conditions by July-June year from
     2017-18), quarterly (urban, from 2018) and monthly (from 2025).
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
"""

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


def slug(text: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out


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

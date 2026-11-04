"""MoSPI's names, and the ids the datasets use for them: indicators, estimate stages, industries and institutional
sectors. Shared by the national accounts (build.py), the state accounts (states.py), population and the checks."""

import math
import re

INDICATORS = {
    1: ("gva", "Gross value added (GVA)"),
    2: ("net_taxes", "Net taxes on products"),
    3: ("product_taxes", "Taxes on products"),
    4: ("product_subsidies", "Subsidies on products"),
    5: ("gdp", "Gross domestic product (GDP)"),
    6: ("cfc", "Consumption of fixed capital (depreciation)"),
    7: ("ndp", "Net domestic product"),
    8: ("gcf_by_industry", "Gross capital formation by industry of use"),
    9: ("gfcf", "Gross fixed capital formation (investment in fixed assets)"),
    10: ("pfce", "Private final consumption expenditure (household spending)"),
    11: ("gfce", "Government final consumption expenditure"),
    12: ("stocks", "Change in stocks"),
    13: ("valuables", "Valuables"),
    14: ("exports", "Exports of goods and services"),
    15: ("imports", "Imports of goods and services"),
    16: ("primary_income_row", "Primary income receivable, net, from rest of world"),
    17: ("gni", "Gross national income"),
    18: ("transfers_row", "Other current transfers, net, from rest of world"),
    19: ("gndi", "Gross national disposable income"),
    20: ("saving", "Gross saving"),
    21: ("gva_growth", "GVA growth rate"),
    22: ("gdp_growth", "GDP growth rate"),
}
GROWTH_INDICATORS = {21, 22}

# Official estimate stages, in the order they are published.
STAGES = [
    ("AE1", "First Advance Estimates", "First Advance Estimate", "about 1 week after the year's 9th month (early January)"),
    ("AE2", "Second Advance Estimates", "Second Advance Estimate", "end of February, before the year ends"),
    ("PE", "Provisional Estimates", "Provisional Estimate", "end of May, 2 months after the year ends"),
    ("RE1", "First Revised Estimates", "First Revised Estimate", "about 1 year after the year ends"),
    ("RE2", "Second Revised Estimates", "Second Revised Estimate", "about 2 years after the year ends"),
    ("RE3", "Third Revised Estimates", "Third Revised Estimate", "about 3 years after the year ends"),
    ("ADD", "Additional Revision", "Additional revision", "special revision of 2011-12 to 2013-14"),
    ("FINAL", "Final Estimates", "Final Estimate", "the last revision under MoSPI's current revision policy"),
]
STAGE_BY_LABEL = {label: sid for sid, label, _, _ in STAGES}
STAGE_ORDER = {sid: i for i, (sid, _, _, _) in enumerate(STAGES)}

INDUSTRIES = {
    "Agriculture, Livestock, Forestry and Fishing": "agriculture",
    "Mining and Quarrying": "mining",
    "Manufacturing": "manufacturing",
    "Electricity, Gas, Water Supply & Other Utility Services": "utilities",
    "Construction": "construction",
    "Trade, Hotels, Transport, Communication & Services Related to Broadcasting": "trade_transport",
    "Trade, Repair, Hotels and Restaurants": "trade_hotels",
    "Transport, Storage, Communication & Services Related to Broadcasting": "transport_comm",
    "Financial, Real Estate & Professional Services": "finance_realestate",
    "Financial Services": "financial",
    "Real Estate, Ownership of Dwelling & Professional Services": "real_estate",
    "Public Administration, Defence & Other Services": "public_other",
    "Public Administration and Defence": "public_admin",
    "Other Services": "other_services",
    "Total Gross Value Added": "total",
    "Total Gross Capital Formation": "total",
    "Total GVA Growth Rate": "total",
}
# The eight broad groups MoSPI uses in its press notes, and the finer industries that make up three of them.
GROUPS = {
    "trade_transport": ["trade_hotels", "transport_comm"],
    "finance_realestate": ["financial", "real_estate"],
    "public_other": ["public_admin", "other_services"],
}
BROAD = ["agriculture", "mining", "manufacturing", "utilities", "construction",
         "trade_transport", "finance_realestate", "public_other"]
INDUSTRY_LABELS = {
    "agriculture": "Agriculture, forestry & fishing",
    "mining": "Mining & quarrying",
    "manufacturing": "Manufacturing",
    "utilities": "Electricity, gas, water & utilities",
    "construction": "Construction",
    "trade_transport": "Trade, hotels, transport & communication",
    "trade_hotels": "Trade, repair, hotels & restaurants",
    "transport_comm": "Transport, storage & communication",
    "finance_realestate": "Finance, real estate & professional services",
    "financial": "Financial services",
    "real_estate": "Real estate, dwellings & professional services",
    "public_other": "Public administration, defence & other services",
    "public_admin": "Public administration & defence",
    "other_services": "Other services",
    "total": "Total GVA",
}
SECTORS = {
    "Public Non-Financial Corporations": "public_nonfin",
    "Private Non-Financial Corporations": "private_nonfin",
    "Public Financial Corporations": "public_fin",
    "Private Financial Corporations": "private_fin",
    "General Government": "government",
    "Household Sector": "households",
    "Households Including NPISH": "households",
    "Total Gross Fixed Capital Formation": "total",
    "Total Gross Saving": "total",
    "Total Consumption of Fixed Capital": "total",
    "Total Gross Value Added": "total",
}
SECTOR_LABELS = {
    "public_nonfin": "Public non-financial companies",
    "private_nonfin": "Private non-financial companies",
    "public_fin": "Public financial companies",
    "private_fin": "Private financial companies",
    "government": "Government",
    "households": "Households",
    "total": "Total",
}


def slug(text: str) -> str:
    """'Trade & Repair Services' -> 'trade_repair_services': lower case, every run of other characters one '_'."""
    return re.sub("_+", "_", "".join(c if c.isalnum() else "_" for c in text.lower())).strip("_")


def number(v) -> float | None:
    if v is None:
        return None
    try:
        x = float(str(v).replace(",", ""))
    except ValueError:
        return None
    return None if math.isnan(x) else x


def latest_stage(stages: dict) -> str:
    return max(stages, key=lambda s: STAGE_ORDER.get(s, 99))

"""Budget at a Glance addresses, and the GDP sentence as it comes out of the real PDFs."""

import json
from pathlib import Path

import pytest

from pipeline_common import budget_glance as bg
from pipeline_common.text import fy

REPO = Path(__file__).resolve().parents[3]


def test_urls_follow_the_site_layout():
    assert bg.url(2005, 2026) == "https://www.indiabudget.gov.in/budget_archive/ub2005-06/bag/bag1.pdf"
    assert bg.url(2015, 2026) == "https://www.indiabudget.gov.in/budget2015-2016/ub2015-16/bag/bag1.pdf"
    assert bg.url(2016, 2026) == "https://www.indiabudget.gov.in/budget2016-2017/ub2016-17/bag/bag11.pdf"  # its quirk
    assert bg.url(2016, 2026, n=2) == "https://www.indiabudget.gov.in/budget2016-2017/ub2016-17/bag/bag2.pdf"
    assert bg.url(2018, 2026, ext="xls") == "https://www.indiabudget.gov.in/budget2018-2019/ub2018-19/bag/bag1.xls"
    assert bg.url(2025, 2026, n=5) == "https://www.indiabudget.gov.in/budget2025-26/doc/Budget_at_Glance/bag5.pdf"
    # the latest budget is at the site's root
    assert bg.url(2026, 2026) == "https://www.indiabudget.gov.in/doc/Budget_at_Glance/bag1.pdf"
    assert bg.url(2026, 2027) == "https://www.indiabudget.gov.in/budget2026-27/doc/Budget_at_Glance/bag1.pdf"


def test_urls_match_the_committed_manifests():
    """Every Budget at a Glance file both areas downloaded is where url() says."""
    gdp = json.loads((REPO / "gdp" / "sources" / "manifest.json").read_text())
    budget = json.loads((REPO / "budget" / "sources" / "manifest.json").read_text())
    for start in range(2011, 2027):
        y = fy(start)
        assert gdp[f"budget/{y}/bag1"]["url"] == bg.url(start, 2026)
    for start in range(2004, 2027):
        pdf = budget[fy(start)]["summary"]["files"].get("pdf")
        if pdf:
            assert pdf["url"] == bg.url(start, 2026)


# Real sentences, as the PDFs' text layers give them (the rupee sign is printed as a backtick in most years).
SENTENCES = [
    ("Notes: 1. GDP for BE 2012-2013 has been projected at ` 10159884 crore assuming 14% growth over the Advance "
     "Estimates of 2011-2012 (` 8912179 crore) released by CSO.",
     {"gdp_crore": 10159884, "printed_year": "2012-2013",
      "text": "GDP for BE 2012-2013 has been projected at ` 10159884 crore"}),
    ("Notes: 1. GDP for BE 2016-2017 has been projected at`15065010 crore assuming 11% growth over theAdvanceEstimates "
     "of 2015-2016 (`13567192 crore) released by CSO.",
     {"gdp_crore": 15065010, "printed_year": "2016-2017",
      "text": "GDP for BE 2016-2017 has been projected at`15065010 crore"}),
    ("(i) GDP for BE 2019-2020 has been projected at 21100607 crore assuming 12.0 % growth over the estimated GDP of "
     "`18840731 crore for 2018-2019 (RE).",
     {"gdp_crore": 21100607, "printed_year": "2019-2020", "growth_pct": 12.0, "over": "estimated GDP",
      "base_gdp_crore": 18840731,
      "text": "GDP for BE 2019-2020 has been projected at 21100607 crore assuming 12.0 % growth over the estimated GDP of "
              "`18840731 crore"}),
    ("Notes: (i) - ` (i) Nominal GDP for BE 2023-2024 has been projected at % `3,01,75,065 crore assuming 10.5 % "
     "growth over the - ` estimated Nominal GDP of `2,73,07,751 crore as per the First Advance Estimates of FY 2022-23.",
     {"gdp_crore": 30175065, "printed_year": "2023-2024", "growth_pct": 10.5, "over": "- ` estimated Nominal GDP",
      "base_gdp_crore": 27307751,
      "text": "GDP for BE 2023-2024 has been projected at % `3,01,75,065 crore assuming 10.5 % growth over the - ` "
              "estimated Nominal GDP of `2,73,07,751 crore"}),
    # 2024-25, the English half of the bilingual page
    ("(i) The GDP for Budget FY 2024-25 (Regular) is estimated at `3,26,36,912 crore which is 10.5% over the "
     "Provisional Estimates of FY 2023-24 at `2,95,35,667 crore.",
     {"gdp_crore": 32636912, "printed_year": "2024-25", "growth_pct": 10.5,
      "over": "Provisional Estimates of FY 2023-24", "base_gdp_crore": 29535667,
      "text": "GDP for Budget FY 2024-25 (Regular) is estimated at `3,26,36,912 crore which is 10.5% over the "
              "Provisional Estimates of FY 2023-24 at `2,95,35,667 crore"}),
    # 2025-26, read from the rendered page
    (bg.IMAGE_READ["2025-26"]["text"],
     {"gdp_crore": 35697923, "printed_year": "2025-26", "growth_pct": 10.1,
      "over": "Revised Estimates for FY 2024-25", "base_gdp_crore": 32411406,
      "text": "GDP for FY 2025-26 is estimated at ₹ 356,97,923 crore, which is 10.1% over the Revised Estimates for "
              "FY 2024-25 of ₹ 324,11,406 crore"}),
    # 2026-27: the Hindi column's figures interleave the growth part, so only the GDP is read
    ("(i) 2026-27 (i) The GDP for FY 2026-27 is estimated at `393,00,393 crore, `393,00,393 2025-26 which is 10% over "
     "the Advance Estimates for FY 2025-26 of `357,13,886 10% `357,13,886 crore released by NSO.",
     {"gdp_crore": 39300393, "printed_year": "2026-27", "text": "GDP for FY 2026-27 is estimated at `393,00,393 crore"}),
]


@pytest.mark.parametrize("text,expected", SENTENCES, ids=[e["printed_year"] for _, e in SENTENCES])
def test_parse_sentence(text, expected):
    assert bg.parse_sentence(text) == expected


def test_parse_sentence_without_growth_stops_at_the_gdp():
    text, expected = SENTENCES[4]
    assert bg.parse_sentence(text, growth=False) == {
        "gdp_crore": 32636912, "printed_year": "2024-25",
        "text": "GDP for Budget FY 2024-25 (Regular) is estimated at `3,26,36,912 crore"}


def test_text_that_lacks_the_sentence_is_not_misread():
    # 2024-25's table read as rows: the Hindi column's figures sit between the words (page_texts reads the halves)
    rows_2024 = ("3,26,36,912 (i) The GDP for Budget FY 2024-25 (Regular) is estimated at 2023-24 `2,95,35,667 "
                 "`3,26,36,912 crore which is 10.5% over the Provisional 10.5% Estimates of FY 2023-24")
    # 2025-26's text layer: the amounts are missing (hence IMAGE_READ)
    rows_2025 = ("(i) The GDP for FY 2025-26 is estimated at ,923 crore, 4- which is 10.1% over the Revised Estimates "
                 "for FY 2024-25 of 5 %")
    assert bg.parse_sentence(rows_2024) is None
    assert bg.parse_sentence(rows_2025) is None


@pytest.mark.parametrize("year,gdp", [("2023-24", 30175065), ("2024-25", 32636912), ("2026-27", 39300393)])
def test_found_in_the_committed_pdfs(year, gdp):
    pdf = REPO / "gdp" / "sources" / "raw" / "budget" / year / "bag1.pdf"
    found, note = bg.texts(year, pdf)
    parsed = next(p for p in map(bg.parse_sentence, found) if p)
    assert parsed["gdp_crore"] == gdp and note is None


def test_2025_26_is_read_from_the_rendered_page():
    found, note = bg.texts("2025-26", Path("unused.pdf"))
    assert bg.parse_sentence(found[0])["gdp_crore"] == 35697923 and "rendered page" in note

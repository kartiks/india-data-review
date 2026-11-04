"""The shared text and number helpers, with the cases each area's former copy handled."""

import math

import pytest

from pipeline_common.numbers import blank_or_number, number, strict_number
from pipeline_common.text import fy, fy_start, next_fy, prev_fy, slug


# ---- slug ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    # gdp's industry and sub-industry ids (every run of separators is one '_')
    ("Trade & Repair Services", "trade_repair_services"),
    ("Communication & Services Related to Broadcasting", "communication_services_related_to_broadcasting"),
    ("Food Products, Beverages and Tobacco", "food_products_beverages_and_tobacco"),
    (" -- Odd -- spacing -- ", "odd_spacing"),
    # jobs-prices' CPI-AL/RL query keys
    ("General Index", "general_index"),
    ("Food__and  Beverages", "food_and_beverages"),
    ("", ""),
    ("---", ""),
    # Unicode letters count as letters unless ascii_only
    ("Café Index", "café_index"),
])
def test_slug(text, expected):
    assert slug(text) == expected


def test_slug_ascii_only_and_max_len():
    # budget's scheme ids: only a-z and 0-9, cut to a length (after the rest, so the cut can end in '_')
    assert slug("Café Index", ascii_only=True) == "caf_index"
    assert slug("Pradhan Mantri Awas Yojana (PMAY)", ascii_only=True, max_len=80) == "pradhan_mantri_awas_yojana_pmay"
    assert slug("ab cd", max_len=3) == "ab_"
    assert slug("Prime Minister's Scheme", ascii_only=True) == "prime_minister_s_scheme"


# ---- fiscal years --------------------------------------------------------------------------------

def test_fy():
    assert fy(2011) == "2011-12"
    assert fy(1999) == "1999-00"
    assert fy(2099) == "2099-00"
    assert fy(1950) == "1950-51"


@pytest.mark.parametrize("label, start", [("2011-12", 2011), ("1999-00", 1999), ("1999-2000", 1999),
                                          ("2023-2024", 2023), ("1950-51", 1950)])
def test_fy_start(label, start):
    assert fy_start(label) == start


@pytest.mark.parametrize("label", ["2011", "2011-13", "1999-01", "1999-2001", "2011-12 Q1", " 2011-12", "FY 2011-12",
                                   "2011–12"])
def test_fy_start_refuses_anything_else(label):
    with pytest.raises(ValueError):
        fy_start(label)


def test_prev_and_next_fy():
    # what gdp's and jobs-prices' inline arithmetic gave: f"{int(y[:4]) - 1}-{y[2:4]}"
    for y in ("2000-01", "2011-12", "2023-24", "1951-52"):
        assert prev_fy(y) == f"{int(y[:4]) - 1}-{y[2:4]}"
    assert prev_fy("2000-01") == "1999-00"
    assert prev_fy("1999-2000") == "1998-99"
    assert next_fy("1999-00") == "2000-01"
    assert next_fy("1999-2000") == "2000-01"
    assert next_fy("2024-25", 2) == "2026-27"  # budget's datasets._next(fy, n)
    assert prev_fy("2024-25", 3) == "2021-22"
    assert next_fy("2024-25", 0) == "2024-25"


# ---- numbers -------------------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("12.5", 12.5), ("1,23,456.7", 123456.7), ("123,456", 123456.0), (" 7 ", 7.0), ("-3.2", -3.2),
    (5, 5.0), (2.5, 2.5),
    # gdp and jobs-prices (MoSPI's API): None, blanks, NaN and transcription errors are not numbers
    (None, None), ("", None), ("   ", None), ("NaN", None), ("nan", None), (float("nan"), None),
    ("l0.8", None), ("IN.4", None), ("20J", None),
    # markers of a missing figure
    ("-", None), ("–", None), ("NA", None), ("*", None),
    # a footnote mark is not stripped unless asked
    ("12.5*", None),
])
def test_number(value, expected):
    assert number(value) == expected


@pytest.mark.parametrize("value, expected", [
    # jobs-prices' CPI 2024 press release cells: footnote marks stripped, then the rest as above
    ("12.5*", 12.5), ("1,234.5*", 1234.5), ("*", None), ("", None), ("-", None), ("–", None),
    ("109.`39", None),  # a stray backtick: not a number
    ("nan", None),
])
def test_number_strip(value, expected):
    assert number(value, strip="*") == expected


def test_blank_or_number():
    assert blank_or_number(None) is None
    assert blank_or_number("") is None
    assert blank_or_number("  ") is None
    assert blank_or_number("12.5") == 12.5
    assert blank_or_number("1,234") == 1234.0
    assert blank_or_number(3) == 3.0
    assert blank_or_number("-", missing={"-", "NA"}) is None
    assert blank_or_number("NA", missing={"-", "NA"}) is None
    with pytest.raises(ValueError):
        blank_or_number("-")  # a marker only when listed
    with pytest.raises(ValueError):
        blank_or_number("l0.8")


def test_strict_number():
    # gdp's population reader and Budget at a Glance's GDP sentence
    assert strict_number("1,76,50,591") == 17650591.0
    assert strict_number("2,15,935") == 215935.0
    assert strict_number("1383") == 1383.0
    assert math.isclose(strict_number("10.5"), 10.5)
    for bad in ("", "-", "12.5*", "l0.8"):
        with pytest.raises(ValueError):
            strict_number(bad)

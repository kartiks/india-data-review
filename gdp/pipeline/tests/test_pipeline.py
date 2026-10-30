"""Unit tests for the readers, plus an end-to-end run of the checks on the saved data."""

import json
from pathlib import Path

import pytest

from gdp_pipeline import budget, build, checks, forecasts

ROOT = Path(__file__).resolve().parents[2]


def test_budget_sentence_with_growth():
    text = ("GDP for BE 2023-2024 has been projected at ` 3,01,75,065 crore assuming 10.5 % growth over the "
            "estimated Nominal GDP of ` 2,73,07,751 crore as per the First Advance Estimates")
    p = budget.parse_sentence(text)
    assert p["gdp_crore"] == 30175065
    assert p["growth_pct"] == 10.5
    assert p["base_gdp_crore"] == 27307751


def test_budget_sentence_without_growth():
    p = budget.parse_sentence("GDP for BE 2015-2016 has been projected at `14108945 crore")
    assert p["gdp_crore"] == 14108945 and "growth_pct" not in p


def test_numbers_in_quotes():
    assert forecasts.numbers_in("negative at (-)9.5 per cent") >= {-9.5}
    assert forecasts.numbers_in("7 to 7¾ per cent") >= {7.0, 7.75}
    assert forecasts.numbers_in("range of 5.4 – 5.9 per cent") >= {5.4, 5.9}


def test_in_order_tolerates_interleaved_text():
    quote = "expected to grow in the range of 5.4 – 5.9 per cent"
    text = "expected to grow in the turing, improved balance of range of 5.4 – 5.9 per cent in 2014-15"
    assert forecasts.in_order(quote, text)
    assert not forecasts.in_order(quote, "expected to fall sharply")


def test_unit_label_error_not_converted():
    assert build.to_crore(2079741, "₹ Lakh", "product_taxes") == 2079741
    assert build.to_crore(100, "₹ Lakh", "gdp") == 1


@pytest.mark.skipif(not (ROOT / "data" / "gdp.json").exists(), reason="data not built")
def test_checks_pass_on_saved_data():
    ds = json.loads((ROOT / "data" / "gdp.json").read_text())
    assert checks.main(ds) == 0

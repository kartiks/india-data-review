"""End-to-end: build the dataset from the saved source files and run every check."""

import json

import pytest

from budget_pipeline import build, checks
from budget_pipeline.build import DATA


@pytest.fixture(scope="module")
def checks_result():
    """Build everything once (headline + taxes, ministries, schemes) and run every check."""
    build.main()
    return checks.main()


@pytest.fixture(scope="module")
def dataset(checks_result):
    return json.loads((DATA / "fiscal.json").read_text())


def test_all_checks_pass(checks_result):
    assert checks_result == 0, "see web/data/validation_report.md"


@pytest.mark.parametrize(
    "year, field, kind, value",
    [
        # Published headline figures, quoted widely at the time.
        ("2000-01", "total_expenditure", "be", 338487),  # Budget 2000-01
        ("2024-25", "fiscal_deficit", "be", 1613312),  # Budget 2024-25 (July): 4.9% of GDP
        ("2024-25", "fiscal_deficit", "actual", 1574431),  # Budget 2026-27; PRS Union Budget Analysis 2026-27
        ("2025-26", "total_expenditure", "re", 4964842),  # Budget 2026-27; PRS
        ("2026-27", "capital_expenditure", "be", 1221821),  # Budget 2026-27; PRS
    ],
)
def test_known_published_figures(dataset, year, field, kind, value):
    assert dataset["years"][year][field][kind]["value"] == value


def test_missing_values_are_absent_not_zero(dataset):
    # The old app stored missing values as 0. Here a missing figure is simply not present.
    for year, fields in dataset["years"].items():
        for field, item in fields.items():
            for kind in ("be", "re", "actual"):
                if kind in item:
                    assert item[kind]["value"] != 0, (year, field, kind)


def test_every_figure_has_a_source(dataset):
    for fields in dataset["years"].values():
        for item in fields.values():
            for kind in ("be", "re", "actual"):
                if kind in item:
                    assert item[kind]["source_budget"] in dataset["sources"]


def detailed(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text())


def test_detailed_tables_built(dataset):
    for name in ("taxes", "ministries", "schemes"):
        assert detailed(name)["years"], name


@pytest.mark.parametrize(
    "name, year, item, kind, field, value",
    [
        # Figures published by PRS Legislative Research (Union Budget 2026-27 Analysis), in Rs crore.
        ("taxes", "2026-27", "corporation_tax", "be", "value", 1231000),
        ("taxes", "2024-25", "states_share", "actual", "value", 1286885),
        ("taxes", "2000-01", "net_tax_revenue", "actual", "value", 136916),  # Receipt Budget 2002-03 Annex 7
        ("ministries", "2024-25", "grand_total", "actual", "total_crore", 4652867.4),
        ("schemes", "2026-27", "css/css:samagra_shiksha", "be", "total_crore", 42100.02),
    ],
)
def test_detailed_known_figures(dataset, name, year, item, kind, field, value):
    assert detailed(name)["years"][year][item][kind][field] == pytest.approx(value, abs=0.01)


def test_image_read_figures_carry_a_note(dataset):
    # 2025-26 Statement 4A's Grand Total is missing from the PDF text layer and was read from the page image.
    item = detailed("schemes")["years"]["2025-26"]
    gt = next(v for k, v in item.items() if k.startswith("css/") and "grand_total" in k)
    assert "page image" in gt["be"]["note"]

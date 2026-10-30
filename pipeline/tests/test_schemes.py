"""Scheme statements (Expenditure Profile 4A/4B): edge cases from real files, and figures
confirmed against the rendered page image."""

import csv
from pathlib import Path

import pytest

from budget_pipeline.parse import ParseError
from budget_pipeline.schemes import (
    ROOT, Line, apply_text_layer_fixes, checks, load_all, parse_file, parse_value,
)

RAW = Path(__file__).resolve().parents[2] / "sources" / "raw"


def parsed(budget: str, scheme_type: str, ext: str = "pdf") -> dict:
    return parse_file(RAW / budget / f"{scheme_type}.{ext}", int(budget[:4]), scheme_type)


def find(result: dict, label_start: str, level: str = "scheme") -> dict:
    hits = [i for i in result["items"] if i["level"] == level and i["label_as_printed"].startswith(label_start)]
    assert len(hits) == 1, [i["label_as_printed"] for i in hits]
    return hits[0]


@pytest.fixture(scope="module")
def css_2026():
    return parsed("2026-27", "css")


def test_figures_confirmed_on_page_image(css_2026):
    # Read off the rendered page (Budget 2026-27 Statement 4A, page 1).
    assert find(css_2026, "Samagra Shiksha")["values"][("2026-27", "BE")]["total"] == 42100.02
    assert find(css_2026, "National AYUSH Mission")["values"][("2024-25", "Actual")]["total"] == 1081.85


def test_wrapped_name_continues_after_the_numbers(css_2026):
    item = find(css_2026, "Pradhan Mantri Poshan Shakti Nirman")
    assert item["label_as_printed"] == "Pradhan Mantri Poshan Shakti Nirman (PM POSHAN)"
    assert item["department"] == "Department of School Education and Literacy"


def test_ellipsis_is_nil_not_zero_and_blank_columns_stay_put():
    item = find(parsed("2026-27", "central_sector"), "Fund for Innovation and Adoption of Technology")
    assert item["values"][("2024-25", "Actual")] == {"revenue": None, "capital": None, "total": None}
    assert item["values"][("2026-27", "BE")]["total"] == 200.00


def test_digits_printed_apart_stay_in_one_cell():
    # Budget 2024-25 prints PMGSY's BE as "19000.00" with the "19" set apart (checked on the page image).
    item = find(parsed("2024-25", "css"), "Pradhan Mantri Gram Sadak Yojna")
    assert item["values"][("2024-25", "BE")]["total"] == 19000.00


def test_glued_cells_are_split():
    # Budget 2021-22: "283802.52" and "69.09" are glued into one word in the text layer.
    core = next(i for i in parsed("2021-22", "css")["items"] if i["level"] == "category_subtotal" and i["category"] == "B")
    assert core["values"][("2021-22", "BE")] == {"revenue": 283802.52, "capital": 69.09, "total": 283871.61}


def test_last_digit_wrapped_onto_next_line_is_joined():
    # Budget 2023-24 Statement 4B Grand Total prints "1209949.5" with the final "9" on the line below.
    gt = next(i for i in parsed("2023-24", "central_sector")["items"] if i["level"] == "grand_total")
    assert gt["values"][("2021-22", "Actual")]["total"] == 1209949.59


def test_2017_18_layout_components_and_department_in_brackets():
    r = parsed("2017-18", "css")
    mg = find(r, "Mahatma Gandhi National Rural Employment Guarantee")
    assert mg["department"] == "Department of Rural Development"
    sc = find(r, "Umbrella Scheme for Development of Schedule Castes")
    comps = [i for i in r["items"] if i["level"] == "component" and i["parent"] == sc["number"]]
    assert [c["number"] for c in comps] == ["a", "b"]
    for period, v in sc["values"].items():
        assert round(sum(c["values"][period]["total"] or 0 for c in comps), 2) == v["total"]


def test_roman_numbered_rows_under_others_are_schemes():
    r = parsed("2020-21", "css")
    others = [i for i in r["items"] if i["level"] == "scheme" and i["category"] == "C"]
    assert [i["number"] for i in others] == ["I", "II", "III", "IV", "V", "VI"]


def test_rows_missing_from_text_layer_come_from_reviewed_image_readings():
    r = parsed("2025-26", "css")
    gt = next(i for i in r["items"] if i["level"] == "grand_total")
    assert gt["values"][("2025-26", "BE")]["total"] == 541850.21
    assert any("Grand Total row is printed" in f for f in r["text_layer_fixes"])


def test_image_reading_refuses_when_the_text_layer_changes():
    lines = [Line("Others -", ["17145.01", "-29.05", "17115.96", "-8034.42"] + ["..."] * 8, 5, 445.0)]
    with pytest.raises(ParseError):
        apply_text_layer_fixes(lines, "2025-26", "css")


def test_text_is_not_a_value():
    with pytest.raises(ParseError):
        parse_value("Estimates", "test")
    assert parse_value("....", "test") is None
    assert parse_value("37*340.71", "test") == 37340.71


def test_all_scheme_checks_pass():
    data = load_all()
    with (ROOT / "data" / "observations.csv").open() as f:
        summary = list(csv.DictReader(f))
    failures = [x for _, _, fails, _ in checks(data, summary) for x in fails]
    assert failures == []
    # Every statement was read from its PDF.
    assert all(e["primary"] == "pdf" for by_type in data["budgets"].values() for e in by_type.values())

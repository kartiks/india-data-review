"""Every entry in annotations.py is still needed: each known exception matches a message of its check, each note
lands on a published figure, and each heading fix changes a heading the parser would otherwise refuse.

Run on the committed data/ and sources/ (read only; scripts/ci.sh checks they are what the pipeline builds), so no
document is parsed again except the one spreadsheet a heading fix applies to."""

import json

import pytest
from pipeline_common.report import Report
from pipeline_common.text import fy_start

from budget_pipeline import annotations, build, checks
from budget_pipeline.parse import ParseError, parse_document
from budget_pipeline.readers import read_any


@pytest.fixture(scope="module")
def observations():
    return checks.load_observations()


def test_every_headline_exception_matches_a_message(observations):
    dataset = json.loads((checks.DATA / "fiscal.json").read_text())
    checks.EXCEPTIONS.reset()
    try:
        report = Report("test")
        checks.check_identities(observations, report)
        checks.check_cross_document(observations, report)
        checks.check_pct_gdp(observations, dataset["gdp_stated_in_budget"], report)
        checks.check_formats(report)
        checks.check_reference(dataset, report)
        unused = checks.EXCEPTIONS.unused()
    finally:
        checks.EXCEPTIONS.reset()
    assert [f for s in report.sections for f in s.failures] == []
    # KNOWN_EXCEPTIONS, KNOWN_FORMAT_ISSUES and KNOWN_REFERENCE_DIFFS all end up in checks.EXCEPTIONS.
    assert len(checks.EXCEPTIONS.known) == (len(annotations.KNOWN_EXCEPTIONS) + len(annotations.KNOWN_FORMAT_ISSUES)
                                            + len(annotations.KNOWN_REFERENCE_DIFFS))
    assert unused == []


def test_every_source_note_is_attached_to_a_published_figure(observations):
    years = build.choose(observations)
    for (budget, year, kind, field), note in annotations.SOURCE_NOTES.items():
        chosen = years.get(year, {}).get(field, {}).values()
        assert any(v["source_budget"] == budget and v.get("note") == note for v in chosen), (budget, year, kind, field)


@pytest.mark.parametrize("budget, ext", sorted(annotations.HEADER_FIXES))
def test_every_heading_fix_is_needed(budget, ext):
    manifest = json.loads(build.MANIFEST.read_text())
    rows = read_any(build.ROOT / manifest[f"{budget}/summary/{ext}"]["file"])
    with pytest.raises(ParseError):
        parse_document(rows, fy_start(budget), ext != "pdf")
    for printed, corrected in annotations.HEADER_FIXES[(budget, ext)]:
        assert any(printed in c for r in rows for c in r), printed
        rows = [[c.replace(printed, corrected) for c in r] for r in rows]
    assert parse_document(rows, fy_start(budget), ext != "pdf")["observations"]

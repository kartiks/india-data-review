import json

from pipeline_common.report import FAILURE_MARK, Allowed, Report


def sample(fail: bool) -> Report:
    report = Report("Intro line.")
    allowed = Allowed()
    allowed.add("A known slip.", "case 1")
    allowed.add("A known slip.", "case 2")
    allowed.add("Another reason.", "case 3")
    report.add("First group", 10, [], ["a note"], allowed)
    report.add("Second group", 5, ["2020: off by 3"] if fail else [])
    return report


def test_markdown_passed():
    md = sample(fail=False).markdown()
    assert md.splitlines()[:5] == ["# Data validation report", "", "Intro line.", "", "**Result: PASSED** (15 checks, 0 failures)"]
    assert "## ✅ First group\n10 checks, 0 failures.\n" in md
    # allowed exceptions first, grouped by reason, then the notes
    assert ("- Allowed (2): A known slip. Cases: case 1; case 2\n- Allowed (1): Another reason. Cases: case 3\n"
            "- a note\n") in md
    assert FAILURE_MARK not in md


def test_markdown_failed():
    md = sample(fail=True).markdown()
    assert "**Result: FAILED** (15 checks, 1 failures)" in md
    assert f"## ❌ Second group\n5 checks, 1 failures.\n\n{FAILURE_MARK}2020: off by 3\n" in md


def test_allowed_cases_beyond_the_limit_are_counted():
    report = Report("x")
    allowed = Allowed()
    for i in range(5):
        allowed.add("Reason.", f"c{i}")
    report.add("Group", 5, [], allowed=allowed, limit=2)
    assert report.sections[0].notes == ["Allowed (5): Reason. Cases: c0; c1; and 3 more (see the CSV)"]
    assert report.summary()["allowed"] == 5


def test_summary_and_files(tmp_path, capsys):
    assert sample(fail=False).write(tmp_path) == 0
    summary = json.loads((tmp_path / "validation_summary.json").read_text())
    assert summary == {
        "result": "PASSED", "checks": 15, "failures": 0, "allowed": 3,
        "sections": [
            {"title": "First group", "checks": 10, "failures": 0, "allowed": 3,
             "allowed_reasons": [{"reason": "A known slip.", "cases": 2}, {"reason": "Another reason.", "cases": 1}]},
            {"title": "Second group", "checks": 5, "failures": 0, "allowed": 0, "allowed_reasons": []},
        ],
    }
    assert (tmp_path / "validation_report.md").read_text().startswith("# Data validation report")
    assert "ok   First group: 10 checks, 0 failures" in capsys.readouterr().out

    assert sample(fail=True).write(tmp_path) == 1
    summary = json.loads((tmp_path / "validation_summary.json").read_text())
    assert (summary["result"], summary["failures"], summary["sections"][1]["failures"]) == ("FAILED", 1, 1)
    assert "FAIL Second group: 5 checks, 1 failures" in capsys.readouterr().out

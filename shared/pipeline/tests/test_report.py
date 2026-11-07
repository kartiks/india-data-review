import hashlib
import json

import pytest

from pipeline_common import log as pipeline_log
from pipeline_common.report import FAILURE_MARK, Allowed, Exceptions, Report, data_hash, data_hashes


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
    assert ("- Allowed (2): A known slip. Cases:\n  - case 1\n  - case 2\n- Allowed (1): Another reason. Cases:\n"
            "  - case 3\n"
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
    assert report.sections[0].notes == ["Allowed (5): Reason. Cases:\n  - c0\n  - c1\n  - and 3 more (see the CSV)"]
    assert report.summary()["allowed"] == 5


def test_summary_and_files(tmp_path, capsys):
    pipeline_log.setup()  # as each pipeline command does: the summary lines go to stdout
    assert sample(fail=False).write(tmp_path) == 0
    summary = json.loads((tmp_path / "validation_summary.json").read_text())
    assert summary == {
        "result": "PASSED", "checks": 15, "failures": 0, "allowed": 3,
        "sections": [
            {"title": "First group", "checks": 10, "failures": 0, "allowed": 3,
             "allowed_reasons": [{"reason": "A known slip.", "cases": 2}, {"reason": "Another reason.", "cases": 1}]},
            {"title": "Second group", "checks": 5, "failures": 0, "allowed": 0, "allowed_reasons": []},
        ],
        "files": {},
    }
    assert (tmp_path / "validation_report.md").read_text().startswith("# Data validation report")
    assert "ok   First group: 10 checks, 0 failures" in capsys.readouterr().out

    assert sample(fail=True).write(tmp_path) == 1
    summary = json.loads((tmp_path / "validation_summary.json").read_text())
    assert (summary["result"], summary["failures"], summary["sections"][1]["failures"]) == ("FAILED", 1, 1)
    assert "FAIL Second group: 5 checks, 1 failures" in capsys.readouterr().out


def test_data_hash_ignores_the_build_time(tmp_path):
    f = tmp_path / "a.json"
    f.write_text('{\n "generated_at": "2026-01-01T00:00:00+00:00",\n "x": 1\n}\n')
    first = data_hash(f)
    assert first == hashlib.sha256(b'{\n ,\n "x": 1\n}\n').hexdigest()
    f.write_text('{\n "generated_at": "2026-11-03T13:05:17+00:00",\n "x": 1\n}\n')
    assert data_hash(f) == first
    f.write_text('{\n "generated_at": "2026-11-03T13:05:17+00:00",\n "x": 2\n}\n')
    assert data_hash(f) != first
    # compact JSON, as jobs_prices.json is written
    g = tmp_path / "b.json"
    g.write_text('{"generated_at":"2026-01-01T00:00:00+00:00","x":1}')
    compact = data_hash(g)
    g.write_text('{"generated_at":"2027-01-01T00:00:00+00:00","x":1}')
    assert data_hash(g) == compact
    g.write_text('{"generated_at":"2027-01-01T00:00:00+00:00","x":10}')
    assert data_hash(g) != compact


def test_data_hashes_lists_every_data_file(tmp_path):
    for name in ("b.csv", "a.json", "notes.md", "validation_report.md", "validation_summary.json", ".DS_Store", "x.txt"):
        (tmp_path / name).write_text(name)
    (tmp_path / "folder.json").mkdir()
    hashes = data_hashes(tmp_path)
    assert list(hashes) == ["a.json", "b.csv", "notes.md"]
    assert hashes["b.csv"] == hashlib.sha256(b"b.csv").hexdigest()


def test_write_records_the_hashes_of_the_data_it_checked(tmp_path, capsys):
    (tmp_path / "data.csv").write_text("year,value\n2020,1\n")
    sample(fail=False).write(tmp_path)
    summary = json.loads((tmp_path / "validation_summary.json").read_text())
    assert summary["files"] == {"data.csv": hashlib.sha256(b"year,value\n2020,1\n").hexdigest()}


# ---- known exceptions ----------------------------------------------------------------------------

def exceptions() -> Exceptions:
    return Exceptions(
        {("source", "row 7: year '1999'"): "A known slip.", ("growth", "2019-20 AE2"): "Mistyped."},
        [("identity", lambda m: m.startswith("back series") and " — printed " in m, "Back series."),
         ("identity", lambda m: "net taxes" in m, "Early net taxes.")])


def test_exceptions_known_by_check_and_message_prefix():
    ex = exceptions()
    assert ex.reason("source", "row 7: year '1999' left out") == "A known slip."
    assert ex.reason("growth", "row 7: year '1999' left out") is None  # another check
    assert ex.reason("source", "row 8: year '1999'") is None
    assert ex.reason("source", "left out: row 7: year '1999'") is None  # a prefix, not anywhere in the message


def test_exceptions_rules_and_which_known_ones_are_unused():
    ex = exceptions()
    assert ex.reason("identity", "back series 1990-91 — printed 100, parts give 95") == "Back series."
    assert ex.reason("identity", "back series 1990-91: missing storage") is None
    assert ex.reason("identity", "2014-15 AE1: GDP = GVA + net taxes") == "Early net taxes."
    assert ex.unused() == [("source", "row 7: year '1999'"), ("growth", "2019-20 AE2")]
    ex.reason("growth", "2019-20 AE2: published 3.3%")
    assert ex.unused() == [("source", "row 7: year '1999'")]
    ex.reset()
    assert len(ex.unused()) == 2


def test_exceptions_with_keys_other_than_check_names():
    # A check can be any key, such as a (budget, table) tuple. An empty prefix allows every message of that key;
    # a rule can look for a fragment anywhere in the message.
    ex = Exceptions({(("cross", "2010-11", "BE", "income_tax"), ""): "Restated."},
                    [(("2017-18", "Ministries"), lambda m: "Railways" in m, "Merged.")])
    assert ex.reason(("cross", "2010-11", "BE", "income_tax"), "anything") == "Restated."
    assert ex.reason(("cross", "2011-12", "BE", "income_tax"), "anything") is None
    assert ex.reason(("2017-18", "Ministries"), "Demand 80 Railways: off by 5") == "Merged."


def test_allowed_sort_out_files_known_messages_and_returns_failures():
    allowed = Allowed(exceptions())
    msgs = ["row 7: year '1999' left out", "row 9: unknown stage"]
    assert allowed.sort_out("source", msgs) == ["row 9: unknown stage"]
    assert allowed.sort_out("growth", ["2019-20 AE2: 3.3%", "2020-21 PE: 9%"]) == ["2020-21 PE: 9%"]
    allowed.add("Worked out by the check.", "case")
    assert allowed.counts() == [{"reason": "A known slip.", "cases": 1}, {"reason": "Mistyped.", "cases": 1},
                                {"reason": "Worked out by the check.", "cases": 1}]
    assert Allowed().sort_out("source", msgs) == msgs  # without exceptions every message is a failure


def test_allowed_more_hint():
    allowed = Allowed(more_hint="")
    for i in range(3):
        allowed.add("Reason.", f"c{i}")
    assert allowed.notes(limit=1) == ["Allowed (3): Reason. Cases:\n  - c0\n  - and 2 more"]
    report = Report("x")
    report.add("Group", 3, [], ["a note"], allowed, limit=1)
    assert report.sections[0].notes == ["Allowed (3): Reason. Cases:\n  - c0\n  - and 2 more", "a note"]
    assert report.summary()["sections"][0]["allowed_reasons"] == [{"reason": "Reason.", "cases": 3}]


def test_a_case_containing_the_separator_stays_one_bullet():
    allowed = Allowed()
    allowed.add("Reason.", "Karnataka: 2011-12 to 2025-26; left out")
    assert allowed.notes() == ["Allowed (1): Reason. Cases:\n  - Karnataka: 2011-12 to 2025-26; left out"]


@pytest.mark.parametrize("order", [1, -1])  # whatever order the entries are listed in
def test_the_longest_matching_prefix_wins_and_shorter_ones_stay_unused(order):
    entries = [(("source", ""), "Any source problem."), (("source", "row 7"), "Row 7."),
               (("source", "row 7: year"), "Row 7's year.")][::order]
    ex = Exceptions(dict(entries))
    assert ex.reason("source", "row 7: year '1999'") == "Row 7's year."
    assert ex.reason("source", "row 7: unit") == "Row 7."
    assert ex.unused() == [("source", "")]
    assert ex.reason("source", "row 8") == "Any source problem."
    assert ex.unused() == []


def test_contains_matches_a_fragment_anywhere_and_is_tracked():
    ex = Exceptions({("grand", "Demand 80"): "Prefix."},
                    contains={(("2017-18", "Ministries"), "Railways"): "Merged.",
                              (("2017-18", "Ministries"), "Railways Pension"): "Pensions moved.",
                              (("2018-19", "Ministries"), "Police"): "Moved."})
    assert ex.reason(("2017-18", "Ministries"), "Demand 80 Railways: off by 5") == "Merged."
    assert ex.reason(("2017-18", "Ministries"), "Demand 81 Railways Pension Fund: off") == "Pensions moved."
    assert ex.reason(("2017-18", "Ministries"), "Demand 82 Police") is None  # another key
    assert ex.unused() == [("grand", "Demand 80"), (("2018-19", "Ministries"), "Police")]


def test_a_case_recorded_apart_from_the_key_it_matched():
    # A check that matches a synthetic key ('demand_subtotal 80|BE 2017-18') records the readable message.
    check = ("2017-18", "central_sector", "group")
    allowed = Allowed(Exceptions({(check, "demand_subtotal 80|"): "Railways."}))
    assert allowed.file(check, "demand_subtotal 80|BE 2017-18", case="Demand 80, BE 2017-18: subtotal off by 5")
    assert not allowed.file(check, "demand_subtotal 81|BE 2017-18", case="Demand 81: off by 2")
    failures = allowed.sort_out(check, ["demand_subtotal 80|RE 2016-17", "demand_subtotal 81|RE 2016-17"],
                                cases=["Demand 80, RE 2016-17: off", "Demand 81, RE 2016-17: off"])
    assert failures == ["Demand 81, RE 2016-17: off"]  # the readable message, not the key
    assert allowed.cases == {"Railways.": ["Demand 80, BE 2017-18: subtotal off by 5", "Demand 80, RE 2016-17: off"]}
    with pytest.raises(ValueError):
        allowed.sort_out(check, ["a", "b"], cases=["only one"])

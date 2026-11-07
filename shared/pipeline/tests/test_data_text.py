"""The text check: every string in an area's data files, keys and values, JSON and CSV."""

import json

from pipeline_common import data_text
from pipeline_common.report import Report


def write(tmp_path, files: dict[str, str]):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def run(data_dir, allowed=None):
    report = Report("test")
    data_text.check_data_text(data_dir, report, allowed)
    return report.sections[0]


def test_clean_data_passes(tmp_path):
    d = write(tmp_path, {
        "a.json": json.dumps({"labels": {"state": ["Jammu & Kashmir", "Dadra & Nagar Haveli"]}, "n": [1, 2.5, None]}),
        "b.csv": "state,value\nGoa,1.5\n\"Andaman & Nicobar, Islands\",2\n",
        "validation_summary.json": json.dumps({"x": "<not data>"}),  # the checks' own output: not read
        "validation_report.md": "<b>",
        "notes.txt": "<b>",
    })
    s = run(d)
    # labels, state, n, the two names; then value, Goa and Andaman (numbers are not text; 'state' is counted once)
    assert s.failures == [] and s.checks == 8
    assert s.notes == ["Every key and text value (each distinct text counted once) in a.json, b.csv."]


def test_markup_and_control_characters_fail(tmp_path):
    d = write(tmp_path, {
        "a.json": json.dumps({"<k>": "ok", "items": [{"name": "Goa\u0007"}, {"name": "a\u2028b"}]}),
        "b.csv": "state,note\nGoa,\"line one\nline two\"\nBihar,</script>\n",
    })
    s = run(d)
    assert s.failures == [
        "a.json: key: '<k>' has '<', '>'",
        "a.json.items[0].name: 'Goa\\x07' has '\\x07'",
        "a.json.items[1].name: 'a\\u2028b' has '\\u2028'",
        "b.csv line 2, note: 'line one\\nline two' has '\\n'",
        "b.csv line 3, note: '</script>' has '<', '>'",
    ]


def test_allowed_cases_are_listed_with_their_reason(tmp_path):
    d = write(tmp_path, {"b.csv": "note\n<a>\n<b>\n"})
    s = run(d, lambda where, text: "the source prints it" if text == "<a>" else None)
    assert s.failures == ["b.csv line 3, note: '<b>' has '<', '>'"]
    assert s.allowed == [{"reason": "the source prints it", "cases": 1}]


def test_long_lists_of_failures_are_cut(tmp_path):
    d = write(tmp_path, {"b.csv": "note\n" + "".join(f"<{i}>\n" for i in range(60)) + "<0>\n"})
    s = run(d)
    assert len(s.failures) == data_text.MAX_LISTED + 1
    assert s.failures[0] == "b.csv line 2, note: '<0>' has '<', '>' (2 times)"
    assert s.failures[-1] == "and 10 more texts with these characters"


def test_no_data_folder_yet(tmp_path):
    s = run(tmp_path / "data")
    assert (s.checks, s.failures) == (0, []) and s.notes[0].startswith("No data files in")

"""pipeline_common.labels: new figures and periods are not new text; new states, items, units and notes are."""

import json

import pytest

from pipeline_common.labels import is_text, main, markdown, new_labels, pattern


# ---- pattern and is_text -------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    # figures, as JSON numbers turned to text or as CSV cells
    "794894.0", "-1.3", "1,00,000", "12.5", "0", "99",
    # years, fiscal years, months, quarters, halves, dates, times
    "2026", "2025-26", "1999-2000", "1986-1987", "2026-01", "Jan 2026", "January, 2026", "Jan-Mar 2026",
    "Apr-Jun", "Sept. 2025", "MAY 2026", "Q2 2025-26", "Q4", "H1 2026", "2026-11-06", "06/11/2026",
    "2026-11-06T09:30:00+00:00", "2026-10-30T15:13:12+00:00", "2026-11-06T093000Z", "2026-11-06 09:30",
    # SHA-256 hashes and punctuation
    "921fe9a26a309e77e8a40839a9681214210368fb511fe343b9a17c24ff29e623", "%", "-", "", "  ", "(2025-26)",
])
def test_periods_figures_and_hashes_are_not_text(text):
    assert not is_text(pattern(text)), pattern(text)


@pytest.mark.parametrize("text", [
    "Ladakh", "Andaman & Nicobar Islands", "₹ Crore", "₹", "Per Thousands", "rural + urban", "AE1",
    "https://api.mospi.gov.in/api/nas/getNASData?base_year=2011-12", "cpi/all_india/2013", "True", "NA",
])
def test_words_symbols_and_addresses_are_text(text):
    assert is_text(pattern(text))


@pytest.mark.parametrize("a, b", [
    ("Q2 2025-26 estimate", "Q3 2026-27 estimate"),
    ("Data for Jan 2026", "Data for Jan-Mar 2027"),
    ("cpi/all_india/2026", "cpi/all_india/2027"),
    ("cpi2024/2026-01", "cpi2024/2026-10"),
    ("https://api.mospi.gov.in/x?year=2026&state_code=99&Format=JSON",
     "https://api.mospi.gov.in/x?year=2027&state_code=1&Format=JSON"),
    ("Base year 2022-23, released 27 February 2026.", "Base year 2022-23, released 3 March 2027."),
    ("published twice with different real growth (3.2 and 3.3)", "published twice with different real growth (-0.4 and 0)"),
    ("snapshots/2026-11-06/x.json", "snapshots/2026-11-13T093000Z/x.json"),
])
def test_same_pattern_when_only_figures_and_periods_differ(a, b):
    assert pattern(a) == pattern(b)


@pytest.mark.parametrize("a, b", [
    ("₹ Crore", "₹ Lakh"),
    ("Rural Male", "Rural Female"),
    ("https://api.mospi.gov.in/api/nas", "https://example.com/api/nas"),
    ("General Index", "General index"),  # case counts
])
def test_different_pattern_when_words_differ(a, b):
    assert pattern(a) != pattern(b)


# ---- new_labels on folders -----------------------------------------------------------------------

def write(folder, name, content):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


@pytest.fixture
def old(tmp_path):
    d = tmp_path / "old"
    write(d, "gdp.json", {
        "generated_at": "2026-11-01T00:00:00+00:00",
        "units": "₹ crore",
        "growth": {"2024-25": {"gdp": 6.5, "note": "Provisional Estimate"}},
        "quarters": ["Q1 2025-26", "Q2 2025-26"],
        "sources": {"cpi/all_india/2025": {"url": "https://api.mospi.gov.in/a?year=2025",
                                            "sha256": "ab" * 32, "fetched_at": "2026-10-30T15:13:12+00:00"}},
    })
    write(d, "states.csv", "state,year,value,unit,generated_at\nKerala,2024-25,10.5,₹ Crore,2026-11-01\n"
                           "Goa,2024-25,3,₹ Crore,2026-11-01\n")
    write(d, "validation_report.md", "# Report\n\n12 checks passed\n")
    return d


@pytest.fixture
def new(tmp_path, old):
    d = tmp_path / "new"
    for p in old.rglob("*"):
        if p.is_file():
            write(d, p.relative_to(old).as_posix(), p.read_text(encoding="utf-8"))
    return d


def test_identical_data_has_no_new_labels(old, new):
    assert new_labels(old, new) == {}


def test_new_figures_months_quarters_and_build_time_are_not_new_labels(old, new):
    write(new, "gdp.json", {
        "generated_at": "A brand new build time format",  # ignored whatever it holds
        "units": "₹ crore",
        "growth": {"2024-25": {"gdp": 6.6, "note": "Provisional Estimate"},
                   "2025-26": {"gdp": 7.4, "note": "Provisional Estimate"}},
        "quarters": ["Q1 2025-26", "Q2 2025-26", "Q3 2025-26"],
        "sources": {"cpi/all_india/2025": {"url": "https://api.mospi.gov.in/a?year=2025",
                                            "sha256": "cd" * 32, "fetched_at": "2026-11-07T15:13:12+00:00"},
                    "cpi/all_india/2026": {"url": "https://api.mospi.gov.in/a?year=2026",
                                            "sha256": "ef" * 32, "fetched_at": "2026-11-07T15:14:00+00:00"}},
    })
    write(new, "states.csv", "state,year,value,unit,generated_at\nKerala,2024-25,10.7,₹ Crore,2026-11-08\n"
                             "Kerala,2025-26,11.0,₹ Crore,2026-11-08\nGoa,2025-26,3.2,₹ Crore,2026-11-08\n")
    write(new, "validation_report.md", "# Report\n\nA new sentence in the report, 13 checks passed\n")
    assert new_labels(old, new) == {}


def test_new_state_unit_note_key_and_address_are_new_labels(old, new):
    write(new, "gdp.json", {
        "generated_at": "2026-11-08T00:00:00+00:00",
        "units": "₹ lakh crore",
        "growth": {"2024-25": {"gdp": 6.5, "note": "First Revised Estimate", "revised": True}},
        "quarters": ["Q1 2025-26"],
        "sources": {"cpi/all_india/2025": {"url": "https://example.org/a?year=2025",
                                            "sha256": "ab" * 32, "fetched_at": "2026-10-30T15:13:12+00:00"}},
    })
    write(new, "states.csv", "state,year,value,unit,generated_at\nKerala,2024-25,10.5,₹ Crore,2026-11-01\n"
                             "Ladakh,2024-25,1,₹ Crore,2026-11-01\n")
    assert new_labels(old, new) == {
        "gdp.json": ["₹ lakh crore", "First Revised Estimate", "revised", "https://example.org/a?year=2025"],
        "states.csv": ["Ladakh"],
    }


def test_new_column_and_new_file_are_new_labels(old, new):
    write(new, "states.csv", "state,year,value,unit,flag\nKerala,2024-25,10.5,₹ Crore,\n")
    write(new, "sub/extra.json", {"note": "A new dataset"})
    assert new_labels(old, new) == {"states.csv": ["flag"], "sub/extra.json": ["note", "A new dataset"]}


def test_removed_text_and_removed_files_are_not_listed(old, new):
    write(new, "states.csv", "state,year,value,unit,generated_at\nKerala,2024-25,10.5,₹ Crore,2026-11-01\n")
    (new / "gdp.json").unlink()
    assert new_labels(old, new) == {}


def test_text_is_compared_within_the_same_file(old, new):
    # 'Kerala' is in states.csv, but new to gdp.json
    write(new, "gdp.json", json.loads((old / "gdp.json").read_text(encoding="utf-8")) | {"state": "Kerala"})
    assert new_labels(old, new) == {"gdp.json": ["state", "Kerala"]}


def test_a_missing_old_folder_makes_everything_new(tmp_path, new):
    found = new_labels(tmp_path / "nothing", new)
    assert set(found) == {"gdp.json", "states.csv"}
    assert "Kerala" in found["states.csv"] and "2024-25" not in found["states.csv"]


# ---- markdown and the command line ---------------------------------------------------------------

def test_markdown_lists_each_file_and_cuts_long_lists():
    text = markdown({"a.json": [f"label {chr(97 + i)}" for i in range(5)], "b.csv": ["x `y`\nz" + "w" * 300]},
                    limit=3)
    lines = text.splitlines()
    assert lines[:5] == ["- `a.json`: 5 new", "  - `label a`", "  - `label b`", "  - `label c`", "  - … and 2 more"]
    assert lines[5] == "- `b.csv`: 1 new"
    assert lines[6].startswith("  - `x 'y' zwww") and lines[6].endswith("…`") and len(lines[6]) < 220
    assert markdown({}) == ""


def test_main_exit_status_and_output(old, new, capsys):
    assert main([str(old), str(new)]) == 0
    assert capsys.readouterr().out == ""
    write(new, "states.csv", "state,year\nLadakh,2024-25\n")
    assert main([str(old), str(new)]) == 1
    assert capsys.readouterr().out == "- `states.csv`: 1 new\n  - `Ladakh`\n"


def test_main_refuses_bad_arguments_and_unreadable_data(old, new, tmp_path, capsys):
    assert main([str(old)]) == 2
    assert main([str(old), str(tmp_path / "missing")]) == 2
    write(new, "gdp.json", "{not json")
    assert main([str(old), str(new)]) == 2
    assert "cannot read" in capsys.readouterr().err
    assert main(["--help"]) == 0

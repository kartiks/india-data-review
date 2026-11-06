"""Reading MoSPI's files: the current download and the earlier versions kept in sources/snapshots/."""

import json

import pytest
from pipeline_common.text import prev_fy

from gdp_pipeline import build

KEY = "nas/2022-23/Current/Annually/ind05"


def gdp_row(year, stage, cur, quarter=None):
    return {"year": year, "indicator": "Gross Domestic Product", "revision": stage, "quarter": quarter,
            "current_price": str(cur), "constant_price": str(cur), "unit": "₹ Crore"}


@pytest.fixture
def sources(tmp_path, monkeypatch):
    """Writes the given versions of ind05 (newest first) under tmp_path and returns their manifest."""
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "NAS_SERIES", [("2022-23", "Current", "Annually")])
    monkeypatch.setattr(build, "NAS_INDICATORS", [5])

    def write(*versions):
        files = []
        for i, rows in enumerate(versions):
            path = f"sources/raw/{KEY}.json" if i == 0 else f"sources/snapshots/2026-0{9 - i}-01/{KEY}.json"
            (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / path).write_text(json.dumps({"rows": rows}))
            files.append({"file": path, "sha256": f"sha{i}", "fetched_at": f"2026-0{9 - i}-01T00:00:00+00:00"})
        entry = {"url": "https://api.example/nas", **files[0], "history": files[:0:-1]}  # history: oldest first
        return {KEY: entry}
    return write


def gdp_by_stage(rows):
    return {(r["year"], r["stage"]): (r["current_price"], r["source_sha256"]) for r in rows}


def test_without_history_only_the_current_file_is_read(sources):
    rows, problems, earlier = build.load_rows(sources([gdp_row("2025-26", "Provisional Estimates", 100)]))
    assert gdp_by_stage(rows) == {("2025-26", "PE"): (100.0, "sha0")} and problems == [] and earlier == []


def test_an_estimate_the_current_file_no_longer_has_is_read_from_its_snapshot(sources):
    manifest = sources(
        [gdp_row("2024-25", "Final Estimates", 300), gdp_row("2025-26", "First Revised Estimates", 210)],
        [gdp_row("2024-25", "First Revised Estimates", 290), gdp_row("2025-26", "Provisional Estimates", 200)],
    )
    rows, problems, earlier = build.load_rows(manifest)
    assert gdp_by_stage(rows) == {
        ("2024-25", "FINAL"): (300.0, "sha0"), ("2025-26", "RE1"): (210.0, "sha0"),
        ("2024-25", "RE1"): (290.0, "sha1"), ("2025-26", "PE"): (200.0, "sha1"),
    }
    assert problems == []
    assert earlier == [
        {"series": "2022-23", "frequency": "annual", "year": "2024-25", "quarter": "", "stage": "RE1",
         "fetched_on": "2026-08-01", "indicators": ["gdp"]},
        {"series": "2022-23", "frequency": "annual", "year": "2025-26", "quarter": "", "stage": "PE",
         "fetched_on": "2026-08-01", "indicators": ["gdp"]},
    ]
    node = build.arrange(rows)["2022-23"]["annual"]["2025-26"]
    assert node["PE"]["gdp"] == {"cur": 200.0, "con": 200.0} and build.latest_stage(node) == "RE1"


def test_the_newest_version_wins_for_an_estimate_several_have(sources):
    manifest = sources(
        [gdp_row("2025-26", "Provisional Estimates", 205)],  # current: PE revised in place
        [gdp_row("2025-26", "Provisional Estimates", 200), gdp_row("2024-25", "First Revised Estimates", 290)],
        [gdp_row("2025-26", "Second Advance Estimates", 190), gdp_row("2024-25", "First Revised Estimates", 280)],
    )
    rows, _, earlier = build.load_rows(manifest)
    assert gdp_by_stage(rows) == {
        ("2025-26", "PE"): (205.0, "sha0"),  # the current file, not either snapshot
        ("2024-25", "RE1"): (290.0, "sha1"),  # the newer snapshot, not the older one
        ("2025-26", "AE2"): (190.0, "sha2"),
    }
    assert [(e["year"], e["stage"], e["fetched_on"]) for e in earlier] == [
        ("2024-25", "RE1", "2026-08-01"), ("2025-26", "AE2", "2026-07-01")]


def test_figures_without_a_stage_of_their_own_come_from_the_current_file_only(sources, monkeypatch):
    monkeypatch.setattr(build, "NAS_SERIES", [("2022-23", "Current", "Quarterly")])
    key = "nas/2022-23/Current/Quarterly/ind05"
    manifest = sources([gdp_row("2025-26", None, 52, quarter="Q1")],
                       [gdp_row("2025-26", None, 50, quarter="Q1"), gdp_row("2025-26", None, 55, quarter="Q2")])
    manifest = {key: manifest[KEY]}
    rows, _, earlier = build.load_rows(manifest)
    assert [(r["quarter"], r["stage"], r["current_price"]) for r in rows] == [("Q1", "LATEST", 52.0)]
    assert earlier == []


def test_problems_in_a_snapshot_are_reported_once(sources):
    def bad(stage):
        return {**gdp_row("2025-26", stage, 1), "industry": "Space Mining"}
    manifest = sources([bad("First Revised Estimates")], [bad("Provisional Estimates")])
    rows, problems, _ = build.load_rows(manifest)
    assert len(rows) == 2 and problems == [f"{KEY}: unknown industry 'Space Mining'"]


def test_a_year_written_in_full_is_read_in_the_short_form(sources):
    # MoSPI's back series writes 1999-2000; the year before 2000-01 must be found under prev_fy's '1999-00'.
    pe, ae2 = "Provisional Estimates", "Second Advance Estimates"
    manifest = sources([gdp_row("1999-2000", pe, 205), gdp_row("2000-01", pe, 210)],
                       [gdp_row("1999-00", pe, 200), gdp_row("1999-00", ae2, 190)])
    rows, problems, _ = build.load_rows(manifest)
    assert problems == []
    # the newest version wins for 1999-00 PE, whichever way each version writes the year
    assert gdp_by_stage(rows) == {("1999-00", "PE"): (205.0, "sha0"), ("2000-01", "PE"): (210.0, "sha0"),
                                  ("1999-00", "AE2"): (190.0, "sha1")}
    annual = build.arrange(rows)["2022-23"]["annual"]
    assert set(annual) == {"1999-00", "2000-01"} and annual[prev_fy("2000-01")]["PE"]["gdp"]["cur"] == 205.0


def read(code, unit, value="100"):
    r = {"year": "2023-24", "revision": "Final Estimates", "indicator": "x", "current_price": value,
         "constant_price": value, "unit": unit}
    return build.read_row(r, f"nas/2022-23/Current/Annually/ind{code:02d}", "2022-23", "Current", "Annually", code,
                          "https://api.example/nas", "sha")


@pytest.mark.parametrize("code, unit", [(5, "₹ Crore"), (22, "%"), (3, "₹ Lakh"), (4, "₹ Lakh")])
def test_each_indicator_s_own_unit_is_read_as_published(code, unit):
    row, problems = read(code, unit, "2079741")
    # taxes and subsidies on products are labelled ₹ lakh but are in ₹ crore: never divided
    assert problems == [] and build.pair(row) == {"cur": 2079741.0, "con": 2079741.0}


@pytest.mark.parametrize("code, unit", [(5, "₹ Lakh"), (5, "₹ Billion"), (5, None), (22, "₹ Crore"),
                                        (3, "₹ Crore"), (1, "%")])
def test_a_row_in_another_unit_is_left_out_and_reported(code, unit):
    row, problems = read(code, unit)
    expected = build.UNITS[build.INDICATORS[code][0]]
    assert row is None and problems == [f"nas/2022-23/Current/Annually/ind{code:02d}: unit {unit!r}, expected "
                                        f"{expected!r}; row left out (2023-24 Final Estimates)"]


def test_snapshots_named_by_date_or_by_time_are_read_newest_first(tmp_path, monkeypatch):
    # Snapshot folders were named by date ('2026-08-01'), now by time ('2026-08-01T120000Z'); old ones keep their
    # names. Versions are read in the order of the manifest's history, whatever the folders are called.
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "NAS_SERIES", [("2022-23", "Current", "Annually")])
    monkeypatch.setattr(build, "NAS_INDICATORS", [5])
    pe = "Provisional Estimates"
    versions = [("sources/raw", "2026-09-01T00:00:00+00:00", 230),
                ("sources/snapshots/2026-08-01T120000Z", "2026-08-01T12:00:00+00:00", 220),
                ("sources/snapshots/2026-08-01", "2026-08-01T06:00:00+00:00", 210),
                ("sources/snapshots/2026-07-01", "2026-07-01T00:00:00+00:00", 200)]
    files = []
    for i, (folder, at, value) in enumerate(versions):
        rows = [gdp_row("2025-26", "Second Advance Estimates", value)] + ([gdp_row("2025-26", pe, value)] if i else [])
        (tmp_path / folder / f"{KEY}.json").parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / folder / f"{KEY}.json").write_text(json.dumps({"rows": rows}))
        files.append({"file": f"{folder}/{KEY}.json", "sha256": f"sha{i}", "fetched_at": at})
    entry = {"url": "https://api.example/nas", **files[0], "history": files[:0:-1]}  # history: oldest first
    rows, _, earlier = build.load_rows({KEY: entry})
    assert gdp_by_stage(rows) == {("2025-26", "AE2"): (230.0, "sha0"), ("2025-26", "PE"): (220.0, "sha1")}
    assert [e["fetched_on"] for e in earlier] == ["2026-08-01"]

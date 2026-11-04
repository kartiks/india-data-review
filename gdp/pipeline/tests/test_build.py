"""Reading MoSPI's files: the current download and the earlier versions kept in sources/snapshots/."""

import json

import pytest

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

"""The refresh logic in fetch.py, with MoSPI's API replaced by a stub (no network)."""

import json

import pytest

from gdp_pipeline import fetch


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "ROOT", tmp_path)
    monkeypatch.setattr(fetch, "RAW", tmp_path / "sources" / "raw")
    monkeypatch.setattr(fetch, "SNAPSHOTS", tmp_path / "sources" / "snapshots")
    monkeypatch.setattr(fetch, "NAS_SERIES", [("2022-23", "Current", "Annual")])
    monkeypatch.setattr(fetch, "NAS_INDICATORS", [1, 2])
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    return tmp_path


def stub(rows_by_code):
    calls = []

    def fetch_nas(base, series, freq, code):
        calls.append(code)
        rows = rows_by_code[code]
        return {"url": f"https://example.test/{code}", "rows": rows, "total_records": len(rows)}

    return fetch_nas, calls


KEY1 = "nas/2022-23/Current/Annual/ind01"
KEY2 = "nas/2022-23/Current/Annual/ind02"


def test_refresh_snapshots_a_revision(sandbox, monkeypatch):
    manifest = {}
    fetch_nas, _ = stub({1: [{"v": 1}], 2: [{"v": 2}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    fetch.fetch_all_nas(manifest, force=False)
    first = manifest[KEY1]["fetched_at"][:10]

    fetch_nas, _ = stub({1: [{"v": 10}], 2: [{"v": 2}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    fetch.fetch_all_nas(manifest, force=True)

    assert json.loads((fetch.RAW / f"{KEY1}.json").read_text())["rows"] == [{"v": 10}]
    snap = fetch.SNAPSHOTS / first / f"{KEY1}.json"
    assert json.loads(snap.read_text())["rows"] == [{"v": 1}]
    assert manifest[KEY1]["history"][0]["file"] == str(snap.relative_to(sandbox))
    assert not (fetch.SNAPSHOTS / first / f"{KEY2}.json").exists()  # unchanged: no snapshot


def test_without_force_only_missing_indicators_are_fetched(sandbox, monkeypatch):
    manifest = {}
    fetch_nas, _ = stub({1: [{"v": 1}], 2: [{"v": 2}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    fetch.fetch_all_nas(manifest, force=False)
    del manifest[KEY2]

    fetch_nas, calls = stub({1: [{"v": 1}], 2: [{"v": 2}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    fetch.fetch_all_nas(manifest, force=False)
    assert calls == [2]


def test_vanished_indicator_keeps_the_saved_file_and_fails(sandbox, monkeypatch):
    manifest = {}
    fetch_nas, _ = stub({1: [{"v": 1}], 2: [{"v": 2}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    fetch.fetch_all_nas(manifest, force=False)
    saved = manifest[KEY1].copy()

    fetch_nas, calls = stub({1: [], 2: [{"v": 20}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    with pytest.raises(RuntimeError, match=KEY1):
        fetch.fetch_all_nas(manifest, force=True)

    assert calls == [1, 2]  # carried on past the empty one
    assert manifest[KEY1]["sha256"] == saved["sha256"]
    assert json.loads((fetch.RAW / f"{KEY1}.json").read_text())["rows"] == [{"v": 1}]
    assert json.loads((fetch.RAW / f"{KEY2}.json").read_text())["rows"] == [{"v": 20}]


def test_indicator_that_never_had_data_is_recorded_as_empty(sandbox, monkeypatch):
    manifest = {}
    fetch_nas, _ = stub({1: [], 2: [{"v": 2}]})
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)
    fetch.fetch_all_nas(manifest, force=True)
    assert manifest[KEY1]["empty"] is True

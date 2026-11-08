"""Reading the downloaded files: rows MoSPI withdrew are kept from the newest earlier download that has them."""

import json

import pytest

from jobs_prices_pipeline import common

KEY = "plfs/monthly/ind01"


@pytest.fixture
def area(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "queries", lambda: [(KEY, "plfs/getData", {}), ("plfs/monthly/ind02", "plfs/getData", {})])
    monkeypatch.setattr(common, "WITHDRAWN", {KEY: {"year": "2026", "month": "March"}})
    return tmp_path


def write(root, path, rows):
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(json.dumps({"query": {}, "rows": rows}))
    return path


def row(month, v, year="2026"):
    return {"year": year, "month": month, "value": v}


def test_withdrawn_rows_come_from_the_newest_download_that_has_them(area):
    oldest = write(area, "sources/snapshots/a/x.json", [row("February", "1"), row("March", "old")])
    newer = write(area, "sources/snapshots/b/x.json", [row("February", "1"), row("March", "new")])
    no_march = write(area, "sources/snapshots/c/x.json", [row("February", "1")])
    current = write(area, "sources/raw/x.json", [row("February", "2")])
    manifest = {KEY: {"file": current, "history": [{"file": oldest}, {"file": newer}, {"file": no_march}]}}
    (_, _, body), = common.load(manifest, "plfs/")
    assert body["rows"] == [row("February", "2"), row("March", "new")]
    assert body["kept"] == {"file": newer, "rows": 1}


def test_nothing_is_kept_when_the_current_download_has_the_rows(area):
    old = write(area, "sources/snapshots/a/x.json", [row("March", "old")])
    current = write(area, "sources/raw/x.json", [row("March", "back")])
    (_, _, body), = common.load({KEY: {"file": current, "history": [{"file": old}]}}, "plfs/")
    assert body["rows"] == [row("March", "back")] and "kept" not in body


def test_other_files_are_read_as_they_are(area):
    current = write(area, "sources/raw/y.json", [row("February", "2")])
    (key, _, body), = common.load({"plfs/monthly/ind02": {"file": current}}, "plfs/")
    assert key == "plfs/monthly/ind02" and body["rows"] == [row("February", "2")] and "kept" not in body


def test_withdrawn_rows_in_no_download_stop_the_build(area):
    current = write(area, "sources/raw/x.json", [row("February", "2")])
    with pytest.raises(RuntimeError, match="no download has the rows"):
        common.load({KEY: {"file": current}}, "plfs/")

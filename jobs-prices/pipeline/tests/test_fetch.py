"""The refresh logic in fetch.py, with MoSPI's API and the document downloads replaced by stubs (no network)."""

import json

import pytest

from jobs_prices_pipeline import fetch

KEY1 = "plfs/annual/ind01"
KEY2 = "plfs/annual/ind02"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "ROOT", tmp_path)
    monkeypatch.setattr(fetch, "RAW", tmp_path / "sources" / "raw")
    monkeypatch.setattr(fetch, "SNAPSHOTS", tmp_path / "sources" / "snapshots")
    monkeypatch.setattr(fetch, "MANIFEST", tmp_path / "sources" / "manifest.json")
    monkeypatch.setattr(fetch, "queries", lambda: [(KEY1, "plfs/getData", {"i": 1}), (KEY2, "plfs/getData", {"i": 2})])
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    docs = []
    monkeypatch.setattr(fetch, "fetch_cpi2024", lambda m, force: docs.append(("cpi2024", force)))
    monkeypatch.setattr(fetch, "fetch_hces_tables", lambda m, force: docs.append(("hces", force)))
    monkeypatch.setattr(fetch, "fetch_rbi", lambda m, force: docs.append(("rbi", force)))
    return docs


def use_api(monkeypatch, rows_by_key):
    calls = []

    def fetch_query(path, params):
        key = KEY1 if params["i"] == 1 else KEY2
        calls.append(key)
        rows = rows_by_key[key]
        return {"source": "test", "query": params, "url": f"https://example.test/{key}",
                "total_records": len(rows), "rows": rows}

    monkeypatch.setattr(fetch, "fetch_query", fetch_query)
    return calls


def saved_rows(key):
    return json.loads((fetch.RAW / f"{key}.json").read_text())["rows"]


def test_refresh_api_re_downloads_api_and_rbi_only(sandbox, monkeypatch):
    use_api(monkeypatch, {KEY1: [{"v": 1}], KEY2: [{"v": 2}]})
    fetch.main()
    sandbox.clear()

    calls = use_api(monkeypatch, {KEY1: [{"v": 1}], KEY2: [{"v": 2}]})
    fetch.main(force_api=True)
    assert calls == [KEY1, KEY2]
    # Press releases and report tables: only if missing. RBI tables: re-downloaded.
    assert sandbox == [("cpi2024", False), ("hces", False), ("rbi", True)]


def test_without_flags_saved_queries_are_not_fetched(sandbox, monkeypatch):
    use_api(monkeypatch, {KEY1: [{"v": 1}], KEY2: [{"v": 2}]})
    fetch.main()
    calls = use_api(monkeypatch, {KEY1: [{"v": 1}], KEY2: [{"v": 2}]})
    fetch.main()
    assert calls == []


def test_revision_is_snapshotted(sandbox, monkeypatch):
    use_api(monkeypatch, {KEY1: [{"v": 1}], KEY2: [{"v": 2}]})
    fetch.main()
    first = json.loads(fetch.MANIFEST.read_text())[KEY1]["fetched_at"][:10]

    use_api(monkeypatch, {KEY1: [{"v": 10}], KEY2: [{"v": 2}]})
    fetch.main(force_api=True)
    assert saved_rows(KEY1) == [{"v": 10}]
    assert json.loads((fetch.SNAPSHOTS / first / f"{KEY1}.json").read_text())["rows"] == [{"v": 1}]
    assert not (fetch.SNAPSHOTS / first / f"{KEY2}.json").exists()


def test_vanished_query_keeps_the_saved_file_and_fails(sandbox, monkeypatch):
    use_api(monkeypatch, {KEY1: [{"v": 1}], KEY2: [{"v": 2}]})
    fetch.main()
    sha = json.loads(fetch.MANIFEST.read_text())[KEY1]["sha256"]
    sandbox.clear()

    calls = use_api(monkeypatch, {KEY1: [], KEY2: [{"v": 20}]})
    with pytest.raises(RuntimeError, match=KEY1):
        fetch.main(force_api=True)

    assert calls == [KEY1, KEY2]  # carried on past the empty one
    assert [name for name, _ in sandbox] == ["cpi2024", "hces", "rbi"]  # and the documents
    manifest = json.loads(fetch.MANIFEST.read_text())  # written even though it failed
    assert manifest[KEY1]["sha256"] == sha
    assert saved_rows(KEY1) == [{"v": 1}]
    assert saved_rows(KEY2) == [{"v": 20}]

"""fetch_nas against a stubbed MoSPI API: every page read and combined, failures tried again, short answers refused.
The real download.get runs, with its opener replaced (no network) and no waiting between tries or pages."""

import io
import json
import urllib.error
import urllib.parse
from contextlib import contextmanager

import pytest
from pipeline_common import download

from gdp_pipeline import fetch
from gdp_pipeline.sources import NAS_API, NAS_PAGE_LIMIT


REAL_GET = download.get


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    waits = []
    monkeypatch.setattr(download.time, "sleep", waits.append)  # the time module fetch.py uses too
    return waits


class Response(io.BytesIO):
    def __init__(self, body: bytes, length: int | None = None):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body) if length is None else length)}


def api(monkeypatch, answer):
    """Route download.get through an opener that asks answer(page, attempt) for each request: a dict (the JSON
    body), bytes (a raw body), a Response, or an exception to raise. Returns the list of (page, query) asked."""
    asked = []

    @contextmanager
    def opener(req, timeout):
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(req.full_url).query))
        page = int(query["page"])
        attempt = sum(1 for p, _ in asked if p == page)
        asked.append((page, query))
        out = answer(page, attempt)
        if isinstance(out, Exception):
            raise out
        if isinstance(out, dict):
            out = json.dumps(out).encode()
        yield out if isinstance(out, Response) else Response(out)

    monkeypatch.setattr(download, "get", lambda url: REAL_GET(url, opener=opener))
    return asked


def body(rows, total, pages):
    return {"data": rows, "meta_data": {"totalRecords": total, "totalPages": pages}}


PAGES = {1: [{"year": "2023-24", "v": 3}, {"year": "2022-23", "v": 1}], 2: [{"year": "2024-25", "v": 2}]}


def test_every_page_is_read_and_the_rows_combined_in_a_stable_order(monkeypatch):
    asked = api(monkeypatch, lambda page, _: body(PAGES[page], 3, 2))
    result = fetch.fetch_nas("2022-23", "Current", "Annually", 5)
    assert [r["v"] for r in result["rows"]] == [1, 2, 3]  # sorted, whatever order the pages came in
    assert result["total_records"] == 3
    assert [p for p, _ in asked] == [1, 2]
    query = {"base_year": "2022-23", "series": "Current", "frequency_code": "Annually", "indicator_code": "5"}
    assert all(q == {**query, "limit": str(NAS_PAGE_LIMIT), "page": str(p)} for p, q in asked)
    # the recorded address names the query, not one page of it
    assert result["url"] == f"{NAS_API}?{urllib.parse.urlencode(fetch.nas_query('2022-23', 'Current', 'Annually', 5))}"
    assert result["query"] == fetch.nas_query("2022-23", "Current", "Annually", 5)


def test_the_same_rows_served_in_another_order_give_an_identical_file(monkeypatch):
    api(monkeypatch, lambda page, _: body(PAGES[page], 3, 2))
    a = fetch.fetch_nas("2022-23", "Current", "Annually", 5)
    api(monkeypatch, lambda page, _: body(PAGES[3 - page][::-1], 3, 2))
    b = fetch.fetch_nas("2022-23", "Current", "Annually", 5)
    assert json.dumps(a) == json.dumps(b)


def test_a_server_error_or_dropped_connection_on_one_page_is_tried_again(monkeypatch, no_waiting):
    def answer(page, attempt):
        if page == 2 and attempt == 0:
            return urllib.error.HTTPError("u", 503, "busy", {}, None)
        if page == 2 and attempt == 1:
            return urllib.error.URLError("connection reset")
        return body(PAGES[page], 3, 2)

    asked = api(monkeypatch, answer)
    result = fetch.fetch_nas("2022-23", "Current", "Annually", 5)
    assert result["total_records"] == 3
    assert [p for p, _ in asked] == [1, 2, 2, 2]  # page 1 is not asked again
    backoff = [w for w in no_waiting if w != download.PAGE_PAUSE_S]
    assert backoff == [download.BACKOFF_S, 2 * download.BACKOFF_S]


def test_a_page_cut_short_is_tried_again_not_read(monkeypatch):
    full = json.dumps(body(PAGES[1] + PAGES[2], 3, 1)).encode()

    def answer(page, attempt):
        return Response(full[:20], length=len(full)) if attempt == 0 else full

    asked = api(monkeypatch, answer)
    assert fetch.fetch_nas("2022-23", "Current", "Annually", 5)["total_records"] == 3
    assert len(asked) == 2


def test_a_client_error_is_not_tried_again(monkeypatch):
    asked = api(monkeypatch, lambda page, _: urllib.error.HTTPError("u", 404, "not found", {}, None))
    with pytest.raises(urllib.error.HTTPError):
        fetch.fetch_nas("2022-23", "Current", "Annually", 5)
    assert len(asked) == 1


def test_the_api_failing_every_try_raises(monkeypatch):
    asked = api(monkeypatch, lambda page, _: urllib.error.HTTPError("u", 500, "error", {}, None))
    with pytest.raises(urllib.error.HTTPError):
        fetch.fetch_nas("2022-23", "Current", "Annually", 5)
    assert len(asked) == download.TRIES


def test_rows_that_do_not_add_up_to_the_total_raise(monkeypatch):
    # page 2 comes back empty although the API promised 3 rows over 2 pages
    api(monkeypatch, lambda page, _: body(PAGES[1] if page == 1 else [], 3, 2))
    with pytest.raises(RuntimeError, match="got 2 rows, API says 3"):
        fetch.fetch_nas("2022-23", "Current", "Annually", 5)


def test_an_indicator_with_no_data_gives_no_rows(monkeypatch):
    asked = api(monkeypatch, lambda page, _: {"data": None, "meta_data": None})
    result = fetch.fetch_nas("2022-23", "Current", "Quarterly", 13)
    assert result["rows"] == [] and result["total_records"] == 0 and len(asked) == 1


def test_a_body_that_is_not_json_raises(monkeypatch):
    api(monkeypatch, lambda page, _: b"<html>Service Unavailable</html>")
    with pytest.raises(json.JSONDecodeError):
        fetch.fetch_nas("2022-23", "Current", "Annually", 5)


# ---- fetch_all_nas: an answer far shorter than the saved file is refused -----------------------------------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "ROOT", tmp_path)
    monkeypatch.setattr(fetch, "RAW", tmp_path / "sources" / "raw")
    monkeypatch.setattr(fetch, "SNAPSHOTS", tmp_path / "sources" / "snapshots")
    monkeypatch.setattr(fetch, "MANIFEST", tmp_path / "sources" / "manifest.json")
    monkeypatch.setattr(fetch, "NAS_SERIES", [("2022-23", "Current", "Annually")])
    monkeypatch.setattr(fetch, "NAS_INDICATORS", [1, 2])
    monkeypatch.setattr(fetch, "STATE_SERIES", [])
    return tmp_path


def serve(monkeypatch, rows_by_code):
    def fetch_nas(base, series, freq, code):
        rows = rows_by_code[code]
        return {"url": f"https://example.test/{code}", "rows": rows, "total_records": len(rows)}
    monkeypatch.setattr(fetch, "fetch_nas", fetch_nas)


def test_a_much_shorter_answer_keeps_the_saved_file_and_fails_after_the_rest(sandbox, monkeypatch):
    key1, key2 = "nas/2022-23/Current/Annually/ind01", "nas/2022-23/Current/Annually/ind02"
    manifest = {}
    serve(monkeypatch, {1: [{"v": i} for i in range(100)], 2: [{"v": 1}]})
    fetch.fetch_all_nas(manifest, force=False)
    saved = manifest[key1]["sha256"]

    serve(monkeypatch, {1: [{"v": i} for i in range(90)], 2: [{"v": 2}]})  # 10% fewer rows
    with pytest.raises(RuntimeError, match=key1):
        fetch.fetch_all_nas(manifest, force=True)
    assert manifest[key1]["sha256"] == saved and manifest[key1]["records"] == 100
    assert len(json.loads((fetch.RAW / f"{key1}.json").read_text())["rows"]) == 100
    assert json.loads((fetch.RAW / f"{key2}.json").read_text())["rows"] == [{"v": 2}]  # the rest still refreshed

    serve(monkeypatch, {1: [{"v": i} for i in range(97)], 2: [{"v": 2}]})  # 3% fewer: a revision, accepted
    fetch.fetch_all_nas(manifest, force=True)
    assert manifest[key1]["records"] == 97 and manifest[key1]["history"]

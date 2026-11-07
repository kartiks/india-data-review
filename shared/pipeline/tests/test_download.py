"""The download helpers, with the network replaced by stubs."""

import io
import json
import urllib.error
from contextlib import contextmanager

import pytest

from pipeline_common import download


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    waits = []
    monkeypatch.setattr(download.time, "sleep", waits.append)
    return waits


def opener_failing(times: int, error: Exception, body: bytes = b"ok"):
    """An opener that raises `error` the first `times` calls, then returns body."""
    calls = []

    @contextmanager
    def opener(req, timeout):
        calls.append((req.full_url, req.get_header("User-agent"), timeout))
        if len(calls) <= times:
            raise error
        yield io.BytesIO(body)

    return opener, calls


# Every HTTPError holds a file (an empty one here) that must be closed, or Python warns (ResourceWarning) when it is
# garbage collected; the tests close the ones they make.
ERRORS: list[urllib.error.HTTPError] = []


@pytest.fixture(autouse=True)
def close_errors():
    yield
    while ERRORS:
        ERRORS.pop().close()


def made(error: urllib.error.HTTPError) -> urllib.error.HTTPError:
    ERRORS.append(error)
    return error


def http_error(code: int) -> urllib.error.HTTPError:
    return made(urllib.error.HTTPError("https://example.test/x", code, "error", {}, None))


def test_get_retries_network_errors_then_succeeds(no_waiting):
    opener, calls = opener_failing(2, urllib.error.URLError("connection reset"))
    assert download.get("https://example.test/x", opener=opener) == b"ok"
    assert len(calls) == 3
    assert no_waiting == [5, 10]  # backoff grows with each try
    assert calls[0][1] == download.USER_AGENT and "india-data-review" in download.USER_AGENT


def test_get_gives_up_after_the_last_try(no_waiting):
    opener, calls = opener_failing(99, TimeoutError("slow"))
    with pytest.raises(TimeoutError):
        download.get("https://example.test/x", opener=opener)
    assert len(calls) == download.TRIES == 5


def test_get_retries_server_errors_but_not_404(no_waiting):
    for code in (503, 408, 429):
        opener, calls = opener_failing(1, http_error(code))
        assert download.get("https://example.test/x", opener=opener) == b"ok"
    opener, calls = opener_failing(1, http_error(404))
    with pytest.raises(urllib.error.HTTPError):
        download.get("https://example.test/x", opener=opener)
    assert len(calls) == 1


def test_file_kind():
    assert download.file_kind(b"%PDF-1.7 ...") == "pdf"
    assert download.file_kind(b"PK\x03\x04") == "xlsx"
    assert download.file_kind(b"\xd0\xcf\x11\xe0\xa1\xb1") == "xls"
    assert download.file_kind(b"<html>not found</html>") == "html"
    assert download.file_kind(b"\r\n<!DOCTYPE html>\n<head>") == "html"
    assert download.file_kind(b"<?xml version='1.0'?><HTML><body>") == "html"
    assert download.file_kind(b' {"data": []}') == "json"
    assert download.file_kind(b"[1, 2]") == "json"
    assert download.file_kind(b"") is None and download.file_kind(b"plain text") is None


def test_get_refuses_a_download_past_the_size_cap(monkeypatch, no_waiting):
    monkeypatch.setattr(download, "MAX_BYTES", 10)
    opener, calls = opener_failing(0, AssertionError, body=b"x" * 11)
    with pytest.raises(download.TooLarge, match="more than 10 bytes"):
        download.get("https://example.test/x", opener=opener)
    assert len(calls) == 1  # not tried again
    opener, _ = opener_failing(0, AssertionError, body=b"x" * 10)
    assert download.get("https://example.test/x", opener=opener) == b"x" * 10


class Response(io.BytesIO):
    def __init__(self, body: bytes, length: int):
        super().__init__(body)
        self.headers = {"Content-Length": str(length)}


def test_get_retries_a_download_cut_short(no_waiting):
    """A dropped connection gives a short body with no error from read(n); Content-Length catches it."""
    bodies = [Response(b"%PDF-1.4 short", 1000), Response(b"%PDF-1.4 whole", 14)]

    @contextmanager
    def opener(req, timeout):
        yield bodies.pop(0)

    assert download.get("https://example.test/x", opener=opener) == b"%PDF-1.4 whole"
    assert bodies == [] and no_waiting == [5]

    @contextmanager
    def always_short(req, timeout):
        yield Response(b"%PDF", 1000)

    with pytest.raises(download.http.client.IncompleteRead):
        download.get("https://example.test/x", opener=always_short)


def redirect(old: str, new: str):
    req = download.urllib.request.Request(old)
    return download._NoDowngrade().redirect_request(req, None, 302, "Found", {}, new)


def test_redirects_from_https_to_http_are_refused():
    with pytest.raises(download.DowngradeRefused, match="from https to http://example.test/y") as e:
        redirect("https://example.test/x", "http://example.test/y")
    made(e.value)
    with pytest.raises(download.DowngradeRefused) as e:
        redirect("https://example.test/x", "ftp://example.test/y")
    made(e.value)
    assert redirect("https://example.test/x", "https://other.test/y").full_url == "https://other.test/y"
    assert redirect("http://example.test/x", "https://example.test/y").full_url == "https://example.test/y"
    assert not download._retryable(made(download.DowngradeRefused("https://example.test/x", 302, "no", {}, None)))


def test_get_does_not_retry_a_refused_redirect(no_waiting):
    opener, calls = opener_failing(99, made(download.DowngradeRefused("https://example.test/x", 301, "no", {}, None)))
    with pytest.raises(download.DowngradeRefused):
        download.get("https://example.test/x", opener=opener)
    assert len(calls) == 1


def paths(tmp_path):
    return {"root": tmp_path, "raw": tmp_path / "sources" / "raw", "snapshots": tmp_path / "sources" / "snapshots"}


def test_save_keeps_the_previous_version_as_a_snapshot(tmp_path):
    p, manifest = paths(tmp_path), {}
    dest = p["raw"] / "nas" / "ind01.json"
    assert download.save(manifest, "nas/ind01", dest, b"v1", "https://example.test/1", {"records": 1}, **p)
    first = manifest["nas/ind01"]
    assert first["file"] == "sources/raw/nas/ind01.json" and first["records"] == 1 and first["bytes"] == 2

    # unchanged: no new file, no snapshot, only checked_at
    assert not download.save(manifest, "nas/ind01", dest, b"v1", "https://example.test/1", **p)
    assert "checked_at" in manifest["nas/ind01"] and not p["snapshots"].exists()

    # changed: the old file is kept under the time it was fetched, and listed in history
    first["fetched_at"] = "2026-01-05T00:00:00+00:00"
    assert download.save(manifest, "nas/ind01", dest, b"v2", "https://example.test/1", **p)
    snap = p["snapshots"] / "2026-01-05T000000Z" / "nas" / "ind01.json"
    assert dest.read_bytes() == b"v2" and snap.read_bytes() == b"v1"
    assert manifest["nas/ind01"]["history"] == [
        {"sha256": first["sha256"], "fetched_at": "2026-01-05T00:00:00+00:00",
         "file": "sources/snapshots/2026-01-05T000000Z/nas/ind01.json"}]


def test_two_versions_fetched_on_the_same_day_keep_their_own_snapshots(tmp_path):
    p, manifest = paths(tmp_path), {}
    dest = p["raw"] / "nas" / "ind01.json"
    url = "https://example.test/1"
    download.save(manifest, "nas/ind01", dest, b"v1", url, **p)
    manifest["nas/ind01"]["fetched_at"] = "2026-01-05T09:30:00+00:00"
    download.save(manifest, "nas/ind01", dest, b"v2", url, **p)
    manifest["nas/ind01"]["fetched_at"] = "2026-01-05T17:45:10+05:30"  # another time zone: named in UTC
    download.save(manifest, "nas/ind01", dest, b"v3", url, **p)
    history = manifest["nas/ind01"]["history"]
    assert [h["file"] for h in history] == ["sources/snapshots/2026-01-05T093000Z/nas/ind01.json",
                                            "sources/snapshots/2026-01-05T121510Z/nas/ind01.json"]
    assert [(tmp_path / h["file"]).read_bytes() for h in history] == [b"v1", b"v2"] and dest.read_bytes() == b"v3"


def test_snapshot_folders_old_and_new_sort_in_time_order():
    # folders made before snapshot_name were named by the date only; they keep those names
    names = [download.snapshot_name("2026-01-06T00:00:01+00:00"), "2026-01-05",
             download.snapshot_name("2026-01-05T23:59:59+00:00"), "2026-01-04",
             download.snapshot_name("2026-01-05T08:00:00+00:00")]
    assert sorted(names) == ["2026-01-04", "2026-01-05", "2026-01-05T080000Z", "2026-01-05T235959Z",
                             "2026-01-06T000001Z"]


def test_check_records_refuses_a_much_shorter_download():
    manifest = {"nas/ind01": {"records": 1000}, "nas/ind02": {"empty": True}}
    download.check_records(manifest, "nas/ind01", 1000)
    download.check_records(manifest, "nas/ind01", 1200)  # more rows: a revision or a new period
    download.check_records(manifest, "nas/ind01", 950)  # 5% fewer: allowed
    with pytest.raises(download.RecordsDropped, match=r"nas/ind01: 949 records, 1,000 before"):
        download.check_records(manifest, "nas/ind01", 949)
    with pytest.raises(download.RecordsDropped):
        download.check_records(manifest, "nas/ind01", 900, max_drop=0.05)
    download.check_records(manifest, "nas/ind01", 900, max_drop=0.2)
    # nothing to compare with: a new key, an empty entry, or one saved without a count
    download.check_records(manifest, "nas/ind03", 1)
    download.check_records(manifest, "nas/ind02", 1)
    download.check_records({"k": {"sha256": "x"}}, "k", 1)


def test_manifest_round_trip_is_stable(tmp_path):
    path = tmp_path / "sources" / "manifest.json"
    assert download.load_manifest(path) == {}
    download.write_manifest(path, {"b": {"title": "₹ crore"}, "a": {}})
    text = path.read_text()
    assert text == '{\n "a": {},\n "b": {\n  "title": "₹ crore"\n }\n}\n'
    download.write_manifest(path, download.load_manifest(path))
    assert path.read_text() == text


def pages(*bodies):
    """Stub get: answers page n with bodies[n - 1]."""
    asked = []

    def get(url):
        asked.append(url)
        return json.dumps(bodies[int(url.rsplit("=", 1)[1]) - 1]).encode()

    return get, asked


def test_fetch_pages_reads_every_page_and_sorts(monkeypatch):
    get, asked = pages({"data": [{"v": 3}, {"v": 1}], "meta_data": {"totalRecords": 3, "totalPages": 2}},
                       {"data": [{"v": 2}], "meta_data": {"totalRecords": 3, "totalPages": 2}})
    monkeypatch.setattr(download, "get", get)
    rows = download.fetch_pages(lambda n: f"https://example.test/q?page={n}", "q")
    assert rows == [{"v": 1}, {"v": 2}, {"v": 3}]
    assert asked == ["https://example.test/q?page=1", "https://example.test/q?page=2"]


def test_fetch_pages_fails_when_rows_go_missing(monkeypatch):
    get, _ = pages({"data": [{"v": 1}], "meta_data": {"totalRecords": 2, "totalPages": 1}})
    monkeypatch.setattr(download, "get", get)
    with pytest.raises(RuntimeError, match="q: got 1 rows, API says 2"):
        download.fetch_pages(lambda n: f"https://example.test/q?page={n}", "q")


def test_fetch_pages_with_no_data(monkeypatch):
    get, _ = pages({"data": [], "meta_data": {}})
    monkeypatch.setattr(download, "get", get)
    assert download.fetch_pages(lambda n: f"https://example.test/q?page={n}", "q") == []


def test_legacy_tls_only_for_mospi_api():
    assert download.tls_for("https://api.mospi.gov.in/api/nas/getNASData?page=1") is download.LEGACY_TLS
    for url in ("https://www.indiabudget.gov.in/doc/bag1.pdf", "https://rbidocs.rbi.org.in/x.XLSX",
                "https://api.mospi.gov.in.evil.test/x"):
        assert download.tls_for(url) is download.TLS
    assert not download.TLS.options & getattr(download.ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)

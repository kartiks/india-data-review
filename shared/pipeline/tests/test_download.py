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


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test/x", code, "error", {}, None)


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


def test_is_type():
    assert download.is_type(b"%PDF-1.7 ...", "pdf")
    assert download.is_type(b"PK\x03\x04", "xlsx")
    assert download.is_type(b"\xd0\xcf\x11\xe0\xa1\xb1", "xls")
    assert not download.is_type(b"<html>not found</html>", "pdf")


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

    # changed: the old file is kept under the date it was fetched, and listed in history
    first["fetched_at"] = "2026-01-05T00:00:00+00:00"
    assert download.save(manifest, "nas/ind01", dest, b"v2", "https://example.test/1", **p)
    snap = p["snapshots"] / "2026-01-05" / "nas" / "ind01.json"
    assert dest.read_bytes() == b"v2" and snap.read_bytes() == b"v1"
    assert manifest["nas/ind01"]["history"] == [
        {"sha256": first["sha256"], "fetched_at": "2026-01-05T00:00:00+00:00", "file": "sources/snapshots/2026-01-05/nas/ind01.json"}]


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

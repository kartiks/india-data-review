"""fetch.py's downloaders one by one: MoSPI's paged API (fetch_query), the base-2024 CPI press releases
(fetch_cpi2024) and the HCES report tables (fetch_hces_tables). The network is replaced by stubs."""

import json
import urllib.parse

import pytest
from pipeline_common import download

from jobs_prices_pipeline import fetch

PDF = b"%PDF-1.7 a release"
XLSX = b"PK\x03\x04 a workbook"
PDF_URL = "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc2026212.pdf"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """fetch's paths under tmp_path, no pauses, and an empty manifest."""
    monkeypatch.setattr(fetch, "ROOT", tmp_path)
    monkeypatch.setattr(fetch, "RAW", tmp_path / "sources" / "raw")
    monkeypatch.setattr(fetch, "SNAPSHOTS", tmp_path / "sources" / "snapshots")
    monkeypatch.setattr(fetch, "MANIFEST", tmp_path / "sources" / "manifest.json")
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    monkeypatch.setattr(download.time, "sleep", lambda s: None)
    return tmp_path


def serve(monkeypatch, responses: dict[str, bytes]) -> list[str]:
    """fetch.get answers from responses (by URL); returns the URLs asked for, in order."""
    asked = []

    def get(url):
        asked.append(url)
        return responses[url]

    monkeypatch.setattr(fetch, "get", get)
    return asked


# ---- MoSPI's API, across pages ---------------------------------------------------------------------

def api_pages(monkeypatch, pages: list[list[dict]], total: int | None = None, total_pages: int | None = None):
    """download.get (which fetch_pages calls) answers page n of the query with pages[n - 1]."""
    asked = []

    def get(url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        asked.append(q)
        n = int(q["page"])
        meta = {"totalRecords": sum(map(len, pages)) if total is None else total,
                "totalPages": len(pages) if total_pages is None else total_pages}
        return json.dumps({"data": pages[n - 1] if n <= len(pages) else [], "meta_data": meta}).encode()

    monkeypatch.setattr(download, "get", get)
    return asked


def test_fetch_query_combines_every_page_in_a_stable_order(sandbox, monkeypatch):
    asked = api_pages(monkeypatch, [[{"v": 3}, {"v": 1}], [{"v": 2}]])
    result = fetch.fetch_query("plfs/getData", {"indicator_code": 1, "frequency_code": 1})
    assert [q["page"] for q in asked] == ["1", "2"]  # stops at totalPages
    assert all(q["limit"] == str(fetch.PAGE_LIMIT) and q["Format"] == "JSON" and q["indicator_code"] == "1" for q in asked)
    assert result["rows"] == [{"v": 1}, {"v": 2}, {"v": 3}]  # sorted, so an unchanged dataset gives the same file
    assert result["total_records"] == 3
    assert result["query"] == {"endpoint": "plfs/getData", "indicator_code": 1, "frequency_code": 1}
    # the URL recorded is the query itself, without the paging
    assert result["url"].startswith(f"{fetch.API}/plfs/getData?") and "page=" not in result["url"]


def test_fetch_query_stops_at_an_empty_page(sandbox, monkeypatch):
    asked = api_pages(monkeypatch, [[{"v": 1}]], total=1, total_pages=5)
    assert fetch.fetch_query("cpi/getCPIIndex", {"year": 2025})["rows"] == [{"v": 1}]
    assert [q["page"] for q in asked] == ["1", "2"]


def test_fetch_query_fails_when_rows_do_not_add_up_to_the_total(sandbox, monkeypatch):
    api_pages(monkeypatch, [[{"v": 1}], [{"v": 2}]], total=3)
    with pytest.raises(RuntimeError, match="got 2 rows, API says 3"):
        fetch.fetch_query("plfs/getData", {"indicator_code": 1})


def test_encode_writes_one_row_per_line_and_round_trips():
    result = {"source": "s", "query": {"endpoint": "x"}, "url": "u", "total_records": 2,
              "rows": [{"b": 1, "a": "क"}, {"a": 2}]}
    text = fetch.encode(result).decode()
    assert json.loads(text) == result
    assert '{"a": "क", "b": 1},\n' in text  # keys sorted, not escaped, one row per line


# ---- base-2024 CPI press releases ------------------------------------------------------------------

PAGE = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1&reg=3&lang=1"


def release_page(body: str = "<p>figures</p>", visitors: int = 1, pdfs: tuple[str, ...] = (PDF_URL,)) -> bytes:
    """A PIB page: the release between the site's header and its visitor counter (which changes on every visit)."""
    links = "".join(f"<a href='{u}'>PDF</a>" for u in pdfs)
    return (f"<html><nav>menu</nav><h2>PRESS RELEASE OF CONSUMER PRICE INDEX ON BASE 2024=100 FOR JANUARY, 2026</h2>"
            f"{body}{links}<div id=\"reel_pic\">Visitor counter: {visitors}</div></html>").encode()


def test_release_content_is_cut_from_the_title_to_the_visitor_counter():
    content = fetch.release_content(release_page().decode())
    assert content.startswith("<h2>PRESS RELEASE OF CONSUMER PRICE INDEX") and content.endswith("PDF</a>\n")
    assert "menu" not in content and "Visitor" not in content
    with pytest.raises(RuntimeError, match="title not found"):
        fetch.release_content("<html>Page not found</html>")
    with pytest.raises(RuntimeError, match="end of release"):
        fetch.release_content("<h2>CONSUMER PRICE INDEX ON BASE 2024</h2> cut short")


def test_fetch_cpi2024_saves_the_release_and_its_pdf(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "CPI2024_RELEASES", {"2026-01": PAGE})
    serve(monkeypatch, {PAGE: release_page(), PDF_URL: PDF})
    manifest = {}
    fetch.fetch_cpi2024(manifest, force=False)
    assert (fetch.RAW / "cpi2024" / "2026-01.html").read_text().startswith("<h2>PRESS RELEASE")
    assert (fetch.RAW / "cpi2024" / "2026-01.pdf").read_bytes() == PDF
    assert manifest["cpi2024/2026-01"]["url"] == PAGE
    assert manifest["cpi2024/2026-01/pdf"]["url"] == PDF_URL and manifest["cpi2024/2026-01/pdf"]["release_page"] == PAGE
    assert json.loads(fetch.MANIFEST.read_text()).keys() == manifest.keys()  # written as it goes


def test_fetch_cpi2024_skips_saved_releases_unless_forced(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "CPI2024_RELEASES", {"2026-01": PAGE})
    serve(monkeypatch, {PAGE: release_page(visitors=1), PDF_URL: PDF})
    manifest = {}
    fetch.fetch_cpi2024(manifest, force=False)
    sha = manifest["cpi2024/2026-01"]["sha256"]

    asked = serve(monkeypatch, {PAGE: release_page(visitors=2), PDF_URL: PDF})
    fetch.fetch_cpi2024(manifest, force=False)
    assert asked == []
    fetch.fetch_cpi2024(manifest, force=True)
    assert asked == [PAGE, PDF_URL]
    # only the visitor counter changed: the same file, so no snapshot
    assert manifest["cpi2024/2026-01"]["sha256"] == sha and "history" not in manifest["cpi2024/2026-01"]
    assert not fetch.SNAPSHOTS.exists()


def test_fetch_cpi2024_release_without_a_pdf(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "CPI2024_RELEASES", {"2026-06": PAGE})
    serve(monkeypatch, {PAGE: release_page(pdfs=())})
    manifest = {}
    fetch.fetch_cpi2024(manifest, force=False)
    assert manifest["cpi2024/2026-06/pdf"]["empty"] is True
    assert not (fetch.RAW / "cpi2024" / "2026-06.pdf").exists()


def test_fetch_cpi2024_refuses_two_pdfs(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "CPI2024_RELEASES", {"2026-01": PAGE})
    serve(monkeypatch, {PAGE: release_page(pdfs=(PDF_URL, PDF_URL.replace("doc2026212", "annex2026212")))})
    with pytest.raises(RuntimeError, match="more than one PDF"):
        fetch.fetch_cpi2024({}, force=False)


def test_fetch_cpi2024_refuses_a_pdf_link_that_is_not_a_pdf(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "CPI2024_RELEASES", {"2026-01": PAGE})
    serve(monkeypatch, {PAGE: release_page(), PDF_URL: b"<html>Error 404</html>"})
    manifest = {}
    with pytest.raises(RuntimeError, match="is not a PDF"):
        fetch.fetch_cpi2024(manifest, force=False)
    assert "cpi2024/2026-01/pdf" not in manifest
    assert not (fetch.RAW / "cpi2024" / "2026-01.pdf").exists()


def test_fetch_cpi2024_retries_a_pdf_that_failed_before(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "CPI2024_RELEASES", {"2026-01": PAGE})
    serve(monkeypatch, {PAGE: release_page(), PDF_URL: b"<html>Error 503</html>"})
    manifest = {}
    with pytest.raises(RuntimeError):
        fetch.fetch_cpi2024(manifest, force=False)

    serve(monkeypatch, {PAGE: release_page(), PDF_URL: PDF})
    fetch.fetch_cpi2024(fetch.load_manifest(), force=False)
    assert (fetch.RAW / "cpi2024" / "2026-01.pdf").exists()


# ---- HCES report tables ----------------------------------------------------------------------------

TABLE_URL = "https://mospi.gov.in/sites/default/files/publication_reports/HCES-23-24/TableA2.xlsx"


def test_fetch_hces_tables_saves_the_excel_file(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "HCES_REPORT_TABLES", {"2023-24/TableA2": TABLE_URL})
    serve(monkeypatch, {TABLE_URL: XLSX})
    manifest = {}
    fetch.fetch_hces_tables(manifest, force=False)
    assert (fetch.RAW / "hces_report" / "2023-24" / "TableA2.xlsx").read_bytes() == XLSX
    assert manifest["hces_report/2023-24/TableA2"]["url"] == TABLE_URL

    asked = serve(monkeypatch, {TABLE_URL: XLSX})
    fetch.fetch_hces_tables(manifest, force=False)
    assert asked == []  # a fixed document: not downloaded again
    fetch.fetch_hces_tables(manifest, force=True)
    assert asked == [TABLE_URL]


def test_fetch_hces_tables_refuses_a_page_that_is_not_excel(sandbox, monkeypatch):
    monkeypatch.setattr(fetch, "HCES_REPORT_TABLES", {"2023-24/TableA2": TABLE_URL})
    serve(monkeypatch, {TABLE_URL: b"<!DOCTYPE html><html>moved</html>"})
    manifest = {}
    with pytest.raises(RuntimeError, match="not an Excel file"):
        fetch.fetch_hces_tables(manifest, force=False)
    assert manifest == {} and not fetch.RAW.exists()

"""Where the documents are (sources.py), how downloads are vetted and saved (fetch.py), and the RBI Handbook tables
(reference.py). Offline: downloads are stubbed and every file is written under tmp_path."""

import json
import urllib.error

import openpyxl
import pytest

from budget_pipeline import fetch, reference
from budget_pipeline.sources import LATEST_BUDGET, candidate_urls

# ----- sources.candidate_urls -----------------------------------------------------------------------------------


def names(start, doc):
    return [u.rsplit("/", 2)[-2] + "/" + u.rsplit("/", 1)[-1] for u in candidate_urls(start, doc)]


def test_formats_offered_change_with_the_site():
    assert names(2005, "summary") == ["bag/bag1.pdf", "bag/bag1.xls", "bag/bag1.htm"]
    assert names(2012, "summary") == ["bag/bag1.pdf", "bag/bag1.xls", "bag/bag1.xlsx"]
    assert names(2022, "summary") == ["Budget_at_Glance/bag1.pdf", "Budget_at_Glance/bag1.xlsx",
                                      "Budget_at_Glance/bag1.xls"]


def test_receipts_table_number_changed_in_2017():
    assert names(2016, "receipts")[0] == "bag/bag2.pdf"
    assert names(2017, "receipts")[0] == "bag/bag5.pdf"


def test_ministries_statement_changed_in_2017():
    assert {n.split(".")[0] for n in names(2016, "ministries")} == {"eb/stat02"}
    # Statement 3A first, then 3: the first one found is kept.
    assert names(2020, "ministries")[:2] == ["eb/stat3a.pdf", "eb/stat3a.xlsx"]
    assert {n.split(".")[0] for n in names(2020, "ministries")} == {"eb/stat3a", "eb/stat3"}


def test_scheme_tables_only_from_2017_and_receipt_budget_only_2002_to_2009():
    assert candidate_urls(2016, "css") == candidate_urls(2016, "central_sector") == []
    assert names(2017, "css")[0] == "eb/stat4a.pdf"
    assert names(2017, "central_sector")[0] == "eb/stat4b.pdf"
    assert candidate_urls(2001, "receipt_budget") == candidate_urls(2010, "receipt_budget") == []
    assert names(2002, "receipt_budget")[0] == "rec/annex7.pdf"


def test_2016_17_headline_table_is_bag11_with_an_excel_copy_named_bag1():
    assert names(2016, "summary") == ["bag/bag11.pdf", "bag/bag11.xls", "bag/bag11.xlsx", "bag/bag1.xls"]


def test_latest_budget_is_at_the_site_root():
    assert candidate_urls(LATEST_BUDGET, "summary")[0] == "https://www.indiabudget.gov.in/doc/Budget_at_Glance/bag1.pdf"
    assert candidate_urls(LATEST_BUDGET - 1, "summary")[0].startswith(
        f"https://www.indiabudget.gov.in/budget{LATEST_BUDGET - 1}-{str(LATEST_BUDGET)[-2:]}/doc/")


def test_unknown_document_type_is_an_error():
    with pytest.raises(ValueError):
        candidate_urls(2020, "statement_99")


# ----- fetch: what counts as a download of the table ------------------------------------------------------------


def html(title: str) -> bytes:
    """A web page holding a table with this title, long enough to pass the size test."""
    return (f"<html><body><table><tr><td>{title}</td></tr>"
            + "<tr><td>Revenue Receipts</td><td>1</td></tr>" * 20 + "</table></body></html>").encode()


@pytest.mark.parametrize("ext, content, ok", [
    ("pdf", b"%PDF-1.4" + b" " * 600, True),
    ("pdf", b"%PDF-1.4", False),  # too small to be a table
    ("pdf", html("Budget at a Glance"), False),  # a web page saved under a .pdf address
    ("xlsx", b"PK\x03\x04" + b" " * 600, True),
    ("xls", b"PK\x03\x04" + b" " * 600, False),  # an .xlsx file under an .xls address
    ("htm", html("Budget at a Glance"), True),
    ("htm", html("404 - File or directory not found."), False),  # the site's not-found page
    ("htm", b"%PDF-1.4" + b" " * 600, False),
])
def test_looks_valid(ext, content, ok):
    assert fetch.looks_valid(ext, content) is ok


def test_has_title_reads_the_file():
    assert fetch.has_title("summary", "htm", html("BUDGET AT A GLANCE"))
    assert not fetch.has_title("summary", "htm", html("Statement of Receipts"))
    assert not fetch.has_title("summary", "pdf", b"%PDF-1.4 not really a pdf" + b" " * 600)  # unreadable: refused


# ----- fetch.main with the downloads stubbed ---------------------------------------------------------------------


@pytest.fixture
def site(monkeypatch, tmp_path):
    """fetch.main for Budget 2005-06 only, writing under tmp_path; returns the {url: answer} the stub serves (an
    exception is raised) and the list of addresses asked for."""
    answers: dict = {}
    asked: list[str] = []

    def get(url):
        asked.append(url)
        answer = answers.get(url, urllib.error.HTTPError(url, 404, "Not Found", {}, None))
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(fetch, "get", get)
    monkeypatch.setattr(fetch, "POLITE_PAUSE_S", 0)
    monkeypatch.setattr(fetch, "BUDGETS", [2005])
    monkeypatch.setattr(fetch, "ROOT", tmp_path)
    monkeypatch.setattr(fetch, "RAW", tmp_path / "sources" / "raw")
    monkeypatch.setattr(fetch, "MANIFEST", tmp_path / "sources" / "manifest.json")
    (tmp_path / "sources").mkdir()
    return answers, asked


def test_fetch_saves_only_the_right_table(site, tmp_path):
    answers, _ = site
    base = "https://www.indiabudget.gov.in/budget_archive/ub2005-06/bag/bag1"
    answers[f"{base}.pdf"] = urllib.error.URLError("connection reset")  # after get()'s retries: carry on
    answers[f"{base}.xls"] = html("Budget at a Glance")  # a web page under an .xls address: skipped
    answers[f"{base}.htm"] = html("Budget at a Glance")
    fetch.main(docs=["summary"])
    manifest = json.loads((tmp_path / "sources" / "manifest.json").read_text())
    files = manifest["2005-06"]["summary"]["files"]
    assert list(files) == ["htm"]
    assert files["htm"]["url"] == f"{base}.htm"
    assert files["htm"]["file"] == "sources/raw/2005-06/summary.htm"
    assert files["htm"]["bytes"] == len(answers[f"{base}.htm"])
    assert (tmp_path / files["htm"]["file"]).read_bytes() == answers[f"{base}.htm"]
    assert sorted(p.name for p in (tmp_path / "sources" / "raw" / "2005-06").iterdir()) == ["summary.htm"]


def test_fetch_refuses_a_file_without_the_table_title(site, tmp_path):
    answers, _ = site
    answers["https://www.indiabudget.gov.in/budget_archive/ub2005-06/bag/bag1.htm"] = html("Receipts")
    fetch.main(docs=["summary"])
    manifest = json.loads((tmp_path / "sources" / "manifest.json").read_text())
    assert "summary" not in manifest["2005-06"]
    assert not (tmp_path / "sources" / "raw").exists()


def test_fetch_keeps_files_already_saved_unless_forced(site, tmp_path):
    answers, asked = site
    url = "https://www.indiabudget.gov.in/budget_archive/ub2005-06/bag/bag1.htm"
    answers[url] = html("Budget at a Glance")
    fetch.main(docs=["summary"])
    asked.clear()
    fetch.main(docs=["summary"])
    assert url not in asked
    answers[url] = html("Budget at a Glance, revised")
    fetch.main(force=True, docs=["summary"])
    assert url in asked
    assert (tmp_path / "sources" / "raw" / "2005-06" / "summary.htm").read_bytes() == answers[url]


def test_fetch_keeps_the_first_statement_found(site, tmp_path, monkeypatch):
    # From 2017-18 the ministries table is Statement 3A or Statement 3, tried in that order.
    answers, _ = site
    monkeypatch.setattr(fetch, "BUDGETS", [2020])
    base = "https://www.indiabudget.gov.in/budget2020-21/doc/eb"
    monkeypatch.setattr(fetch, "candidate_urls", lambda start, doc: [f"{base}/stat3a.htm", f"{base}/stat3.htm"])
    answers[f"{base}/stat3a.htm"] = html("Ministry-wise statement 3A")
    answers[f"{base}/stat3.htm"] = html("Ministry-wise statement 3")
    fetch.main(docs=["ministries"])
    manifest = json.loads((tmp_path / "sources" / "manifest.json").read_text())
    assert manifest["2020-21"]["ministries"]["files"]["htm"]["url"] == f"{base}/stat3a.htm"


def test_refresh_keeps_the_same_statement_as_fetch(site, tmp_path, monkeypatch):
    answers, _ = site
    monkeypatch.setattr(fetch, "BUDGETS", [2020])
    base = "https://www.indiabudget.gov.in/budget2020-21/doc/eb"
    monkeypatch.setattr(fetch, "candidate_urls", lambda start, doc: [f"{base}/stat3a.htm", f"{base}/stat3.htm"])
    answers[f"{base}/stat3a.htm"] = html("Ministry-wise statement 3A")
    answers[f"{base}/stat3.htm"] = html("Ministry-wise statement 3")
    fetch.main(force=True, docs=["ministries"])
    manifest = json.loads((tmp_path / "sources" / "manifest.json").read_text())
    assert manifest["2020-21"]["ministries"]["files"]["htm"]["url"] == f"{base}/stat3a.htm"
    assert (tmp_path / "sources" / "raw" / "2020-21" / "ministries.htm").read_bytes() == html("Ministry-wise statement 3A")


def test_refresh_keeps_a_mix_of_statements_by_format(site, tmp_path, monkeypatch):
    # As in the committed manifest for 2023-24: Statement 3A only as PDF, Statement 3 only as Excel.
    answers, _ = site
    monkeypatch.setattr(fetch, "BUDGETS", [2023])
    base = "https://www.indiabudget.gov.in/budget2023-24/doc/eb"
    monkeypatch.setattr(fetch, "candidate_urls", lambda start, doc: [
        f"{base}/stat3a.pdf", f"{base}/stat3a.htm", f"{base}/stat3.pdf", f"{base}/stat3.htm"])
    answers[f"{base}/stat3a.pdf"] = b"statement 3A"  # stat3a.htm is not there (404)
    answers[f"{base}/stat3.pdf"] = answers[f"{base}/stat3.htm"] = b"statement 3"
    monkeypatch.setattr(fetch, "looks_valid", lambda ext, content: True)
    monkeypatch.setattr(fetch, "has_title", lambda doc, ext, content: True)
    for force in (False, True):
        fetch.main(force=force, docs=["ministries"])
        files = json.loads((tmp_path / "sources" / "manifest.json").read_text())["2023-24"]["ministries"]["files"]
        assert {ext: f["url"].rsplit("/", 1)[-1] for ext, f in files.items()} == {"pdf": "stat3a.pdf", "htm": "stat3.htm"}


# ----- reference: the RBI Handbook tables ---------------------------------------------------------------------


def rbi_table(path, rows):
    """An RBI Handbook table as the RBI lays it out: an empty first column, the year in the second."""
    book = openpyxl.Workbook()
    for r in rows:
        book.active.append(["", *r])
    book.save(path)


TABLE = [
    ["TABLE 86 : KEY DEFICIT INDICATORS OF THE CENTRAL GOVERNMENT"],
    ["(₹ Crore)"],
    ["Year", "Gross Fiscal Deficit", "Net Fiscal Deficit", "Revenue Deficit"],
    ["1", "2", "3", "4"],
    ["2023-24", "1654643", "1", "761434"],
    ["2024-25", "1574431", "1", "-"],  # not available: left out
    ["2025-26", "1558492", "1", "-5"],  # a surplus
    ["2026-27", "1695768", "1", "500"],
    ["Notes : 1. Data for 2025-26 are Revised Estimates and data for 2026-27 are Budget Estimates."],
]


@pytest.fixture
def one_table(monkeypatch, tmp_path):
    monkeypatch.setattr(reference, "REF_DIR", tmp_path)
    monkeypatch.setattr(reference, "RBI_TABLES", {"t86": {
        "title": "Table 86", "url": "https://rbidocs.rbi.org.in/t86.XLSX",
        "columns": {"fiscal_deficit": 2, "revenue_deficit": 4}}})
    return tmp_path / "t86.xlsx"


def test_load_rbi_reads_columns_by_their_printed_number(one_table):
    rbi_table(one_table, TABLE)
    out = reference.load_rbi()
    assert out == {
        ("2023-24", "fiscal_deficit", "actual"): {"value": 1654643, "table": "Table 86"},
        ("2023-24", "revenue_deficit", "actual"): {"value": 761434, "table": "Table 86"},
        ("2024-25", "fiscal_deficit", "actual"): {"value": 1574431, "table": "Table 86"},
        ("2025-26", "fiscal_deficit", "re"): {"value": 1558492, "table": "Table 86"},
        ("2025-26", "revenue_deficit", "re"): {"value": -5, "table": "Table 86"},
        ("2026-27", "fiscal_deficit", "be"): {"value": 1695768, "table": "Table 86"},
        ("2026-27", "revenue_deficit", "be"): {"value": 500, "table": "Table 86"},
    }


def test_load_rbi_finds_columns_after_a_spacer(one_table):
    # A blank spacer column before column 4: values are found by the printed column number, not the position.
    rows = [r if len(r) < 4 else [*r[:3], "", *r[3:]] for r in TABLE]
    rbi_table(one_table, rows)
    assert reference.load_rbi()[("2023-24", "revenue_deficit", "actual")]["value"] == 761434


def test_load_rbi_refuses_a_malformed_year(one_table):
    rbi_table(one_table, [*TABLE[:4], ["2023-25", "1", "1", "1"]])
    with pytest.raises(ValueError, match="not a fiscal year"):
        reference.load_rbi()


def test_load_rbi_refuses_a_table_without_column_numbers(one_table):
    rbi_table(one_table, [row for row in TABLE if row[:1] != ["1"]])
    with pytest.raises(ValueError, match=r"t86\.xlsx: no row of column numbers"):
        reference.load_rbi()


def test_load_rbi_refuses_a_table_missing_a_numbered_column(one_table):
    rbi_table(one_table, [["1", "2", "3"] if row[:1] == ["1"] else row for row in TABLE])
    with pytest.raises(ValueError, match=r"t86\.xlsx: column number\(s\) \[4\]"):
        reference.load_rbi()


def test_load_rbi_on_the_committed_tables():
    out = reference.load_rbi()
    # Figures also published in Budget 2026-27 (and checked against our data by checks.check_reference).
    assert out[("2024-25", "fiscal_deficit", "actual")]["value"] == 1574431
    assert out[("2026-27", "fiscal_deficit", "be")]["value"] == 1695768
    assert {k[2] for k in out} == {"actual", "re", "be"}
    assert {f for _, f, _ in out} == {f for spec in reference.RBI_TABLES.values() for f in spec["columns"]}


def test_reference_fetch_refuses_an_error_page(monkeypatch, tmp_path):
    monkeypatch.setattr(reference, "get", lambda url: html("Page not found"))
    monkeypatch.setattr(reference, "REF_DIR", tmp_path / "rbi")
    monkeypatch.setattr(reference, "REF_MANIFEST", tmp_path / "manifest.json")
    with pytest.raises(RuntimeError, match="is not an Excel file"):
        reference.fetch()
    assert list((tmp_path / "rbi").iterdir()) == []
    assert not (tmp_path / "manifest.json").exists()


def test_reference_fetch_saves_each_table_and_its_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(reference, "get", lambda url: b"PK\x03\x04 " + url.encode())
    monkeypatch.setattr(reference, "ROOT", tmp_path)
    monkeypatch.setattr(reference, "REF_DIR", tmp_path / "rbi")
    monkeypatch.setattr(reference, "REF_MANIFEST", tmp_path / "manifest.json")
    reference.fetch()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert set(manifest) == set(reference.RBI_TABLES)
    for name, spec in reference.RBI_TABLES.items():
        assert manifest[name]["url"] == spec["url"]
        assert manifest[name]["file"] == f"rbi/{name}.xlsx"
        assert (tmp_path / "rbi" / f"{name}.xlsx").read_bytes().endswith(spec["url"].encode())

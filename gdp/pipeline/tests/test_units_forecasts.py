"""forecasts.verify_quotes on hand-made records and documents: each quote is looked for in the document saved under
a temporary sources/ folder (read through the manifest, as in a real run)."""

import json

import pytest

from gdp_pipeline import forecasts

URL = "https://survey.example/chapter1.html"
URL_2 = "https://survey.example/statistical-appendix.html"
QUOTE = "real GDP growth in FY27 in the range of 6.8 to 7.2 per cent."


@pytest.fixture
def documents(tmp_path, monkeypatch):
    """Saves {url: html} as downloaded documents and returns a function that runs verify_quotes on the records."""
    monkeypatch.setattr(forecasts, "ROOT", tmp_path)
    monkeypatch.setattr(forecasts, "SOURCES", {"economic_survey": "Economic Survey"})

    def run(docs: dict, *records):
        monkeypatch.setattr(forecasts, "_cache", {})  # texts are cached by address for a whole run
        manifest = {}
        (tmp_path / "sources").mkdir(exist_ok=True)
        for url, html in docs.items():
            key = forecasts.doc_key(url)
            path = tmp_path / "sources" / "raw" / f"{key}.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html)
            manifest[key] = {"url": url, "file": str(path.relative_to(tmp_path)), "sha256": "x"}
        (tmp_path / "sources" / "manifest.json").write_text(json.dumps(manifest))
        monkeypatch.setattr(forecasts, "load", lambda name: list(records))
        return forecasts.verify_quotes({})
    return run


def record(**kw):
    return {"fiscal_year": "2026-27", "survey": "Economic Survey 2025-26", "low": 6.8, "high": 7.2, "quote": QUOTE,
            "url": URL, **kw}


LABEL = "Economic Survey, Economic Survey 2025-26 → 2026-27"


def test_a_quote_found_in_its_web_page_passes_whatever_the_markup_and_spacing(documents):
    html = ("<html><head><style>p { color: red }</style><script>var x = 'real GDP';</script></head><body>"
            "<p>The Survey projects <b>real GDP growth</b> in FY27\n in the range of 6.8 to\n7.2 per&nbsp;cent.</p>")
    checked, failures, notes = documents({URL: html}, record())
    assert (checked, failures) == (2, [])  # the quote, then the record against its quote
    assert notes[-1].startswith("1 quoted sentences found in their official documents")


def test_a_quote_not_in_its_document_fails_and_names_the_page(documents):
    checked, failures, _ = documents({URL: "<p>real GDP growth in FY27 of 7 per cent.</p>"}, record(pdf_page=31))
    assert checked == 2
    assert failures == [f"{LABEL}: quote not found on page 31 of {URL}: “{QUOTE}”"]


def test_a_document_not_downloaded_fails(documents):
    checked, failures, _ = documents({}, record())
    assert checked == 2 and failures == [f"{LABEL}: document not downloaded ({URL})"]


def test_the_text_layer_version_of_a_quote_is_accepted_in_its_place(documents):
    layer = "real GDP growth in FY27 in the range of 6.8 to 7.2 percent."  # the PDF's text layer drops a space
    checked, failures, _ = documents({URL: f"<p>{layer}</p>"}, record(quote_text_layer=layer))
    assert (checked, failures) == (2, [])  # the text-layer quote is not counted as a quote of its own


def test_a_second_quote_is_looked_for_in_its_own_document(documents):
    band = "a band of 6.5 to 7.5 per cent for 2026-27"
    r = record(band_low=6.5, band_high=7.5, quote_2=band, quote_2_url=URL_2)
    checked, failures, _ = documents({URL: f"<p>{QUOTE}</p>", URL_2: f"<p>{band}</p>"}, r)
    assert (checked, failures) == (3, [])
    # in the first document only: not found where the record says it is
    _, failures, _ = documents({URL: f"<p>{QUOTE} {band}</p>", URL_2: "<p>tables</p>"}, r)
    assert failures == [f"{LABEL}: quote_2 not found on the page of {URL_2}: “{band}”"]


def test_a_quote_broken_up_by_other_text_is_found_and_noted(documents):
    html = "<p>real GDP growth in FY27 [Box 1.2: Monsoon] in the range of 6.8 to 7.2 per cent.</p>"
    _, failures, notes = documents({URL: html}, record())
    assert failures == []
    assert notes[0] == f"{LABEL}: quote found with other text (a margin box or second column) printed between its words"


def test_figures_the_quote_does_not_bear_out_fail_even_when_the_quote_is_found(documents):
    _, failures, _ = documents({URL: f"<p>{QUOTE}</p>"}, record(high=7.5))
    assert failures == [f"{LABEL}: recorded [6.8, 7.5] not all in the quote “{QUOTE}”"]


def test_the_rbi_s_flags_are_checked_once_for_all_its_records(documents, monkeypatch):
    monkeypatch.setattr(forecasts, "SOURCES", {"rbi": "RBI"})
    quote = "real GDP growth for 2026-27 is projected at 7.1 per cent"

    def rbi(date, **flags):
        return {"fiscal_year": "2026-27", "statement": f"Policy {date}", "date": date, "value": 7.1, "quote": quote,
                "url": URL, **flags}
    good = [rbi("2026-04-08", is_first=True, is_first_april_policy=True), rbi("2026-06-05", is_last=True)]
    checked, failures, _ = documents({URL: f"<p>{quote}</p>"}, *good)
    assert (checked, failures) == (5, [])  # 2 × (quote, record) + the flags
    bad = [rbi("2026-04-08", is_first_april_policy=True), rbi("2026-06-05", is_first=True, is_last=True)]
    _, failures, _ = documents({URL: f"<p>{quote}</p>"}, *bad)
    assert failures == ["2026-27: is_first is set on ['Policy 2026-06-05 (2026-06-05)'], "
                        "expected ['Policy 2026-04-08 (2026-04-08)']"]

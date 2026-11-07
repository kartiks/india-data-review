"""The base-2024 CPI release reader (cpi2024.py), on small hand-made pages shaped like MoSPI's releases on PIB: each
table on its own, the whole release, the series across releases, and what the CSV and the site get. (The summary
table read provisional-first and the CFPI series are also in test_pipeline.py.)"""

import pytest

from jobs_prices_pipeline import cpi2024


def html_table(*rows: list[str]) -> str:
    return "<table>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"


def tables(html: str) -> list[list[list[str]]]:
    p = cpi2024.Tables()
    p.feed(html)
    return p.tables


IDX = ["Rural", "Urban", "Comb.", "Rural", "Urban", "Comb."]


# ---- the HTML tables -------------------------------------------------------------------------------

def test_tables_reads_cells_and_drops_trailing_empty_ones():
    html = ("<p>not a table</p><table><tr><th> Division\n code </th><td>A&amp;B</td></tr>"
            "<tr><td><b>1</b>.5</td><td></td><td> </td></tr></table>")
    assert tables(html) == [[["Division code", "A&B"], ["1.5"]]]


def test_tables_keeps_nested_tables_apart():
    html = "<table><tr><td>outer</td><td><table><tr><td>inner</td></tr></table></td></tr></table>"
    inner, outer = tables(html)
    assert inner == [["inner"]]
    assert outer[0][0] == "outer"


def test_text_of_drops_markup_scripts_and_styles():
    assert cpi2024.text_of("<style>p{}</style><p>Inflation&nbsp;is <b>3.93</b>%</p><script>var x=1;</script>") == \
        "Inflation is 3.93 %"


@pytest.mark.parametrize("cell, value", [("104.59", 104.59), ("106.0*", 106.0), ("-", None), ("", None),
                                         ("109.`39", None), ("1,234.5", 1234.5)])
def test_num(cell, value):
    assert cpi2024.num(cell) == value


def test_six_needs_a_label_and_three_numbers():
    assert cpi2024.six(["01", "Food", "1", "2", "3", "4", "5", "6"]) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert cpi2024.six(["Chandigarh", "-", "104.98", "104.98", "-", "3.10", "3.10"]) == [None, 104.98, 104.98, None, 3.10, 3.10]
    assert cpi2024.six(["1", "2", "3", "4", "5", "6"]) is None  # no label
    assert cpi2024.six(["Header", "Rural", "Urban", "Comb.", "Rural", "Urban", "Comb."]) is None  # no numbers


def test_divisions_with_the_all_india_row():
    t = tables(html_table(["Division code", "Division name", "Index", "Inflation"], IDX,
                          ["(i)", "(ii)", "(iii)", "(iv)", "(v)", "(vi)", "(vii)", "(viii)"],
                          ["01", "Food and beverages", "111.86", "111.61", "111.77", "7.71", "6.75", "7.36"],
                          ["All India", "110.11", "108.71", "109.49", "6.08", "4.88", "5.54"]))[0]
    assert cpi2024.divisions(t) == [
        {"code": "01", "name": "Food and beverages", "values": [111.86, 111.61, 111.77, 7.71, 6.75, 7.36]},
        {"code": "00", "name": "All India", "values": [110.11, 108.71, 109.49, 6.08, 4.88, 5.54]}]


@pytest.mark.xfail(strict=True, reason=(
    "cpi2024.divisions looks for 'All India' in the first cell, but every saved release prints the All-India row of "
    "Annexure I with an empty first cell (&nbsp;) and the name in the second, so the row (code '00') is never read "
    "and check_headline_agrees silently compares one source fewer"))
def test_divisions_reads_the_all_india_row_as_the_releases_print_it():
    t = tables(html_table(["Division code", "Division name", "Index", "Inflation"],
                          ["01", "Food and beverages", "111.86", "111.61", "111.77", "7.71", "6.75", "7.36"],
                          ["&nbsp;", "All India", "110.11", "108.71", "109.49", "6.08", "4.88", "5.54"]))[0]
    assert [d["code"] for d in cpi2024.divisions(t)] == ["01", "00"]


def test_groups_with_or_without_a_serial_number_column():
    t = tables(html_table(["Group code", "Group name", "Index", "Inflation"],
                          ["01.1", "Food", "1", "2", "3", "4", "5", "6"],
                          ["7", "13.9", "Other services", "1", "2", "3", "4", "5", "6"],
                          ["Note: Comb.: Combined"]))[0]
    assert [(g["code"], g["name"]) for g in cpi2024.groups(t)] == [("01.1", "Food"), ("13.9", "Other services")]


def test_states_drop_serial_numbers_and_footnote_marks():
    t = tables(html_table(["S.No.", "State", "CPI", "Inflation"], IDX,
                          ["1.", "Andhra Pradesh", "108.82", "108.65", "108.75", "6.63", "5.74", "6.29"],
                          ["", "Chandigarh*", "-", "104.98", "104.98", "-", "3.10", "3.10"]))[0]
    out = cpi2024.states(t)
    assert [s["name"] for s in out] == ["Andhra Pradesh", "Chandigarh"]
    assert out[1]["values"][:3] == [None, 104.98, 104.98] and out[1]["printed"][0] == "-"


def test_all_india_series_pads_index_only_rows_and_marks_the_provisional_month():
    t = tables(html_table(["Month", "Index", "Inflation (%)"], ["Rural", "Urban", "Combined"] * 2,
                          ["Jan-25", "101.81", "101.49", "101.67"],
                          ["Sep-26*", "110.11", "108.71", "109.49", "6.08", "4.88", "5.54"],
                          ["*Index and Inflation for the month of September, 2026 are provisional."]))[0]
    series, combined = cpi2024.all_india_series(t)
    assert series == [
        {"month": "2025-01", "values": [101.81, 101.49, 101.67, None, None, None], "provisional": False},
        {"month": "2026-09", "values": [110.11, 108.71, 109.49, 6.08, 4.88, 5.54], "provisional": True}]
    assert combined == []


def test_all_india_series_of_the_first_release_is_combined_cpi_and_cfpi():
    t = tables(html_table(["Month", "CPI", "CFPI"], ["Dec-25", "104.10", "104.09"], ["Jan-26", "104.46", "104.04"]))[0]
    series, combined = cpi2024.all_india_series(t)
    assert series == []
    assert combined == [{"month": "2025-12", "cpi": 104.10, "cfpi": 104.09}, {"month": "2026-01", "cpi": 104.46, "cfpi": 104.04}]


def test_linking_factors_and_weights():
    link = tables(html_table(["S. no.", "CPI General", "Linking factor"], ["1.", "Rural", "0.5222"], ["2.", "Urban", "0.5320"],
                             ["3.", "Combined", "0.5267"], ["", "Note", "-"]))[0]
    assert cpi2024.linking(link) == {"Rural": 0.5222, "Urban": 0.5320, "Combined": 0.5267}
    w = tables(html_table(["Divisions", "Rural", "Urban", "Combined"], ["CPI 2012", "CPI 2024"] * 3,
                          ["Food and beverages", "50.922", "41.983", "32.811", "30.251", "42.617", "36.753"]))[0]
    assert cpi2024.weights(w) == [{"division": "Food and beverages", "rural_2012": 50.922, "rural_2024": 41.983,
                                   "urban_2012": 32.811, "urban_2024": 30.251, "combined_2012": 42.617,
                                   "combined_2024": 36.753}]


def test_summary_printed_final_month_first():
    t = tables(html_table(["", "August, 2026 (Final)", "September, 2026 (Provisional)"], [],
                          ["", "", "Rural", "Urban", "Combined", "Rural", "Urban", "Combined"],
                          ["Inflation (%)", "CPI (General)", "5.24", "4.31", "4.83", "6.08", "4.88", "5.54"],
                          ["CFPI", "6.17", "5.64", "5.97", "8.06", "7.18", "7.74"],
                          ["Index", "CPI (General)", "109.28", "108.07", "108.74", "110.11", "108.71", "109.49"],
                          ["CFPI", "110.74", "110.72", "110.73", "112.21", "112.10", "112.17"]))[0]
    out, problems = cpi2024.summary(t, "2026-09")
    assert problems == []
    assert out["current"] == {"general_inflation": [6.08, 4.88, 5.54], "cfpi_inflation": [8.06, 7.18, 7.74],
                              "general_index": [110.11, 108.71, 109.49], "cfpi_index": [112.21, 112.10, 112.17]}
    assert out["previous"]["general_inflation"] == [5.24, 4.31, 4.83]


def test_summary_of_one_month_only():
    t = tables(html_table(["", "January, 2026 (Provisional) at Base year 2024=100"], ["Rural", "Urban", "Combined"],
                          ["Inflation (%)", "CPI (General)", "2.73", "2.77", "2.75"], ["CFPI", "1.96", "2.44", "2.13"]))[0]
    out, _ = cpi2024.summary(t, "2026-01")
    assert out == {"current": {"general_inflation": [2.73, 2.77, 2.75], "cfpi_inflation": [1.96, 2.44, 2.13]}}


def test_headline_figures():
    text = ("Year-on-year inflation rate based on All India Consumer Price Index (CPI) with base year 2024 for the month "
            "of January 2026 over January, 2025 is 2.75 % (Provisional). Corresponding inflation rates for rural and "
            "urban are 2.73% and 2.77%, respectively.")
    h = cpi2024.headline_figures(text)
    assert (h["month_name"], h["year"], h["combined"], h["rural"], h["urban"]) == ("January", "2026", 2.75, 2.73, 2.77)
    assert cpi2024.headline_figures("no figures here") == {}


# ---- a whole release -------------------------------------------------------------------------------

def release_html(month_label="Feb-26", divisions=True, states=True, extra="") -> str:
    """A release whose All-India row (first cell 'All India') and series (from Jan-25) the reader recognises."""
    parts = [
        "<h2>PRESS RELEASE OF CONSUMER PRICE INDEX ON BASE 2024=100 FOR FEBRUARY, 2026</h2>",
        "<p>... for the month of February, 2026 over February, 2025 is 3.00% (Provisional). Corresponding inflation "
        "rates for rural and urban are 2.00% and 4.00%, respectively.</p>",
        html_table(["", "February, 2026 (Provisional)", "January, 2026 (Final)"],
                   ["Inflation (%)", "CPI (General)", "2.00", "4.00", "3.00", "1.00", "2.00", "1.50"],
                   ["CFPI", "5.00", "6.00", "5.50", "4.00", "5.00", "4.50"]),
        html_table(["Division code", "Division name", "Index", "Inflation"],
                   ["01", "Food and beverages", "102.00", "104.00", "103.00", "2.00", "4.00", "3.00"],
                   ["All India", "102.00", "104.00", "103.00", "2.00", "4.00", "3.00"]) if divisions else "",
        html_table(["Group code", "Group name", "Index", "Inflation"],
                   ["01.1", "Food", "102.00", "104.00", "103.00", "2.00", "4.00", "3.00"]),
        html_table(["State", "CPI", "Inflation"],
                   ["Andhra Pradesh", "102.00", "104.00", "103.00", "2.00", "4.00", "3.00"],
                   ["Uttar Pradesh", "102.00", "104.00", "103.00", "2.00", "4.00", "3.00"]) if states else "",
        html_table(["Month", "Index", "Inflation (%)"], ["Jan-25", "99.00", "99.00", "99.00"],
                   ["Feb-25", "100.00", "100.00", "100.00"],
                   [f"{month_label}*", "102.00", "104.00", "103.00", "2.00", "4.00", "3.00"]),
        extra,
    ]
    return "".join(parts)


def test_parse_a_whole_release():
    r = cpi2024.parse(release_html(), "2026-02")
    assert r["problems"] == []
    assert r["headline"]["combined"] == 3.0 and r["headline"]["rural"] == 2.0
    assert r["summary"]["current"]["general_inflation"] == [2.0, 4.0, 3.0]
    assert r["summary"]["previous"] == {"general_inflation": [1.0, 2.0, 1.5], "cfpi_inflation": [4.0, 5.0, 4.5]}
    assert [d["code"] for d in r["divisions"]] == ["01", "00"]
    assert [g["code"] for g in r["groups"]] == ["01.1"]
    assert [s["name"] for s in r["states"]] == ["Andhra Pradesh", "Uttar Pradesh"]
    assert [s["month"] for s in r["series"]] == ["2025-01", "2025-02", "2026-02"] and r["series"][-1]["provisional"]
    assert r["linking"] == {} and r["weights"] == []


def test_parse_lists_the_tables_it_did_not_find():
    r = cpi2024.parse(release_html(divisions=False, states=False).replace("Jan-25", "Mar-25"), "2026-02")
    # without a Jan-25 row the series table is not recognised either
    assert r["problems"] == ["2026-02: no divisions table found", "2026-02: no states table found",
                             "2026-02: no All-India series table found"]


def test_parse_reads_the_first_releases_linking_factors_and_weights():
    extra = (html_table(["S. no.", "CPI General Level", "Linking factor"], ["", "Rural", "0.5222"], ["", "Combined", "0.5267"])
             + html_table(["Divisions", "Rural", "Urban", "Combined"], ["CPI 2012", "CPI 2024"] * 3,
                          ["Food and beverages", "1", "2", "3", "4", "5", "6"]))
    r = cpi2024.parse(release_html(month_label="Jan-26", extra=extra), "2026-01")
    assert r["linking"] == {"Rural": 0.5222, "Combined": 0.5267}
    assert [w["division"] for w in r["weights"]] == ["Food and beverages"]


# ---- the PDF ---------------------------------------------------------------------------------------

def tiny_pdf(text: str) -> bytes:
    """A one-page PDF showing one line of text (Helvetica), with a correct cross-reference table."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
               b"/Resources << /Font << /F1 5 0 R >> >> >>",
               b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return out


def test_pdf_numbers_writes_every_decimal_with_two_places(tmp_path):
    path = tmp_path / "r.pdf"
    path.write_bytes(tiny_pdf("Index 102.8 and 104.46, inflation -1.5 in 2026; weight 0.5222"))
    # whole numbers (the year) are not figures; 102.8 is printed for 102.80; four decimals are not read whole
    assert cpi2024.pdf_numbers(path) == ["102.80", "104.46", "-1.50"]


# ---- every release: the series, the CSV and the site -----------------------------------------------

def test_dataset_reads_every_saved_release(tmp_path, monkeypatch):
    monkeypatch.setattr(cpi2024, "ROOT", tmp_path)
    monkeypatch.setattr(cpi2024, "CPI2024_RELEASES", {"2026-01": "page1", "2026-02": "page2", "2026-03": "page3"})
    extra = html_table(["S. no.", "CPI General", "Linking factor"], ["1.", "Rural", "0.5222"])
    (tmp_path / "jan.html").write_text(release_html(month_label="Jan-26", extra=extra))
    (tmp_path / "feb.html").write_text(release_html())
    manifest = {"cpi2024/2026-01": {"file": "jan.html", "url": "page1"},
                "cpi2024/2026-01/pdf": {"file": "jan.pdf", "url": "pdf1"},
                "cpi2024/2026-02": {"file": "feb.html", "url": "page2"},
                "cpi2024/2026-02/pdf": {"url": "page2", "empty": True},
                "cpi2024/2026-03": {"url": "page3", "empty": True}}  # not out yet
    c = cpi2024.dataset(manifest)
    assert list(c["releases"]) == ["2026-01", "2026-02"] and c["latest"] == "2026-02"
    assert c["releases"]["2026-01"]["pdf"] == "jan.pdf" and c["releases"]["2026-01"]["pdf_url"] == "pdf1"
    assert c["releases"]["2026-02"]["pdf"] is None and c["releases"]["2026-02"]["pdf_url"] is None
    assert [s["month"] for s in c["series"]] == ["2025-01", "2025-02", "2026-02"]  # the latest release's series
    assert {s["source"] for s in c["series"]} == {"cpi2024/2026-02"}
    assert c["linking"] == {"Rural": 0.5222}  # from the first release
    assert c["cfpi"]["2026-02"]["inflation"] == [5.0, 6.0, 5.5]  # from the latest summary, provisional
    # January's final inflation, from February's release; still provisional, as no final index was printed
    assert c["cfpi"]["2026-01"] == {"index": None, "inflation": [4.0, 5.0, 4.5], "provisional": True,
                                    "source": "cpi2024/2026-02"}


def test_dataset_with_no_release():
    assert cpi2024.dataset({}) == {"releases": {}, "latest": None, "series": [], "cfpi": {}, "linking": {}, "weights": []}


def test_cfpi_of_a_january_release_finalises_december_of_the_year_before():
    rel = {"2025-12": {"summary": {"current": {"cfpi_index": [1.0, 2.0, 3.0], "cfpi_inflation": [4.0, 5.0, 6.0]}}, "source": "a"},
           "2026-01": {"summary": {"current": {}, "previous": {"cfpi_index": [1.5, 2.5, 3.5], "cfpi_inflation": [4.5, 5.5, 6.5]}},
                       "source": "b"}}
    assert cpi2024.cfpi_by_month(rel)["2025-12"] == {"index": [1.5, 2.5, 3.5], "inflation": [4.5, 5.5, 6.5],
                                                     "provisional": False, "source": "b"}


def one_release() -> dict:
    return {"releases": {"2026-01": {
        "source": "cpi2024/2026-01", "url": "page", "pdf_url": None,
        "divisions": [{"code": "01", "name": "Food", "values": [1, 2, 3, 4, 5, 6]}],
        "groups": [], "states": [{"name": "Goa", "values": [None, 2, 2, None, 5, 5]}],
        "series": [{"month": "2025-01", "values": [9, 9, 9, None, None, None], "provisional": False},
                   {"month": "2026-01", "values": [10, 10, 10, 1, 1, 1], "provisional": True}],
        "series_combined": [{"month": "2025-12", "cpi": 8.0, "cfpi": 7.0}, {"month": "2026-01", "cpi": 10.0, "cfpi": 7.5}]}},
        "latest": "2026-01", "series": [], "cfpi": {}, "linking": {"Rural": 0.5}, "weights": []}


def test_csv_rows_one_line_per_figure_with_its_status():
    rows = cpi2024.csv_rows(one_release())
    by_table = {}
    for r in rows:
        by_table.setdefault(r["table"], []).append(r)
    assert len(by_table["division"]) == 3 and len(by_table["state"]) == 3  # rural, urban, combined
    assert [(r["sector"], r["index"], r["inflation"]) for r in by_table["division"]] == [
        ("Rural", 1, 4), ("Urban", 2, 5), ("Combined", 3, 6)]
    assert by_table["state"][0]["index"] is None and by_table["state"][0]["status"] == "provisional"
    series = [(r["month"], r["sector"], r["status"]) for r in by_table["all_india_series"]]
    assert ("2025-01", "Rural", "final") in series and ("2026-01", "Combined", "provisional") in series
    # first release's combined-only series: only its own month is provisional
    combined = [r for r in by_table["all_india_series"] if r["inflation"] is None and r["index"] in (8.0, 10.0)]
    assert [(r["month"], r["status"]) for r in combined] == [("2025-12", "final"), ("2026-01", "provisional")]
    assert {r["release_month"] for r in rows} == {"2026-01"} and {r["source"] for r in rows} == {"cpi2024/2026-01"}


def test_site_part():
    c = one_release()
    c["series"] = c["releases"]["2026-01"]["series"]
    s = cpi2024.site(c)
    assert s["latest"] == "2026-01"
    assert s["series"][-1] == ["2026-01", 10, 10, 10, 1, 1, 1, True]
    assert len(s["series_fields"]) == len(s["series"][0])
    assert s["divisions"] == {"2026-01": [["01", "Food", 1, 2, 3, 4, 5, 6]]}
    assert s["states"]["2026-01"][0][:2] == ["", "Goa"]
    assert s["releases"] == {"2026-01": {"page": "page", "pdf": None}}
    assert s["linking"] == {"Rural": 0.5}

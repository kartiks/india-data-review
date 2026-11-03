"""Population and figures per person: reading the sources, working out per-person figures, and the checks."""

from gdp_pipeline import population as pop


class Report:
    def __init__(self):
        self.sections = []

    def add(self, title, checked, failures, notes):
        self.sections.append((title, checked, failures, notes))


def test_numbers_are_read_from_a_quoted_row_without_its_row_number():
    assert pop.numbers("25 Population (in million) 1383 1395 1408 1421") == [1383, 1395, 1408, 1421]
    assert pop.numbers("3 Gross Domestic Product (GDP) @ 1,76,50,591 1,87,96,955") == [17650591, 18796955]
    assert pop.numbers("27 Per Capita GDP (₹) 2,15,935") == [215935]


def test_net_national_income_is_ndp_plus_gni_minus_gdp():
    node = {"gdp": {"cur": 100.0}, "gni": {"cur": 98.0}, "ndp": {"cur": 88.0}}
    assert pop.nni(node, "cur") == 86.0  # GNI 98 less depreciation 12 (GDP 100 − NDP 88)
    assert pop.nni(node, "con") is None


def test_per_person_figures_are_rupees_per_person():
    node = {"gdp": {"cur": 2_00_000.0, "con": 1_50_000.0}, "pfce": {"cur": 1_20_000.0}}
    # ₹2,00,000 crore over 1,000 million people = ₹2,000 a person
    assert pop.per_person(node, 1000.0) == {"gdp": {"cur": 2000, "con": 1500}, "pfce": {"cur": 1200}}


def test_population_is_implied_by_a_total_and_its_per_person_figure():
    table = {"figures": {"gdp": {"2025-26": 3_23_12_034.0}, "pc_gdp": {"2025-26": 2_27_447.0},
                         "nni": {"2025-26": 2_74_86_593.0}, "pc_nni": {"2025-26": 1_93_480.0}}}
    vals = pop.implied(table, "2025-26")
    assert len(vals) == 2
    assert all(abs(v - 1420.64) < 0.01 for v in vals)


def fake_sources(monkeypatch, projections=None, notes=None, rbi=None, population=None):
    # 1,000 million in 2021 (thousands), rising a million a year; male and female half each.
    proj = projections or {pop.fy(y): {"persons": 990_000.0 + (y - 2011) * 1000, "male": 495_000.0 + (y - 2011) * 500,
                                       "female": 495_000.0 + (y - 2011) * 500} for y in range(2011, 2037)}
    by_series = population or {"2011-12": {"2021-22": {"million": 1000.0, "source": "projections"}}, "2022-23": {}}
    sources = {"projections": proj, "notes": notes or [], "rbi": rbi or [], "note_checked": 0, "problems": []}
    monkeypatch.setattr(pop, "population", lambda manifest: (by_series, sources))


def ds_with(node, series="2011-12", year="2021-22", stage="RE3"):
    return {"data": {series: {"annual": {year: {stage: node}}}}}


def test_check_reproduces_published_per_person_figures_of_the_same_estimate(monkeypatch):
    note = {"document": "Press note", "statement": "S1", "base": "2011-12", "prices": "cur", "years": ["2021-22"],
            "figures": {"gdp": {"2021-22": 2_00_000.0}, "pc_gdp": {"2021-22": 2000.0}}}
    fake_sources(monkeypatch, notes=[note])
    node = {"gdp": {"cur": 2_00_000.0}, "per_person": {"gdp": {"cur": 2000}}}
    report = Report()
    pop.check(ds_with(node), report, manifest={})
    _, checked, failures, notes = report.sections[0]
    assert failures == []
    assert any("2011-12 series: 1 published per-person figures reproduced" in n for n in notes)

    node["per_person"]["gdp"]["cur"] = 2010
    report = Report()
    pop.check(ds_with(node), report, manifest={})
    assert any("GDP per person" in f and "2010 here" in f for f in report.sections[0][2])


def test_check_skips_published_figures_for_an_earlier_estimate(monkeypatch):
    note = {"document": "Press note", "statement": "S1", "base": "2011-12", "prices": "cur", "years": ["2021-22"],
            "figures": {"gdp": {"2021-22": 1_90_000.0}, "pc_gdp": {"2021-22": 1900.0}}}
    fake_sources(monkeypatch, notes=[note])
    node = {"gdp": {"cur": 2_00_000.0}, "per_person": {"gdp": {"cur": 2000}}}  # revised since the press note
    report = Report()
    pop.check(ds_with(node), report, manifest={})
    assert report.sections[0][2] == []
    assert any("2011-12 series: 0 published per-person figures reproduced" in n and "1 are for an earlier estimate" in n
               for n in report.sections[0][3])


def test_check_fails_when_one_table_implies_two_populations(monkeypatch):
    note = {"document": "Press note", "statement": "S1", "base": "2022-23", "prices": "con", "years": ["2025-26"],
            "figures": {"gdp": {"2025-26": 2_00_000.0}, "pc_gdp": {"2025-26": 2000.0},
                        "nni": {"2025-26": 1_80_000.0}, "pc_nni": {"2025-26": 1900.0}}}  # 1,000 and 947 million
    fake_sources(monkeypatch, notes=[note])
    report = Report()
    pop.check({"data": {}}, report, manifest={})
    assert any("imply different populations" in f for f in report.sections[0][2])


def test_check_fails_when_the_projections_do_not_add_up(monkeypatch):
    proj = {pop.fy(y): {"persons": 1_000_000.0 + y, "male": 500_000.0 + y, "female": 500_000.0} for y in range(2011, 2037)}
    proj["2015-16"]["male"] += 10
    fake_sources(monkeypatch, projections=proj)
    report = Report()
    pop.check({"data": {}}, report, manifest={})
    assert any("projections 2015-16: male + female" in f for f in report.sections[0][2])


def test_years_without_population_are_listed_not_failed(monkeypatch):
    fake_sources(monkeypatch)
    ds = {"data": {"2022-23": {"annual": {"2026-27": {"AE1": {"gdp": {"cur": 1.0}}}}}}}
    report = Report()
    pop.check(ds, report, manifest={})
    _, _, failures, notes = report.sections[0]
    assert failures == []
    assert any("2022-23 series: no population for 2026-27" in n for n in notes)


def test_build_adds_per_person_to_the_latest_estimate_where_there_is_a_population(monkeypatch):
    note = {"document": "Press note", "statement": "S1", "base": "2011-12", "prices": "cur", "years": ["2021-22"],
            "figures": {"gdp": {"2021-22": 2_00_000.0}, "pc_gdp": {"2021-22": 2000.0}}}
    fake_sources(monkeypatch, notes=[note], population={"2011-12": {"2021-22": {"million": 1000.0, "source": "projections"}},
                                                        "2022-23": {}})
    tree = {"2011-12": {"annual": {"2021-22": {"RE2": {"gdp": {"cur": 1_90_000.0}}, "RE3": {"gdp": {"cur": 2_00_000.0}}},
                                   "2022-23": {"RE2": {"gdp": {"cur": 2_20_000.0}}}}}}
    block = pop.build({}, tree)
    assert tree["2011-12"]["annual"]["2021-22"]["RE3"]["per_person"] == {"gdp": {"cur": 2000}}
    assert "per_person" not in tree["2011-12"]["annual"]["2021-22"]["RE2"]  # earlier estimate: population of its time
    assert "per_person" not in tree["2011-12"]["annual"]["2022-23"]["RE2"]  # no population
    assert block["projections_until"] == pop.PROJECTIONS_UNTIL
    assert block["checked"] == {"2011-12": {"2021-22": "Press note"}, "2022-23": {}}


def test_check_fails_when_a_quoted_row_is_under_the_wrong_year(monkeypatch):
    # The fixture projects 1,004 million for 2025-26; 1,014 million (ten years on, as if the row were mislabelled)
    # is 1% off.
    note = {"document": "Press note", "statement": "S1", "base": "2022-23", "prices": "con", "years": ["2025-26"],
            "figures": {"gdp": {"2025-26": 1_01_400.0}, "pc_gdp": {"2025-26": 1000.0}}}
    fake_sources(monkeypatch, notes=[note])
    report = Report()
    pop.check({"data": {}}, report, manifest={})
    assert any("check the years of the quoted statement" in f for f in report.sections[0][2])


def test_population_prefers_projections_then_the_newest_note_then_the_rbi(monkeypatch):
    proj = {pop.fy(y): {"persons": 1_000_000.0 + (y - 2021) * 10_000, "male": 0.0, "female": 0.0} for y in range(2011, 2037)}
    older = {"document": "January note", "date": "2026-01-07", "base": "2011-12", "prices": "con", "years": ["2021-22", "2023-24"],
             "statement": "", "figures": {"gdp": {"2021-22": 99_900.0, "2023-24": 1_02_000.0}, "pc_gdp": {"2021-22": 1000.0, "2023-24": 1000.0}}}
    newer = {**older, "document": "June note", "date": "2026-06-05", "years": ["2023-24"],
             "figures": {"gdp": {"2023-24": 1_02_100.0}, "pc_gdp": {"2023-24": 1000.0}}}
    rbi = {**older, "document": "RBI", "date": None, "years": ["2022-23"],
           "figures": {"gdp": {"2022-23": 1_01_100.0}, "pc_gdp": {"2022-23": 1000.0}}}
    monkeypatch.setattr(pop, "read_projections", lambda m: (proj, []))
    monkeypatch.setattr(pop, "read_notes", lambda m: ([older, newer], [], 0))
    monkeypatch.setattr(pop, "read_rbi", lambda m: ([rbi], []))
    by_series, _ = pop.population({})
    old = by_series["2011-12"]
    assert old["2021-22"] == {"million": 1000.0, "source": "projections"}  # projection, not the note's 999
    assert old["2023-24"]["million"] == 1021.0 and old["2023-24"]["document"] == "June note"
    assert old["2022-23"]["million"] == 1011.0 and old["2022-23"]["document"] == "RBI"


def test_a_year_read_twice_from_the_projections_table_is_a_problem(monkeypatch, tmp_path):
    page = "Projected Total Population by Sex as on 1st October INDIA\n2011 12,20,116 6,27,946 5,92,170 1\n2011 12,20,116 6,27,946 5,92,170 1\n"
    monkeypatch.setattr(pop, "path_of", lambda m, k: tmp_path)
    monkeypatch.setattr(pop, "page_text", lambda path, n: page)
    proj, problems = pop.read_projections({})
    assert proj["2011-12"] == {"persons": 1220116, "male": 627946, "female": 592170}
    assert problems == ["projections: year 2011 read twice on page 125"]


def nas_workbook(path):
    """A small copy of NAS Statement 1.2's layout (Hindi and English labels, years across)."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    rows = [
        [None, "STATEMENT 1.2: PER CAPITA INCOME, PRODUCT AND FINAL CONSUMPTION"],
        ["क्र. सं.", "मद", "2023-24", "2024-25", "Item ", "S.No."],
        [1, "जनसंख्या", 1000.5, 1010.25, "Population (in million)", 1],
        [None, "प्रचलित", None, None, "At current prices", None],
        [2, "x", 2000.4, 2100.6, "Per Capita GDP( ₹) ", 2],
        [3, "x", 1900.0, 2000.0, "Per Capita GNI ( ₹) ", 3],
        [4, "x", 1700.0, 1800.0, "Per Capita NNI ( ₹) ", 4],
        [5, "x", 2050.0, 2150.0, "Per Capita GNDI( ₹) ", 5],
        [6, "x", 1200.0, 1300.0, "Per Capita PFCE( ₹) ", 6],
        [None, "स्थिर", None, None, "At constant (2022-23) prices", None],
        [7, "x", 1950.0, 2000.0, "Per Capita GDP ( ₹) ", 7],
        [8, "x", 1850.0, 1900.0, "Per Capita GNI ( ₹) ", 8],
        [9, "x", 1650.0, 1700.0, "Per Capita NNI( ₹) ", 9],
        [10, "x", 1150.0, 1200.0, "Per Capita PFCE( ₹) ", 10],
        [None, "x", None, None, "Percentage change over previous year at constant (2022-23) prices", None],
        [11, "x", None, 2.6, "Per Capita GDP ", 11],
    ]
    for r in rows:
        ws.append(r)
    wb.save(path)


def test_the_nas_statement_is_read_by_its_english_labels(monkeypatch, tmp_path):
    nas_workbook(tmp_path / "s.xlsx")
    monkeypatch.setattr(pop, "path_of", lambda m, k: tmp_path / "s.xlsx")
    tables, problems = pop.read_nas({})
    assert problems == []
    cur, con = tables
    assert cur["prices"] == "cur" and con["prices"] == "con" and cur["years"] == ["2023-24", "2024-25"]
    assert cur["figures"]["population"] == {"2023-24": 1000.5, "2024-25": 1010.25} == con["figures"]["population"]
    assert cur["figures"]["pc_gdp"]["2023-24"] == 2000.4
    assert con["figures"]["pc_gdp"]["2024-25"] == 2000.0  # growth rates after it are not read
    assert cur["exact_population"] and pop.table_population(cur, "2024-25") == 1010.25


def test_a_statement_without_totals_is_compared_through_per_person_times_population():
    # ₹2,000.4 a person × 1,000.5 million = ₹2,00,140.02 crore: the API's total, so the same estimate.
    table = {"document": "NAS", "base": "2022-23", "prices": "cur", "years": ["2023-24"], "exact_population": True,
             "figures": {"population": {"2023-24": 1000.5}, "pc_gdp": {"2023-24": 2000.4}}}
    data = {"2022-23": {"annual": {"2023-24": {"FINAL": {"gdp": {"cur": 2_00_140.0}, "per_person": {"gdp": {"cur": 2000}}}}}}}
    (row,) = pop.comparisons(data, {"notes": [table], "rbi": []})
    assert row[5:] == (2000, 2000.4, "NAS", True)
    data["2022-23"]["annual"]["2023-24"]["FINAL"]["gdp"]["cur"] = 2_10_000.0  # revised since: not compared
    (row,) = pop.comparisons(data, {"notes": [table], "rbi": []})
    assert row[-1] is False


def test_the_newest_mospi_document_gives_the_population(monkeypatch):
    proj = {pop.fy(y): {"persons": 1_000_000.0, "male": 0.0, "female": 0.0} for y in range(2011, 2037)}
    june = {"document": "June note", "date": "2026-06-05", "base": "2022-23", "prices": "con", "years": ["2023-24"],
            "statement": "", "figures": {"gdp": {"2023-24": 1_00_000.0}, "pc_gdp": {"2023-24": 1000.0}}}
    nas = {"document": "NAS", "date": "2026-08-31", "base": "2022-23", "prices": "cur", "years": ["2023-24"],
           "statement": "", "exact_population": True, "figures": {"population": {"2023-24": 1000.004}}}
    monkeypatch.setattr(pop, "read_projections", lambda m: (proj, []))
    monkeypatch.setattr(pop, "read_notes", lambda m: ([june], [], 0))
    monkeypatch.setattr(pop, "read_rbi", lambda m: ([], []))
    monkeypatch.setattr(pop, "read_nas", lambda m: ([nas], []))
    by_series, _ = pop.population({})
    assert by_series["2022-23"]["2023-24"] == {"million": 1000.004, "source": "mospi", "document": "NAS"}


def test_the_committed_nas_2026_statement_reads_as_published():
    from gdp_pipeline.fetch import load_manifest

    tables, problems = pop.read_nas(load_manifest())
    assert problems == []
    cur = next(t for t in tables if t["prices"] == "cur")
    assert cur["years"] == ["2022-23", "2023-24", "2024-25"]
    assert cur["figures"]["population"] == {"2022-23": 1382.894, "2023-24": 1395.478, "2024-25": 1408.054}
    assert round(cur["figures"]["pc_gdp"]["2023-24"], 2) == 208339.27


def statement_rows(*extra, constant_heading="At constant (2022-23) prices", unit="( ₹)"):
    return [
        ("मद", "2023-24", "Item "),
        (None, 1000.5, "Population (in million)"),
        (None, None, "At current prices"),
        (None, 2000.0, f"Per Capita GDP{unit}"), (None, 1900.0, "Per Capita GNI ( ₹)"),
        (None, 1700.0, "Per Capita NNI ( ₹)"), (None, 1200.0, "Per Capita PFCE( ₹)"),
        (None, None, constant_heading),
        (None, 1950.0, "Per Capita GDP ( ₹)"), (None, 1850.0, "Per Capita GNI ( ₹)"),
        (None, 1650.0, "Per Capita NNI( ₹)"), (None, 1150.0, "Per Capita PFCE( ₹)"),
        *extra,
    ]


def test_a_growth_section_headed_like_constant_prices_is_not_read_as_figures():
    rows = statement_rows((None, None, "At constant (2022-23) prices: percentage change over previous year"),
                          (None, 6.3, "Per Capita GDP ( ₹)"))
    figures, _, problems = pop.parse_nas(rows)
    assert problems == []
    assert figures["con"]["pc_gdp"] == {"2023-24": 1950.0}


def test_a_row_read_twice_or_in_another_unit_is_a_problem():
    _, _, problems = pop.parse_nas(statement_rows((None, 1960.0, "Per Capita GDP ( ₹)")))
    assert problems == ["'Per Capita GDP ( ₹)' read twice at constant prices"]
    _, _, problems = pop.parse_nas(statement_rows(unit="(₹ lakh)"))
    assert "'Per Capita GDP(₹ lakh)': unit is not ₹" in problems
    assert any("pc_gdp not read at current prices" in p for p in problems)


def test_documents_that_disagree_on_a_population_fail(monkeypatch):
    june = {"document": "June note", "statement": "S1", "base": "2022-23", "prices": "con", "years": ["2023-24"],
            "figures": {"gdp": {"2023-24": 1_00_400.0}, "pc_gdp": {"2023-24": 1000.0}}}  # 1,004.0 million
    nas = {"document": "NAS", "statement": "", "base": "2022-23", "prices": "cur", "years": ["2023-24"],
           "exact_population": True, "figures": {"population": {"2023-24": 1004.001}}}
    fake_sources(monkeypatch, notes=[june, nas])
    report = Report()
    pop.check({"data": {}}, report, manifest={})
    assert not any("give different populations" in f for f in report.sections[0][2])
    nas["figures"]["population"]["2023-24"] = 1005.0
    report = Report()
    pop.check({"data": {}}, report, manifest={})
    assert any("give different populations" in f for f in report.sections[0][2])


def test_a_press_note_total_far_from_the_api_is_a_revision_not_a_failure(monkeypatch):
    note = {"document": "Press note", "statement": "S1", "base": "2022-23", "prices": "con", "years": ["2023-24"],
            "figures": {"gdp": {"2023-24": 1_00_000.0}, "pc_gdp": {"2023-24": 1000.0}}}  # since revised by 100%
    fake_sources(monkeypatch, notes=[note])
    ds = {"data": {"2022-23": {"annual": {"2023-24": {"FINAL": {"gdp": {"con": 2_00_000.0}, "per_person": {"gdp": {"con": 2000}}}}}}}}
    report = Report()
    pop.check(ds, report, manifest={})
    assert not any("misread" in f for f in report.sections[0][2])


def test_a_published_total_far_from_the_api_is_a_misread_not_a_revision(monkeypatch):
    table = {"document": "NAS", "statement": "", "base": "2022-23", "prices": "con", "years": ["2023-24"],
             "exact_population": True, "figures": {"population": {"2023-24": 1000.0}, "pc_gdp": {"2023-24": 6.3}}}
    fake_sources(monkeypatch, notes=[table])
    ds = {"data": {"2022-23": {"annual": {"2023-24": {"FINAL": {"gdp": {"con": 2_00_000.0}, "per_person": {"gdp": {"con": 2000}}}}}}}}
    report = Report()
    pop.check(ds, report, manifest={})
    assert any("a misread row, unit or section" in f for f in report.sections[0][2])


def test_add_refuses_to_put_another_file_under_an_edition_unless_told(monkeypatch, tmp_path, capsys):
    import pytest

    from gdp_pipeline import fetch as F

    monkeypatch.setattr(F, "ROOT", tmp_path)
    monkeypatch.setattr(F, "RAW", tmp_path / "sources" / "raw")
    monkeypatch.setattr(F, "SNAPSHOTS", tmp_path / "sources" / "snapshots")
    monkeypatch.setattr(F, "MANIFEST", tmp_path / "sources" / "manifest.json")
    key = pop.NAS_STATEMENTS[-1]["key"]
    a, b, bad = tmp_path / "a.xlsx", tmp_path / "b.xlsx", tmp_path / "c.xlsx"
    a.write_bytes(b"PK first"), b.write_bytes(b"PK second"), bad.write_bytes(b"<html>")
    pop.add_by_hand(a, key)
    assert F.load_manifest()[key]["file_name"] == "a.xlsx"
    pop.add_by_hand(a, key)
    assert "unchanged" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="already holds another file"):
        pop.add_by_hand(b, key)
    with pytest.raises(SystemExit, match="not an xlsx file"):
        pop.add_by_hand(bad, key)
    with pytest.raises(SystemExit, match="no such file"):
        pop.add_by_hand(tmp_path / "missing.xlsx", key)
    pop.add_by_hand(b, key, replace=True)
    assert F.load_manifest()[key]["file_name"] == "b.xlsx"


def test_fetch_carries_on_when_a_hand_downloaded_file_is_missing(monkeypatch, capsys):
    monkeypatch.setattr(pop, "documents", lambda: [])
    pop.fetch({}, False)  # no exception: the refresh goes on
    assert "Download it from" in capsys.readouterr().out


# ---- check failures not covered above ---------------------------------------------------------------------------

def check_failures(monkeypatch, ds=None, **sources):
    fake_sources(monkeypatch, **sources)
    report = Report()
    pop.check(ds or {"data": {}}, report, manifest={})
    return report.sections[0][2]


def projections(changes=None):
    out = {pop.fy(y): {"persons": 990_000.0 + (y - 2011) * 1000, "male": 495_000.0 + (y - 2011) * 500,
                       "female": 495_000.0 + (y - 2011) * 500} for y in range(2011, 2037)}
    return {**out, **(changes or {})}


def test_a_source_that_could_not_be_read_fails(monkeypatch):
    fake_sources(monkeypatch)
    sources = pop.population({})[1]
    sources["problems"].append("RBI table 1: layout changed (no year or base-year row)")
    report = Report()
    pop.check({"data": {}}, report, manifest={})
    assert report.sections[0][2] == ["RBI table 1: layout changed (no year or base-year row)"]


def test_projections_missing_a_year_fail(monkeypatch):
    proj = projections()
    proj.pop("2036-37")
    failures = check_failures(monkeypatch, projections=proj)
    assert failures == ["projections: years read ['2011-12']…['2035-36'] (25), expected 2011 to 2036"]


def test_projections_that_do_not_rise_fail(monkeypatch):
    failures = check_failures(monkeypatch, projections=projections(
        {"2020-21": {"persons": 990_000.0, "male": 495_000.0, "female": 495_000.0}}))
    assert failures == ["projections 2020-21: population does not rise from 2019-20"]


def test_implied_population_far_from_the_printed_one_fails(monkeypatch):
    note = {"document": "Press note", "statement": "S1", "base": "2022-23", "prices": "con", "years": ["2025-26"],
            "figures": {"gdp": {"2025-26": 1_00_400.0}, "pc_gdp": {"2025-26": 1000.0},
                        "population": {"2025-26": 1010.0}}}  # implies 1,004 million, prints 1,010
    failures = check_failures(monkeypatch, notes=[note])
    assert failures == ["Press note, S1, 2025-26: implied population 1004.000 million, printed 1,010"]


def test_population_far_from_the_rbis_reprint_fails(monkeypatch):
    rbi = {"document": "RBI", "statement": "", "base": "2011-12", "prices": "cur", "years": [],
           "figures": {"population_lakh": {"2021-22": 10_010.0}}}  # 1,001 million; 1,000 used here
    failures = check_failures(monkeypatch, rbi=[rbi])
    assert failures == ["2011-12 series, 2021-22: population 1000.000 million here, RBI 10,010 lakh"]


def test_mospi_population_off_the_projection_before_2022_23_fails(monkeypatch):
    # The fixture projects 1,000 million for 2021-22; MoSPI's figure must equal it in those years.
    note = {"document": "Press note", "statement": "S1", "base": "2011-12", "prices": "cur", "years": ["2021-22"],
            "figures": {"gdp": {"2021-22": 1_00_100.0}, "pc_gdp": {"2021-22": 1000.0}}}  # 1,001 million
    failures = check_failures(monkeypatch, notes=[note])
    assert failures == ["2011-12 series, 2021-22: MoSPI's population (implied, 1001.000 million, Press note) differs "
                        "from the projection (1000.000) by +0.100%"]

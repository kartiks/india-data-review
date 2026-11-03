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

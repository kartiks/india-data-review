"""Reading PLFS files in the layout MoSPI's data service has used since November 2026, and in the one before."""

import json

import pytest

from jobs_prices_pipeline import common, plfs


def test_plain_year():
    assert plfs.plain_year("PLFS 2025") == "2025"
    assert plfs.plain_year("2025") == "2025" and plfs.plain_year("2023-24") == "2023-24" and plfs.plain_year("") == ""


@pytest.mark.parametrize("field, category, expected", [
    ("nco_division", "Division 1", ("nco_division", plfs.NCO_DIVISIONS[1])),
    ("nco_division", "Division  2", ("nco_division", plfs.NCO_DIVISIONS[2])),  # MoSPI's double space
    ("nco_division", "NCO Division 9: ELEMENTARY OCCUPATIONS", ("nco_division", plfs.NCO_DIVISIONS[9])),
    ("nco_division", "Sub-division 11", ("nco_subdivision", "11")),
    ("nco_division", "34", ("nco_subdivision", "34")),  # a sub-division printed without its label
    ("nco_division", "111", ("nco_group", "111")),
    ("nco_division", "total", ("nco_division", "All")),
    ("nic_division", "   A", ("nic_section", "A")),
    ("nic_division", "  01", ("nic_division", "01")),
    ("nic_division", " 011", ("nic_group", "011")),
    ("nic_division", "0111", ("nic_class", "0111")),
    ("nic_division", "total", ("nic_division", "All")),
    ("industry_section", "A_Agriculture, forestry and fishing", ("industry_section", "A_Agriculture, forestry and fishing")),
])
def test_level(field, category, expected):
    assert plfs.level(field, category) == expected


@pytest.mark.parametrize("field, category", [
    ("nco_division", "Division 12"), ("nco_division", "Managers"), ("nic_division", "  A"), ("nic_division", "011"),
])
def test_level_refuses_a_category_that_fits_no_level(field, category):
    with pytest.raises(ValueError, match="fits no level"):
        plfs.level(field, category)


@pytest.fixture
def files(tmp_path, monkeypatch):
    keys = [f"plfs/annual/ind0{i}" for i in (1, 2, 3, 4)]
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "queries", lambda: [(k, "plfs/getData", {}) for k in keys])

    def write(code, rows):
        key = f"plfs/annual/ind0{code}"
        path = tmp_path / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        base = {"year": "PLFS 2025", "year_type": "Calendar Year", "state": "Bihar", "sector": "rural",
                "gender": "male", "weekly_status": "PS+SS", "frequency": "Annually", "unit": "%",
                "indicator": f"indicator {code}"}
        path.write_text(json.dumps({"query": {"indicator_code": code}, "rows": [{**base, **r} for r in rows]}))
        return key

    return write


def test_annual_rates_in_the_new_layout(files):
    rows = [  # LFPR, WPR, UR: 50, 47.5, 5 for 15 and over, and for the 'all' rows that repeat it
        {"AgeGroup": "15 years and above"}, {"AgeGroup": "15 years and above", "religion": "all"},
        {"AgeGroup": "15 years and above", "socialGroup": "all"},
        {"General_Education": "all"},  # the education block's total, a second copy (here a little off)
        {"General_Education": "7.graduate"},
    ]
    values = {1: ["50", "50", "50", "50.1", "60"], 2: ["47.5", "47.5", "47.5", "47.6", "54"], 3: ["5", "5", "5", "5", "10"]}
    manifest = {files(code, [{**r, "value": v} for r, v in zip(rows, vs)]): {"file": f"plfs/annual/ind0{code}.json"}
                for code, vs in values.items()}
    problems: list[str] = []
    out = plfs.read(manifest, problems)
    assert problems == []
    got = {(r["year"], r["age"], r["religion"], r["social_group"], r["education"]): (r["lfpr"], r["wpr"], r["ur"], r["source"])
           for r in out["rates"]}
    src = "plfs/annual/ind01 plfs/annual/ind02 plfs/annual/ind03"
    assert got == {("2025", "15 years and above", "all", "all", "all"): (50.0, 47.5, 5.0, src),
                   ("2025", "15 years and above", "all", "all", "7.graduate"): (60.0, 54.0, 10.0, src)}


def test_workers_in_the_new_layout(files):
    rows = [
        {"nco_division": "Division 1", "value": "60"}, {"nco_division": "Division  2", "value": "40"},
        {"nco_division": "Sub-division 11", "value": "100"}, {"nco_division": "total", "value": "100"},
        {"nic_division": "   A", "value": "100"}, {"nic_division": "  01", "value": "100"},
        {"employee_contract": "1.with no written job contract", "value": "59.6"},
        {"broad_status_employment": "4.regular wage/salary", "industry": "10-33 (manufacturing)", "value": "20"},
        {"nco_division": "Managers", "value": "1"},
    ]
    problems: list[str] = []
    out = plfs.read({files(4, rows): {"file": "plfs/annual/ind04.json"}}, problems)
    assert [(r["year"], r["breakdown"], r["category"], r["value"]) for r in out["distribution"]] == [
        ("2025", "nco_division", plfs.NCO_DIVISIONS[1], 60.0), ("2025", "nco_division", plfs.NCO_DIVISIONS[2], 40.0),
        ("2025", "nco_subdivision", "11", 100.0), ("2025", "nco_division", "All", 100.0),
        ("2025", "nic_section", "A", 100.0), ("2025", "nic_division", "01", 100.0)]
    # job conditions by calendar year, beside indicator 5's July-June years
    assert [(r["year"], r["year_type"], r["condition"], r["value"]) for r in out["conditions"]] == [
        ("2025", "Calendar Year", "1.with no written job contract", 59.6)]
    assert out["crossed"] == ["plfs/annual/ind04: 2025, Bihar, rural, male, PS+SS 10-33 (manufacturing) × 4.regular wage/salary"]
    assert problems == ["plfs/annual/ind04: 2025, Bihar, rural, male, PS+SS: nco_division category 'Managers' fits no level"]

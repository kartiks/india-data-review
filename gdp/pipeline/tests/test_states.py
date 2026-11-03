"""The state accounts: how rows are arranged, what is derived, and what is left out."""

from gdp_pipeline import states


def row(code, state, year, cur, con, industry="", sub=""):
    ind, unit, _ = states.INDICATORS[code]
    return {"base_year": "2011-12", "state": state, "year": year, "indicator_code": code, "indicator": ind,
            "industry": industry, "subindustry": sub, "current_price": cur, "constant_price": con, "unit": unit,
            "left_out": ""}


def test_lakh_figures_become_crore_and_growth_is_named():
    tree, notes = states.arrange([
        row(29, "Goa", "2020-21", 1_000_000, 800_000, industry="total"),
        row(26, "Goa", "2020-21", 7.5, 5.1),
    ])
    node = tree["2011-12"]["Goa"]["2020-21"]
    assert node["gsva"]["total"] == {"cur": 10_000, "con": 8_000}
    assert node["growth"]["gsdp"] == {"real": 5.1, "nominal": 7.5}
    assert notes == []


def test_gsdp_is_derived_where_not_published_and_its_growth_worked_out():
    rows = []
    for year, (va, tax, sub) in {"2021-22": (90_000_00, 12_000_00, 2_000_00), "2022-23": (99_000_00, 13_000_00, 2_000_00)}.items():
        rows += [row(29, "Haryana", year, va, va, industry="total"), row(33, "Haryana", year, tax, tax),
                 row(34, "Haryana", year, sub, sub)]
    tree, _ = states.arrange(rows)
    years = tree["2011-12"]["Haryana"]
    assert years["2021-22"]["gsdp"] == {"cur": 100_000, "con": 100_000, "derived": True}
    assert years["2022-23"]["gsdp"] == {"cur": 110_000, "con": 110_000, "derived": True}
    assert years["2022-23"]["growth"]["gsdp"] == {"real": 10.0, "nominal": 10.0, "published": False}


def test_published_gsdp_is_not_replaced():
    tree, _ = states.arrange([
        row(23, "Goa", "2020-21", 100_000, 90_000),
        row(29, "Goa", "2020-21", 1, 1, industry="total"), row(33, "Goa", "2020-21", 1, 1), row(34, "Goa", "2020-21", 1, 1),
    ])
    assert tree["2011-12"]["Goa"]["2020-21"]["gsdp"] == {"cur": 100_000, "con": 90_000}


def test_net_figure_equal_to_gross_is_left_out():
    rows = [
        row(31, "Karnataka", "2022-23", 344_527, 203_314),
        row(32, "Karnataka", "2022-23", 344_527, 344_527),  # the second table repeats the gross figure
        row(25, "Karnataka", "2022-23", 311_709, 181_487),
        row(29, "Karnataka", "2022-23", 5_000, 4_000, industry="total"),
        row(30, "Karnataka", "2022-23", 5_000, 5_000, industry="total"),
        row(30, "Karnataka", "2022-23", 1_000, 1_000, industry="agriculture", sub="crops"),
    ]
    tree, notes = states.arrange(rows)
    node = tree["2011-12"]["Karnataka"]["2022-23"]
    assert "pc_nsdp_alt" not in node and "nsva" not in node and "nsva_sub" not in node
    assert node["pc_nsdp"] == {"cur": 311_709, "con": 181_487}
    assert len(notes) == 2 and all(n.startswith("Karnataka: ") for n in notes)
    assert all(states.allowed("source", n) for n in notes)  # both are known, explained source errors
    assert [r["indicator_code"] for r in rows if r["left_out"]] == [32, 30, 30]


def raw(state, year, cur, con=None, unit="₹ Crore"):
    return {"state": state, "year": year, "indicator": "Gross State Domestic Product", "current_price": cur,
            "constant_price": con if con is not None else cur, "unit": unit}


def load_from(tmp_path, monkeypatch, rows):
    import json
    monkeypatch.setattr(states, "ROOT", tmp_path)
    monkeypatch.setattr(states, "STATE_SERIES", [("2011-12", "Current", "Annually")])
    monkeypatch.setattr(states, "STATE_INDICATORS", [23])
    monkeypatch.setattr(states, "KNOWN_STATES", ["Goa", "Kerala"])
    f = tmp_path / "ind23.json"
    f.write_text(json.dumps({"rows": rows}))
    return states.load({"nas/2011-12/Current/Annually/ind23": {"file": "ind23.json", "url": "u", "sha256": "s"}})


def test_unknown_or_missing_state_is_a_problem(tmp_path, monkeypatch):
    rows, problems = load_from(tmp_path, monkeypatch, [raw("Goa", "2020-21", "100"), raw("Goa & Daman", "2020-21", "5")])
    assert [r["state"] for r in rows] == ["Goa"]
    assert any("unknown state" in p and "Goa & Daman" in p for p in problems)
    assert any("no rows at all for Kerala" in p for p in problems)


def test_conflicting_duplicate_is_a_problem_and_identical_one_is_dropped(tmp_path, monkeypatch):
    rows, problems = load_from(tmp_path, monkeypatch, [
        raw("Goa", "2020-21", "100"), raw("Goa", "2020-21", "100"),  # identical: kept once
        raw("Kerala", "2020-21", "200"), raw("Kerala", "2020-21", "210"),  # different: a problem
    ])
    assert len([r for r in rows if r["state"] == "Goa"]) == 1
    assert any("published twice with different values" in p and "Kerala" in p for p in problems)


def test_coverage_counts_last_years_weight_of_the_states_reporting():
    data = {
        "Big": {"2023-24": {"gsdp": {"cur": 90}}, "2024-25": {"gsdp": {"cur": 99}}},
        "Small": {"2023-24": {"gsdp": {"cur": 10}}},
    }
    assert states.coverage(data, "2024-25") == 0.9

"""The state accounts' failure paths not covered in test_states.py: rows load cannot use, net figures that reach the
gross one, derived GSDP that must not override published growth, the NSDP identity, and the whole build-and-check
run on a tiny saved source (written to tmp_path)."""

import json

import pytest

from gdp_pipeline import states
from gdp_pipeline import states_checks as sc


def raw(state, year, cur, con=None, unit="₹ Crore", **kw):
    return {"state": state, "year": year, "indicator": "x", "current_price": cur,
            "constant_price": con if con is not None else cur, "unit": unit, **kw}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    """Writes {code: rows} as the 2011-12 state files and returns their manifest."""
    monkeypatch.setattr(states, "ROOT", tmp_path)
    monkeypatch.setattr(states, "DATA", tmp_path / "data")
    monkeypatch.setattr(sc, "DATA", tmp_path / "data")
    monkeypatch.setattr(states, "STATE_SERIES", [("2011-12", "Current", "Annually")])
    monkeypatch.setattr(states, "KNOWN_STATES", ["Goa"])
    monkeypatch.setattr(sc, "KNOWN_STATES", ["Goa"])

    def write(files: dict):
        monkeypatch.setattr(states, "STATE_INDICATORS", sorted(files))
        manifest = {}
        for code, rows in files.items():
            (tmp_path / f"ind{code}.json").write_text(json.dumps({"rows": rows}))
            manifest[f"nas/2011-12/Current/Annually/ind{code}"] = {"file": f"ind{code}.json", "url": f"u{code}",
                                                                   "sha256": f"s{code}"}
        return manifest
    return write


def test_a_row_without_a_state_or_year_is_a_problem(saved):
    rows, problems = states.load(saved({23: [raw("Goa", "2020-21", "1"), raw(None, "2020-21", "2"),
                                             raw("Goa", None, "3")]}))
    assert len(rows) == 1
    assert problems == ["nas/2011-12/Current/Annually/ind23: row with year '2020-21', state None not understood",
                        "nas/2011-12/Current/Annually/ind23: row with year None, state 'Goa' not understood"]


def test_an_indicator_recorded_as_empty_is_skipped(saved):
    manifest = saved({23: [raw("Goa", "2020-21", "1")], 24: [raw("Goa", "2020-21", "1")]})
    manifest["nas/2011-12/Current/Annually/ind24"] = {"url": "u24", "empty": True}
    rows, problems = states.load(manifest)
    assert [r["indicator"] for r in rows] == ["gsdp"] and problems == []


def test_with_no_rows_on_the_site_s_base_no_state_is_reported_missing(saved):
    # Every state is reported missing only once some state has rows: a base with none at all is not a coverage problem
    rows, problems = states.load({})
    assert rows == [] and problems == []


def test_value_added_in_lakh_is_stored_in_crore_and_an_unknown_industry_left_out(saved):
    total = "Total Gross State Value Added"
    rows, problems = states.load(saved({29: [raw("Goa", "2020-21", "123456", "100000", unit="₹ Lakh", industry=total),
                                             raw("Goa", "2020-21", "1", unit="₹ Lakh")]}))  # no industry at all
    assert problems == ["nas/2011-12/Current/Annually/ind29: unknown industry ''"]
    assert states.pair(rows[0]) == {"cur": 1234.56, "con": 1000.0}


def test_nsdp_not_below_gsdp_is_left_out_and_noted_for_every_year():
    def row(code, year, v):
        ind, unit, _ = states.INDICATORS[code]
        return {"base_year": "2011-12", "state": "Goa", "year": year, "indicator_code": code, "indicator": ind,
                "industry": "", "subindustry": "", "current_price": v, "constant_price": v, "unit": unit,
                "left_out": ""}
    rows = [row(23, "2020-21", 100.0), row(24, "2020-21", 100.0), row(23, "2021-22", 110.0),
            row(24, "2021-22", 111.0), row(23, "2022-23", 120.0), row(24, "2022-23", 100.0)]
    tree, notes = states.arrange(rows)
    goa = tree["2011-12"]["Goa"]
    assert "nsdp" not in goa["2020-21"] and "nsdp" not in goa["2021-22"] and goa["2022-23"]["nsdp"]["cur"] == 100.0
    assert notes == ["Goa: NSDP (ind24) is not below the gross figure, 2020-21 to 2021-22 (2 years), 2011-12 base; "
                     "left out"]
    assert [(r["year"], r["indicator"]) for r in rows if r["left_out"]] == [("2020-21", "nsdp"), ("2021-22", "nsdp")]
    # a case nobody has looked at fails the checks
    assert sc.EXCEPTIONS.reason("source", notes[0]) is None


def test_derived_gsdp_never_replaces_published_growth_and_needs_the_year_before():
    tree = {"2011-12": {"Assam": {
        "2021-22": {"gsva": {"total": {"cur": 90.0}}, "taxes": {"cur": 12.0}, "subsidies": {"cur": 2.0}},
        "2022-23": {"gsva": {"total": {"cur": 99.0}}, "taxes": {"cur": 13.0}, "subsidies": {"cur": 2.0},
                    "growth": {"gsdp": {"nominal": 9.9}}},
        "2024-25": {"gsva": {"total": {"cur": 99.0}}, "taxes": {"cur": 13.0}, "subsidies": {"cur": 2.0}},
    }}}
    states.derive_gsdp(tree)
    years = tree["2011-12"]["Assam"]
    assert years["2022-23"]["gsdp"] == {"cur": 110.0, "derived": True}
    assert years["2022-23"]["growth"]["gsdp"] == {"nominal": 9.9}  # MoSPI's published rate stays
    assert "growth" not in years["2021-22"] and "growth" not in years["2024-25"]  # no year before to compare with


# ---- checks -------------------------------------------------------------------------------------------------------

class Report:
    def __init__(self):
        self.sections = []

    def add(self, title, checked, failures, notes=(), allowed=None):
        self.sections.append((title, checked, failures, [*(allowed.notes() if allowed else []), *notes]))


def st_of(data, bases=("2011-12",)):
    return {"data": {b: data.get(b, {}) for b in bases}, "bases": list(bases), "source_problems": [], "left_out": []}


def test_nsdp_that_is_not_net_value_added_plus_taxes_less_subsidies_fails():
    node = {"nsdp": {"con": 900.0}, "nsva": {"total": {"con": 800.0}}, "taxes": {"con": 120.0},
            "subsidies": {"con": 20.0}}
    report = Report()
    sc.check_identities(st_of({"2011-12": {"Goa": {"2023-24": node}}}), report)
    (_, checked, failures, _), = report.sections
    assert (checked, failures) == (1, [])
    node["nsdp"]["con"] = 905.0
    report = Report()
    sc.check_identities(st_of({"2011-12": {"Goa": {"2023-24": node}}}), report)
    assert report.sections[0][2] == ["Goa, 2023-24, con: NSDP 905 but NSVA + taxes - subsidies = 900 (₹ crore)"]


def test_a_state_publishing_no_subsidies_is_checked_without_them_and_noted():
    node = {"gsdp": {"cur": 1_100.0}, "gsva": {"total": {"cur": 1_000.0}}, "taxes": {"cur": 100.0}}
    report = Report()
    sc.check_identities(st_of({"2011-12": {"Chhattisgarh": {"2023-24": node}}}), report)
    (_, checked, failures, notes), = report.sections
    assert (checked, failures) == (1, [])
    assert notes == ["Chhattisgarh publishes no subsidies on products; its GSDP and NSDP equal value added plus "
                     "taxes on products."]


def test_a_derived_gsdp_is_not_checked_against_its_own_parts_but_is_named():
    node = {"gsdp": {"cur": 5.0, "derived": True}, "gsva": {"total": {"cur": 1_000.0}}, "taxes": {"cur": 100.0},
            "subsidies": {"cur": 1.0}}
    report = Report()
    sc.check_identities(st_of({"2011-12": {"Assam": {"2023-24": node}}}), report)
    (_, checked, failures, notes), = report.sections
    assert (checked, failures) == (0, []) and notes == ["GSDP worked out as GSVA + taxes - subsidies (no GSDP "
                                                        "published): Assam."]


def test_a_new_base_is_reported_with_the_states_not_on_it_yet(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "DATA", tmp_path)
    monkeypatch.setattr(sc, "KNOWN_STATES", ["Goa", "Kerala"])
    (tmp_path / "state_accounts.csv").write_text("header\na\nb\nc\n")
    st = st_of({"2011-12": {"Goa": {}, "Kerala": {}}, "2022-23": {"Goa": {}}}, bases=("2011-12", "2022-23"))
    report = Report()
    sc.check_rows(st, report)
    (_, checked, failures, notes), = report.sections
    assert (checked, failures) == (3, [])  # one check per row of state_accounts.csv
    assert notes[0].startswith("MoSPI now publishes state accounts on the 2022-23 base (not yet for Kerala).")


AGRICULTURE = "Agriculture, Livestock, Forestry and Fishing"


def test_build_then_check_on_a_tiny_saved_source(saved):
    total = "Total Gross State Value Added"
    manifest = saved({
        23: [raw("Goa", "2022-23", "100", "90"), raw("Goa", "2023-24", "110", "95")],
        26: [raw("Goa", "2023-24", "10", "5.6", unit="%")],
        29: [raw("Goa", "2022-23", "9000", "8000", unit="₹ Lakh", industry=total),
             raw("Goa", "2023-24", "9900", "8500", unit="₹ Lakh", industry=total),
             raw("Goa", "2022-23", "4000", "3000", unit="₹ Lakh", industry=AGRICULTURE),
             raw("Goa", "2023-24", "4900", "3500", unit="₹ Lakh", industry=AGRICULTURE),
             raw("Goa", "2022-23", "5000", "5000", unit="₹ Lakh", industry="Manufacturing"),
             raw("Goa", "2023-24", "5000", "5000", unit="₹ Lakh", industry="Manufacturing")],
        33: [raw("Goa", "2022-23", "1200", "1100", unit="₹ Lakh"), raw("Goa", "2023-24", "1300", "1200", unit="₹ Lakh")],
        34: [raw("Goa", "2022-23", "200", "100", unit="₹ Lakh"), raw("Goa", "2023-24", "200", "200", unit="₹ Lakh")],
    })
    ds = states.build(manifest)
    data_dir = states.DATA
    assert json.loads((data_dir / "states.json").read_text())["data"] == ds["data"]
    lines = (data_dir / "state_accounts.csv").read_text().splitlines()
    assert len(lines) == 1 + 13 and lines[0].startswith("base_year,state,year,indicator_code")
    assert ds["data"]["2011-12"]["Goa"]["2023-24"]["growth"]["gsdp"] == {"real": 5.6, "nominal": 10.0}

    report = Report()
    sc.check({"data": {}}, report)  # reads the states.json just written
    failures = {title: f for title, _, f, _ in report.sections if f}
    assert failures == {}
    # one wrong figure at the source makes the run fail
    manifest = saved({23: [raw("Goa", "2022-23", "100", "90"), raw("Goa", "2023-24", "110", "95")],
                      26: [raw("Goa", "2023-24", "12", "5.6", unit="%")]})
    states.build(manifest)
    report = Report()
    sc.check({"data": {}}, report)
    failures = [f for _, _, fs, _ in report.sections for f in fs]
    assert failures == ["Goa, 2023-24, gsdp_growth nominal: published 12.0%, levels give 10.00%"]

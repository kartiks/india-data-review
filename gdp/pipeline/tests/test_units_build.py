"""build.py on small hand-made inputs: load_rows' failure paths, dedupe, arrange and long_run; and the Budget's GDP
assumption (budget.assumption)."""

import json
from pathlib import Path

import pytest

from gdp_pipeline import budget, build

ROOT = Path(__file__).resolve().parents[2]
KEY = "nas/2022-23/Current/Annually/ind05"


# ---- load_rows ----------------------------------------------------------------------------------------------------

@pytest.fixture
def one_file(tmp_path, monkeypatch):
    """Writes the rows as the current file of ind05 and returns its manifest."""
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "NAS_SERIES", [("2022-23", "Current", "Annually")])
    monkeypatch.setattr(build, "NAS_INDICATORS", [5])

    def write(rows, **entry):
        path = tmp_path / "sources" / "raw" / f"{KEY}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"rows": rows}))
        return {KEY: {"url": "https://api.example/nas", "file": f"sources/raw/{KEY}.json", "sha256": "sha0",
                      "fetched_at": "2026-09-01T00:00:00+00:00", **entry}}
    return write


def gdp(year="2024-25", stage="Final Estimates", value="100", **kw):
    return {"year": year, "indicator": "Gross Domestic Product", "revision": stage, "current_price": value,
            "constant_price": value, "unit": "₹ Crore", **kw}


def test_an_entry_marked_empty_or_missing_from_the_manifest_is_skipped(one_file):
    assert build.load_rows({}) == ([], [], [])
    manifest = one_file([gdp()])
    assert build.load_rows({KEY: {"url": "u", "empty": True, "checked_at": "2026-09-01"}}) == ([], [], [])
    assert len(build.load_rows(manifest)[0]) == 1


def test_a_snapshot_listed_in_the_manifest_but_missing_on_disk_is_an_error(one_file):
    manifest = one_file([gdp()], history=[{"file": "sources/snapshots/2026-08-01/gone.json", "sha256": "old",
                                           "fetched_at": "2026-08-01T00:00:00+00:00"}])
    with pytest.raises(FileNotFoundError, match="gone.json"):
        build.load_rows(manifest)


def test_rows_that_cannot_be_used_are_left_out_and_each_reported(one_file):
    manifest = one_file([
        gdp(),
        gdp(year="1999"),  # MoSPI's row labelled with one year
        gdp(stage="Third Advance Estimates"),  # no such stage
        gdp(year="2023-24", industry="Space Mining"),  # kept, but the industry is unknown
        gdp(year="2023-24", stage="Provisional Estimates", institutional_sector="Martians"),
    ])
    rows, problems, _ = build.load_rows(manifest)
    assert [(r["year"], r["stage"], r["industry"], r["sector"]) for r in rows] == [
        ("2024-25", "FINAL", "", ""), ("2023-24", "FINAL", "", ""), ("2023-24", "PE", "", "")]
    assert problems == [
        f"{KEY}: row with year '1999' left out (not a fiscal year): Gross Domestic Product Final Estimates 100",
        f"{KEY}: unknown estimate stage 'Third Advance Estimates'",
        f"{KEY}: unknown industry 'Space Mining'",
        f"{KEY}: unknown institutional sector 'Martians'",
    ]


def test_figures_are_read_as_numbers_and_blank_ones_as_none(one_file):
    manifest = one_file([{**gdp(), "current_price": "2,79,741.5", "constant_price": None}])
    (row,), _, _ = build.load_rows(manifest)
    assert (row["current_price"], row["constant_price"]) == (279741.5, None)
    assert build.pair(row) == {"cur": 279741.5}


def test_a_back_series_row_without_a_stage_is_back_and_a_quarter_without_one_latest():
    rows = {}
    for series, freq in (("Back", "Annually"), ("Current", "Quarterly")):
        row, problems = build.read_row({**gdp(year="1999-2000", stage=None), "quarter": "Q1" if freq == "Quarterly" else None},
                                       "k", "2011-12", series, freq, 5, "u", "s")
        assert problems == []
        rows[series] = row
    assert (rows["Back"]["series"], rows["Back"]["stage"], rows["Back"]["year"]) == ("2011-12-back", "BACK", "1999-00")
    assert (rows["Current"]["frequency"], rows["Current"]["stage"], rows["Current"]["quarter"]) == (
        "quarterly", "LATEST", "Q1")


# ---- dedupe -------------------------------------------------------------------------------------------------------

def row(indicator, industry="", sector="", cur=None, con=None, unit="₹ Crore", stage="FINAL", year="2023-24",
        subindustry=""):
    return {"series": "2022-23", "frequency": "annual", "year": year, "quarter": "", "stage": stage,
            "indicator": indicator, "industry": industry, "industry_as_printed": industry, "subindustry": subindustry,
            "sector": sector, "sector_as_printed": sector, "current_price": cur, "constant_price": con, "unit": unit}


def test_a_total_repeated_with_its_industry_left_blank_is_kept_once_with_the_name():
    blank, named = row("gva", cur=100.0, con=90.0), row("gva", "total", cur=100.0, con=90.0)
    for rows in ([blank, named], [named, blank]):
        out, notes = build.dedupe(rows)
        assert notes == [] and len(out) == 1
        assert (out[0]["industry"], out[0]["current_price"], out[0]["constant_price"]) == ("total", 100.0, 90.0)


@pytest.mark.parametrize("indicator, field", [("gva", "industry"), ("gva_growth", "industry"),
                                              ("gcf_by_industry", "industry"), ("saving", "sector"),
                                              ("cfc", "sector"), ("gfcf", "sector")])
def test_a_lone_total_with_no_industry_or_sector_is_named_total(indicator, field):
    (out,), _ = build.dedupe([row(indicator, cur=1.0)])
    assert out[field] == "total"


def test_a_figure_one_copy_leaves_blank_is_taken_from_the_other():
    (out,), notes = build.dedupe([row("gva", cur=100.0), row("gva", "total", con=90.0)])
    assert notes == [] and (out["current_price"], out["constant_price"]) == (100.0, 90.0)


def test_copies_within_rounding_are_one_row():
    out, notes = build.dedupe([row("gva", cur=100.0), row("gva", "total", cur=102.0)])
    assert notes == [] and len(out) == 1 and out[0]["current_price"] == 100.0  # the first copy's figure


def test_copies_that_disagree_are_both_left_out_and_reported():
    out, notes = build.dedupe([row("gva", cur=100.0, con=90.0), row("gva", "total", cur=103.0, con=90.0),
                               row("gdp", cur=500.0)])
    assert [r["indicator"] for r in out] == ["gdp"]  # neither copy is used
    assert notes == ["2022-23 series, 2023-24, gva, FINAL, total: published twice with different current-price "
                     "value (100 and 103); neither is used"]


def test_growth_rates_that_disagree_by_more_than_a_rounding_step_are_reported():
    ok, notes = build.dedupe([row("gva_growth", con=5.0, unit="%"), row("gva_growth", "total", con=5.04, unit="%")])
    assert len(ok) == 1 and notes == []
    out, notes = build.dedupe([row("gva_growth", con=5.0, unit="%"), row("gva_growth", "total", con=5.1, unit="%")])
    assert out == [] and len(notes) == 1 and "different real growth (5 and 5.1)" in notes[0]


def test_different_estimates_industries_and_subindustries_are_not_copies():
    rows = [row("gva", "mining", cur=1.0), row("gva", "mining", cur=2.0, stage="RE1"),
            row("gva", "manufacturing", cur=3.0), row("gva", "manufacturing", cur=4.0, subindustry="textiles"),
            row("gva", "mining", cur=5.0, year="2024-25")]
    out, notes = build.dedupe(rows)
    assert notes == [] and [r["current_price"] for r in out] == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_dedupe_leaves_its_input_rows_unchanged():
    rows = [row("gva", cur=100.0), row("gva", "total", con=90.0)]
    before = json.dumps(rows)
    build.dedupe(rows)
    assert json.dumps(rows) == before


# ---- arrange ------------------------------------------------------------------------------------------------------

def node_of(rows, period="2023-24", stage="FINAL", series="2022-23", freq="annual"):
    return build.arrange(rows)[series][freq][period][stage]


def test_each_indicator_lands_in_its_place_in_the_tree():
    node = node_of([
        row("gdp", cur=500.0, con=400.0),
        row("gdp_growth", cur=9.0, con=6.5, unit="%"),
        row("gva_growth", "total", cur=8.0, con=6.0, unit="%"),
        row("gva", "total", cur=450.0, con=360.0),
        row("gva", "manufacturing", cur=80.0),
        row("gva", "manufacturing", cur=10.0, subindustry="textiles"),
        row("gcf_by_industry", "mining", cur=7.0),
        row("gcf_by_industry", "mining", cur=3.0, subindustry="coal"),  # sub-industries of investment: not in the tree
        row("gfcf", sector="total", cur=150.0),
        row("gfcf", sector="households", cur=60.0),
        row("saving", sector="government", cur=-5.0),
        row("pfce", cur=300.0),
    ])
    assert node == {
        "gdp": {"cur": 500.0, "con": 400.0},
        "growth": {"gdp": {"real": 6.5, "nominal": 9.0}},
        "gva_growth": {"total": {"real": 6.0, "nominal": 8.0}},
        "gva_by_industry": {"total": {"cur": 450.0, "con": 360.0}, "manufacturing": {"cur": 80.0}},
        "gva_sub": {"manufacturing": {"textiles": {"cur": 10.0}}},
        "gcf_by_industry": {"mining": {"cur": 7.0}},
        "gfcf": {"cur": 150.0},
        "gfcf_by_sector": {"households": {"cur": 60.0}},
        "saving_by_sector": {"government": {"cur": -5.0}},
        "pfce": {"cur": 300.0},
    }


def test_quarters_are_filed_under_year_and_quarter():
    r = {**row("gdp", cur=120.0), "frequency": "quarterly", "quarter": "Q2", "stage": "LATEST"}
    tree = build.arrange([r])
    assert tree["2022-23"]["quarterly"]["2023-24 Q2"]["LATEST"]["gdp"] == {"cur": 120.0}
    assert "annual" not in tree["2022-23"]


def test_broad_service_groups_are_summed_from_their_parts_where_only_the_parts_are_published():
    gva = node_of([row("gva", "trade_hotels", cur=30.0, con=20.0), row("gva", "transport_comm", cur=10.0),
                   row("gva", "financial", cur=5.0, con=4.0), row("gva", "real_estate", cur=6.0, con=5.0),
                   row("gva", "public_admin", cur=1.0)])["gva_by_industry"]
    # summed only for a price basis every part has; no group where a part is missing
    assert gva["trade_transport"] == {"cur": 40.0, "summed": True}
    assert gva["finance_realestate"] == {"cur": 11.0, "con": 9.0, "summed": True}
    assert "public_other" not in gva


def test_a_published_broad_group_is_not_replaced_by_its_parts():
    gva = node_of([row("gva", "trade_transport", cur=41.0), row("gva", "trade_hotels", cur=30.0),
                   row("gva", "transport_comm", cur=10.0)])["gva_by_industry"]
    assert gva["trade_transport"] == {"cur": 41.0}


# ---- long_run -----------------------------------------------------------------------------------------------------

def tree(back, cur):
    """back: {year: (cur, con)}; cur: {year: {stage: (cur, con, published real growth or None)}}."""
    def gdp(c, k):
        return {k2: v for k2, v in (("cur", c), ("con", k)) if v is not None}
    out = {"2011-12-back": {"annual": {y: {"BACK": {"gdp": gdp(c, k)}} for y, (c, k) in back.items()}},
           "2011-12": {"annual": {}}}
    for y, stages in cur.items():
        out["2011-12"]["annual"][y] = {}
        for st, (c, k, g) in stages.items():
            node = {"gdp": gdp(c, k)}
            if g is not None:
                node["growth"] = {"gdp": {"real": g}}
            out["2011-12"]["annual"][y][st] = node
    return out


def test_long_run_joins_the_back_series_to_the_latest_estimate_of_each_later_year():
    t = tree({"2009-10": (80.0, 90.0), "2010-11": (100.0, 100.0), "2011-12": (110.0, 105.0)},
             {"2011-12": {"FINAL": (111.0, 111.0, None)},
              "2012-13": {"AE1": (120.0, 110.0, 4.5), "RE3": (125.0, 112.0, 5.5)}})
    rows = build.long_run(t)
    assert [(r["year"], r["series"], r["stage"]) for r in rows] == [
        ("2009-10", "2011-12-back", "BACK"), ("2010-11", "2011-12-back", "BACK"),
        ("2011-12", "2011-12-back", "BACK"),  # the base year comes from the back series
        ("2012-13", "2011-12", "RE3")]  # the latest estimate, not the first
    assert "growth" not in rows[0]
    assert rows[1]["growth"] == {"real": 11.1, "nominal": 25.0, "published": False}
    assert rows[3]["growth"] == {"real": 5.5, "published": True}


def test_long_run_growth_without_current_prices_has_no_nominal_figure():
    rows = build.long_run(tree({"1950-51": (None, 100.0), "1951-52": (None, 103.0)}, {}))
    assert rows[1]["growth"] == {"real": 3.0, "nominal": None, "published": False}


def test_long_run_works_out_no_growth_without_constant_prices():
    rows = build.long_run(tree({"1950-51": (100.0, None), "1951-52": (103.0, 100.0)}, {}))
    assert "growth" not in rows[1]


# ---- budget.assumption ----------------------------------------------------------------------------------------------

SENTENCE = ("GDP for BE 2024-25 has been projected at ₹3,26,36,912 crore assuming 10.5% growth over the "
            "Provisional Estimates of FY 2023-24 of ₹2,95,35,667 crore.")
ENTRY = {"url": "https://budget.example/bag1.pdf", "sha256": "abc", "file": "sources/raw/budget/x/bag1.pdf"}


def test_a_budget_not_downloaded_has_no_assumption(monkeypatch):
    monkeypatch.setattr(budget, "texts", lambda year, path: pytest.fail("nothing to read"))
    assert budget.assumption(2024, {}) is None


def test_the_assumption_is_read_from_the_first_text_with_the_sentence(monkeypatch):
    asked = []

    def texts(year, path):
        asked.append((year, path))
        return ["Budget at a Glance, no sentence here", "header " + SENTENCE + " footer"], None

    monkeypatch.setattr(budget, "texts", texts)
    a = budget.assumption(2024, {"budget/2024-25/bag1": ENTRY})
    assert asked == [("2024-25", budget.ROOT / ENTRY["file"])]
    assert a == {"budget": "2024-25", "gdp_crore": 32636912, "printed_year": "2024-25", "growth_pct": 10.5,
                 "over": "Provisional Estimates of FY 2023-24", "base_gdp_crore": 29535667,
                 "text": SENTENCE.rstrip("."), "url": ENTRY["url"], "sha256": "abc",
                 "document": "Budget at a Glance 2024-25"}


def test_a_document_without_the_sentence_has_no_assumption(monkeypatch):
    monkeypatch.setattr(budget, "texts", lambda year, path: (["GDP growth is expected to be strong"], None))
    assert budget.assumption(2024, {"budget/2024-25/bag1": ENTRY}) is None


def test_a_sentence_read_from_the_rendered_page_carries_its_note():
    # 2025-26's text layer lacks the numbers: the sentence comes from IMAGE_READ, and the file is never opened
    a = budget.assumption(2025, {"budget/2025-26/bag1": {**ENTRY, "file": "no/such/file.pdf"}})
    assert (a["gdp_crore"], a["growth_pct"], a["base_gdp_crore"]) == (35697923, 10.1, 32411406)
    assert "rendered page" in a["note"]


def test_a_committed_budget_at_a_glance_reads_as_published():
    manifest = json.loads((ROOT / "sources" / "manifest.json").read_text())
    a = budget.assumption(2013, manifest)
    assert (a["budget"], a["printed_year"], a["gdp_crore"]) == ("2013-14", "2013-2014", 11371886)
    assert a["sha256"] == manifest["budget/2013-14/bag1"]["sha256"] and "note" not in a

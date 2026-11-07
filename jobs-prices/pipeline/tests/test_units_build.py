"""build.py function by function, on small hand-made datasets. The conftest's data_dir points build.DATA at a
temporary folder, so nothing here writes jobs-prices/data/."""

import csv
import json

import pytest

from jobs_prices_pipeline import build
from jobs_prices_pipeline.plfs import RATE_DIMS


def read_csv(path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# ---- write_csv and fields_of -----------------------------------------------------------------------

def test_write_csv_keeps_as_printed_text_only_where_it_is_not_the_number(data_dir):
    data_dir.mkdir()
    rows = [{"state": "Goa", "value": 12.5, "value_as_printed": "12.50", "extra": "ignored"},
            {"state": "Goa", "value": None, "value_as_printed": "l0.8"},
            {"state": "Goa", "value": None, "value_as_printed": None},
            {"state": "Goa", "value": 3.0, "value_as_printed": "3.1"}]
    build.write_csv("t.csv", ["state", "value", "value_as_printed"], rows)
    assert read_csv(data_dir / "t.csv") == [
        {"state": "Goa", "value": "12.5", "value_as_printed": ""},  # the same number: not repeated
        {"state": "Goa", "value": "", "value_as_printed": "l0.8"},  # not a number: kept
        {"state": "Goa", "value": "", "value_as_printed": ""},
        {"state": "Goa", "value": "3.0", "value_as_printed": "3.1"}]  # a different number: kept


def test_fields_of_puts_the_first_columns_first_and_source_last():
    rows = [{"source": "a", "x": 1, "state": "Goa"}, {"y": 2, "x": 3}]
    assert build.fields_of(rows, ["state", "value"]) == ["state", "value", "x", "y", "source"]
    assert build.fields_of([], ["state"]) == ["state", "source"]


# ---- the compact table and the site's JSON ---------------------------------------------------------

def test_table_stores_text_once_and_keeps_numbers():
    t = build.table(["state", "year", "value"], [["Goa", 2024, 1.5], ["Bihar", 2024, None], ["Goa", 2025, 2.0]])
    assert t["labels"] == {"state": ["Bihar", "Goa"]}  # a column with no text keeps its values
    assert t["rows"] == [[1, 2024, 1.5], [0, 2024, None], [1, 2025, 2.0]]
    assert build.table(["state"], []) == {"fields": ["state"], "labels": {}, "rows": []}


def unpack(t: dict) -> list[dict]:
    """The rows of a compact table as dicts, with text looked up."""
    return [{f: (t["labels"][f][v] if f in t["labels"] and v is not None else v) for f, v in zip(t["fields"], r)}
            for r in t["rows"]]


def rate_row(left_out="", **kw):
    return {"frequency": "annual", "year_type": "calendar", **{d: "all" for d in RATE_DIMS}, "state": "Goa",
            "lfpr": 50.0, "wpr": 47.5, "ur": 5.0, "left_out": left_out, **kw}


def worker(state="Goa", breakdown="broad_industry_work", status="CWS", category="Agriculture", frequency="annual"):
    return {"frequency": frequency, "year": "2024", "state": state, "sector": "rural", "gender": "male",
            "status": status, "breakdown": breakdown, "category": category, "value": 40.0}


def cpi(state, subgroup, sector="Combined", group="General Index"):
    return {"month": "2025-01", "state": state, "sector": sector, "group": group, "subgroup": subgroup,
            "index": 200.0, "inflation": 4.0}


def hces(indicator, left_out="", **kw):
    return {"indicator": indicator, "year": "2023-24", "state": "Goa", "sector": "Rural",
            "imputation_type": "Without Imputation", "category": "", "value": 5000.0, "left_out": left_out, **kw}


MPCE = "Average monthly per capita consumption expenditure (MPCE)"


@pytest.fixture
def ds() -> dict:
    return {
        "description": "d", "generated_at": "now", "sources": {"k": {"url": "u"}},
        "plfs": {"indicators": {"1": "LFPR"},
                 "rates": [rate_row(), rate_row(left_out="inconsistent", state="Bihar")],
                 "distribution": [
                     worker(),  # broad industry: published in CWS only, so shown
                     worker(category="All"),  # the total row: not a share
                     worker(frequency="quarterly"),
                     worker(breakdown="broad_status_employment", status="PS+SS", category="2. helper"),
                     worker(breakdown="broad_status_employment", status="PS+SS", category="2. helper", state="All India"),
                     worker(breakdown="broad_status_employment", status="CWS", category="2. helper"),  # usual status only
                     worker(breakdown="enterprise_type", status="PS+SS", category="Proprietary"),  # All India only
                     worker(breakdown="enterprise_type", status="PS+SS", category="Proprietary", state="All India"),
                 ],
                 "conditions": [], "earnings": []},
        "cpi": [cpi("All India", "General-Overall"), cpi("All India", "Food", group="Food and beverages"),
                cpi("Goa", "General-Overall", sector="Rural")],
        "cpialrl": [{"month": "2025-01", "indicator": "General Index", "base_year": "2019", "state": "Goa", "index_al": 1.0},
                    {"month": "2025-01", "indicator": "Group Index", "base_year": "2019", "state": "Goa", "index_al": 2.0}],
        "hces": [hces(MPCE), hces(MPCE, left_out="mismatch", state="Assam"), hces("Average Per Capita Monthly Quantity Consumption ")],
        "cpi2024": {"releases": {}, "latest": None, "series": [], "cfpi": {}, "linking": {}, "weights": []},
        "rbi": [{"table": 8, "table_id": "unemployment_rural", "title": "T8", "unit": "Per Thousands",
                 "variant": "Rural Male", "state": "Goa", "year": "2023-24", "value": 41.0}],
        "rbi_editions": {8: "2024-25", 9: "2024-25"},
        "hces_overall": [{"year": "2023-24", "state": "Goa", "mpce": 5123.456, "persons_rural_00": 10, "source": "x"}],
        "source_problems": ["p"],
    }


def test_site_json_shows_what_the_site_uses(ds):
    site = build.site_json(ds)
    assert [r["state"] for r in unpack(site["plfs"]["rates"])] == ["Goa"]  # left-out combinations are not shown
    workers = [(r["state"], r["breakdown"], r["status"], r["category"]) for r in unpack(site["plfs"]["workers"])]
    assert workers == [("Goa", "broad_industry_work", "CWS", "Agriculture"),
                       ("Goa", "broad_status_employment", "PS+SS", "2. helper"),
                       ("All India", "enterprise_type", "PS+SS", "Proprietary")]
    assert set(site["cpi"]["all_india"]) == {"General Index|General-Overall", "Food and beverages|Food"}
    assert site["cpi"]["all_india"]["General Index|General-Overall"]["Combined"] == [["2025-01", 200.0, 4.0]]
    assert set(site["cpi"]["states"]) == {"All India", "Goa"} and set(site["cpi"]["states"]["Goa"]) == {"Rural"}
    assert [r["index_al"] for r in unpack(site["cpialrl"])] == [1.0]  # general index only
    assert [(r["indicator"], r["state"]) for r in unpack(site["hces"])] == [("mpce", "Goa")]
    assert site["rbi"]["editions"] == ["2024-25"]
    assert site["rbi"]["titles"] == {"unemployment_rural": "T8"} and site["rbi"]["units"] == {"unemployment_rural": "Per Thousands"}
    assert unpack(site["rbi"])[0]["value"] == 41.0
    assert site["hces_overall"] == [{"year": "2023-24", "state": "Goa", "mpce": 5123.46, "persons_rural_00": 10}]
    assert site["source_problems"] == ["p"] and site["cpi2024"]["latest"] is None
    json.dumps(site)  # all of it serialisable


# ---- outputs, assemble and main --------------------------------------------------------------------

def test_outputs_names_every_csv_with_its_rows(ds):
    out = build.outputs(ds)
    assert set(out) == {"plfs_rates.csv", "plfs_workers.csv", "plfs_conditions.csv", "plfs_earnings.csv", "cpi.csv",
                        "cpialrl.csv", "hces.csv", "rbi_states.csv", "hces_overall.csv", "cpi2024.csv"}
    assert out["cpi.csv"][0] is ds["cpi"] and out["plfs_rates.csv"][0] is ds["plfs"]["rates"]
    assert out["plfs_rates.csv"][1][-1] == "left_out"
    assert out["cpi2024.csv"] == ([], ["table", "month", "code", "name", "sector", "index", "inflation", "status", "release_month"])


def test_assemble_reads_every_source_through_its_reader(tmp_path, monkeypatch):
    manifest = {"cpi/x": {"url": "u", "sha256": "s", "fetched_at": "t", "records": 3, "file": "f"},
                "plfs/y": {"url": "u2", "empty": True}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(build, "MANIFEST", tmp_path / "manifest.json")
    seen = {}

    def reader(name, value, problem=None):
        def read(m, problems=None):
            seen[name] = m
            if problem:
                problems.append(problem)
            return value
        return read

    monkeypatch.setattr(build.plfs, "read", reader("plfs", {"rates": []}, "plfs: odd row"))
    monkeypatch.setattr(build.prices, "cpi", reader("cpi", ["cpi"], "cpi: odd row"))
    monkeypatch.setattr(build.prices, "cpialrl", reader("cpialrl", ["alrl"]))
    monkeypatch.setattr(build.hces, "read", reader("hces", ["hces"]))
    monkeypatch.setattr(build.hces, "population", reader("population", ["pop"]))
    monkeypatch.setattr(build.hces, "overall", lambda pop, rows: [("overall", pop, rows)])
    monkeypatch.setattr(build.rbi, "read_all", lambda m: (["rbi"], ["rbi problem"], {8: "2024-25"}))
    monkeypatch.setattr(build.cpi2024, "dataset", reader("cpi2024", {"releases": {}}))

    ds = build.assemble()
    assert all(m == manifest for m in seen.values())
    assert ds["sources"] == {"cpi/x": {"url": "u", "sha256": "s", "fetched_at": "t", "records": 3}}  # empty ones left out
    assert ds["source_problems"] == ["plfs: odd row", "cpi: odd row"]  # every reader's problems, in one list
    assert ds["hces_overall"] == [("overall", ["pop"], ["hces"])]
    assert (ds["rbi"], ds["rbi_problems"], ds["rbi_editions"]) == (["rbi"], ["rbi problem"], {8: "2024-25"})
    assert ds["cpi"] == ["cpi"] and ds["cpialrl"] == ["alrl"] and ds["cpi2024"] == {"releases": {}}


def test_main_writes_every_file(ds, data_dir, monkeypatch):
    ds["plfs"]["rates"][0]["unused"] = ""  # blank in every row: dropped from plfs_*.csv
    monkeypatch.setattr(build, "assemble", lambda: ds)
    assert build.main() is ds
    names = {p.name for p in data_dir.iterdir()}
    assert names == set(build.outputs(ds)) | {"sources.csv", "jobs_prices.json"}
    rates = read_csv(data_dir / "plfs_rates.csv")
    assert [r["state"] for r in rates] == ["Goa", "Bihar"]  # the CSV keeps left-out rows, with the reason
    assert rates[1]["left_out"] == "inconsistent" and "unused" not in rates[0]
    assert read_csv(data_dir / "plfs_conditions.csv") == []  # no rows: written all the same
    assert read_csv(data_dir / "sources.csv") == [{"key": "k", "url": "u", "sha256": "", "fetched_at": "", "records": ""}]
    text = (data_dir / "jobs_prices.json").read_text()
    assert text.endswith("}\n") and ", " not in text.split('"description"')[0]  # compact
    assert json.loads(text) == json.loads(json.dumps(build.site_json(ds)))

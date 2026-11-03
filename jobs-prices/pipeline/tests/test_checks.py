"""Every check fails on bad data: small hand-made datasets, each with one thing wrong, next to the same data
without it. (The RBI unit and state GDP checks are in test_rbi.py.)"""

import copy

import pytest
from conftest import failures_of, run_check

from jobs_prices_pipeline.checks import jobs, prices, prices2024, spending, states, values
from jobs_prices_pipeline.plfs import RATE_DIMS


def notes_of(check, ds) -> list[str]:
    return [n for s in run_check(check, ds).sections for n in s.notes]


# ---- source values ---------------------------------------------------------------------------------

def empty_ds(**kw) -> dict:
    return {"source_problems": [], "plfs": {"rates": [], "distribution": [], "conditions": [], "earnings": [],
                                            "unlabelled": []}, "cpi": [], "cpialrl": [], "hces": [], **kw}


def test_source_problems_fail_and_unreadable_values_are_allowed():
    assert failures_of(values.check_source, empty_ds()) == []
    assert failures_of(values.check_source, empty_ds(source_problems=["cpi/x: published twice"])) == ["cpi/x: published twice"]
    ds = empty_ds(hces=[{"year": "2023-24", "state": "Goa", "indicator": "MPCE", "value": None, "value_as_printed": "l0.8"}])
    report = run_check(values.check_source, ds)
    assert report.failures == 0 and report.sections[0].allowed[0]["cases"] == 1


# ---- jobs ------------------------------------------------------------------------------------------

def rate(gender="person", lfpr=50.0, wpr=47.5, ur=5.0, frequency="annual", **kw) -> dict:
    r = {"frequency": frequency, "year_type": "calendar", **{d: "all" for d in RATE_DIMS}, "year": "2024", "period": "",
         "state": "Bihar", "sector": "rural", "gender": gender, "age": "15+", "status": "PS+SS",
         "lfpr": lfpr, "wpr": wpr, "ur": ur, "left_out": ""}
    r.update({f"{k}_as_printed": str(r[k]) for k in ("lfpr", "wpr", "ur")}, **kw)
    return r


def plfs_ds(rates=(), distribution=(), conditions=(), earnings=()) -> dict:
    return {"plfs": {"rates": list(rates), "distribution": list(distribution), "conditions": list(conditions),
                     "earnings": list(earnings)}}


def test_rates_identity():
    assert failures_of(jobs.check_rates, plfs_ds([rate()])) == []
    assert failures_of(jobs.check_rates, plfs_ds([rate(wpr=46.0)]))  # 50 × 0.95 = 47.5
    # within SMALL_GAP: shown, with a note
    assert failures_of(jobs.check_rates, plfs_ds([rate(wpr=47.3)])) == []
    assert any("Within" in n for n in notes_of(jobs.check_rates, plfs_ds([rate(wpr=47.3)])))
    # left out by the build: allowed, not checked
    assert failures_of(jobs.check_rates, plfs_ds([rate(wpr=46.0, left_out="inconsistent")])) == []


def test_totals_between_their_parts():
    def rates(person):
        return [rate("person", lfpr=person, wpr=person * 0.95), rate("male", lfpr=60.0, wpr=57.0), rate("female", lfpr=40.0, wpr=38.0)]

    assert failures_of(jobs.check_brackets, plfs_ds(rates(50.0))) == []
    fails = failures_of(jobs.check_brackets, plfs_ds(rates(70.0)))
    assert any(f.startswith("lfpr") and "outside male 60.0 and female 40.0" in f for f in fails)

    def earnings(freq, person):
        base = {"frequency": freq, "year": "2024", "period": "" if freq == "annual" else "Q1", "state": "Bihar",
                "sector": "rural", "kind": "regular"}
        return [{**base, "gender": g, "value": v} for g, v in (("person", person), ("male", 20000.0), ("female", 15000.0))]

    assert failures_of(jobs.check_brackets, plfs_ds(earnings=earnings("annual", 25000.0)))
    # not shown on the site: a note only
    assert failures_of(jobs.check_brackets, plfs_ds(earnings=earnings("quarterly", 25000.0))) == []


def shares(values_by_category, frequency="annual", breakdown="broad_industry_work", status="CWS", state="Bihar") -> list[dict]:
    base = {"frequency": frequency, "breakdown": breakdown, "year": "2024", "period": "", "state": state,
            "sector": "rural", "gender": "male", "status": status}
    return [{**base, "category": c, "value": v, "value_as_printed": str(v)} for c, v in values_by_category.items()]


def test_shares_of_workers_add_up_to_100():
    ok = {"Agriculture": 40.0, "Industry": 25.0, "Services": 35.0}
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=shares(ok))) == []
    short = {"Agriculture": 40.0, "Industry": 25.0, "Services": 25.0}
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=shares(short))) == [
        "annual broad_industry_work: 2024, Bihar, rural, male, CWS: shares add up to 90.0%"]
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=shares(short, frequency="quarterly"))) == []
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=shares({"Agriculture": None, "Industry": None})))
    # by type of work: all self-employed = own-account workers + helpers
    status = {"1. own account": 30.0, "2. helper": 10.0, "3. all self-employed": 45.0, "4. regular": 20.0, "5. casual": 40.0}
    fails = failures_of(jobs.check_distribution, plfs_ds(distribution=shares(status, breakdown="broad_status_employment", status="PS+SS")))
    assert any("all self-employed 45.0 ≠ 30.0 + 10.0" in f for f in fails)


# ---- prices ----------------------------------------------------------------------------------------

def cpi_row(month, index, inflation=None, state="All India", sector="Combined", subgroup="General-Overall"):
    return {"month": month, "state": state, "sector": sector, "subgroup": subgroup, "index": index, "inflation": inflation}


def test_cpi_inflation_reproduced():
    ok = [cpi_row("2024-01", 100.0), cpi_row("2025-01", 105.0, 5.0)]
    assert failures_of(prices.check_cpi_inflation, {"cpi": ok}) == []
    assert failures_of(prices.check_cpi_inflation, {"cpi": [cpi_row("2024-01", 100.0), cpi_row("2025-01", 105.0, 5.2)]})


def test_cpi_combined_between_rural_and_urban():
    rows = [cpi_row("2025-01", 100.0, sector="Rural"), cpi_row("2025-01", 110.0, sector="Urban")]
    assert failures_of(prices.check_cpi_combined, {"cpi": rows + [cpi_row("2025-01", 105.0)]}) == []
    assert failures_of(prices.check_cpi_combined, {"cpi": rows + [cpi_row("2025-01", 111.0)]})


def test_cpi_no_month_missing():
    rows = [cpi_row("2025-01", 100.0), cpi_row("2025-02", 100.0), cpi_row("2025-03", 100.0),
            cpi_row("2025-01", 100.0, state="Goa"), cpi_row("2025-03", 100.0, state="Goa")]
    assert failures_of(prices.check_cpi_months, {"cpi": rows}) == []  # Goa's gap is a note
    assert any("Goa" in n for n in notes_of(prices.check_cpi_months, {"cpi": rows}))
    fails = failures_of(prices.check_cpi_months, {"cpi": [r for r in rows if r["month"] != "2025-02" or r["state"] != "All India"]})
    assert fails == ["CPI general index, All India, Combined: no index for 1 months (2025-02)"]


def test_cpialrl_inflation_reproduced():
    def row(month, index, inflation):
        return {"month": month, "indicator": "General Index", "base_year": "2019", "state": "Bihar",
                "index_al": index, "index_al_as_printed": str(index), "inflation_al": inflation}

    assert failures_of(prices.check_cpialrl, {"cpialrl": [row("2024-06", 130.0, None), row("2025-06", 136.5, 5.0)]}) == []
    assert failures_of(prices.check_cpialrl, {"cpialrl": [row("2024-06", 130.0, None), row("2025-06", 136.5, 4.0)]})


# ---- household spending ----------------------------------------------------------------------------

CLASSES = ["0-5", "5-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90", "90-95", "95-100"]


def hces_row(indicator, value, **kw):
    return {"year": "2023-24", "state": "Goa", "sector": "Rural", "imputation_type": "Without Imputation",
            "indicator": indicator, "value": value, "left_out": "", **kw}


def hces_classes(average):
    # every class at 1,000: the population-weighted average is 1,000
    return [hces_row(spending.MPCE, average)] + [
        hces_row(spending.MPCE + " Over 12 Fractile Classes", 1000.0, mpce_fractile_classes=c) for c in CLASSES]


def hces_shares(cereal):
    rows = [("Food Total", 50.0), ("Non-Food Total", 50.0), ("Cereal", cereal), ("Milk and Milk Products", 50.0 - 20.0),
            ("Conveyance", 50.0)]
    return [hces_row(spending.CATEGORY_SHARES, v, item_category=c) for c, v in rows]


def test_hces_classes_and_categories_add_up():
    assert failures_of(spending.check_hces, {"hces": hces_classes(1000.0) + hces_shares(20.0)}) == []
    assert failures_of(spending.check_hces, {"hces": hces_classes(1100.0)}) == [
        "HCES 2023-24, Goa, Rural, Without Imputation: spending classes average ₹1,000, published average ₹1,100"]
    assert failures_of(spending.check_hces, {"hces": hces_shares(25.0)}) == [
        "HCES 2023-24, Goa, Rural, Without Imputation %: food items add up to 55.00, food total 50.0"]
    assert failures_of(spending.check_hces, {"hces": []}) == ["no HCES data"]


def test_hces_overall():
    pop = [{"year": "2023-24", "state": s, "sector": sec, "persons_00": p, "mpce_a2": m}
           for s, p in (("Goa", 100), ("All India", 100)) for sec, m in (("Rural", 1000.0), ("Urban", 2000.0))]
    api = [hces_row(spending.MPCE, m, state=s, sector=sec) for s in ("Goa", "All India") for sec, m in (("Rural", 1000.0), ("Urban", 2000.0))]
    overall = [{"year": "2023-24", "state": "Goa", "imputation_type": "Without Imputation", "mpce_rural": 1000.0,
                "mpce_urban": 2000.0, "mpce": 1500.0}]
    ds = {"hces_population": pop, "hces": api, "hces_overall": overall}
    assert failures_of(spending.check_hces_overall, ds) == []

    bad = copy.deepcopy(ds)
    bad["hces"][0]["value"] = 1010.0  # the data service and Table A2 disagree
    bad["hces_population"][2]["persons_00"] = 300  # All India is not the states' sum
    bad["hces_overall"][0]["mpce"] = 2500.0  # overall outside rural and urban
    fails = failures_of(spending.check_hces_overall, bad)
    assert len(fails) == 3
    assert failures_of(spending.check_hces_overall, {**ds, "hces_population": []}) == ["Table A2 not read"]


# ---- RBI handbook ----------------------------------------------------------------------------------

def rbi_rec(table, state, year, value, variant=""):
    return {"table": table, "state": state, "year": year, "value": value, "variant": variant}


def test_rbi_read_needs_enough_states_from_one_edition():
    from jobs_prices_pipeline.rbi import RBI_STATE_TABLES

    recs = [{**rbi_rec(n, f"State {i}", "2023-24", 1.0, spec.variants[0]), "unit": spec.unit}
            for n, spec in RBI_STATE_TABLES.items() for i in range(30 if n != 112 else 10)]
    ds = {"rbi": recs, "rbi_problems": [], "rbi_editions": {8: "2024-25", 9: "2023-24"}}
    fails = failures_of(states.check_rbi_read, ds)
    assert any("RBI table 112 (wage_construction): 10 states read, expected at least 18" in f for f in fails)
    assert any("different editions" in f for f in fails)


def test_rbi_inflation_agrees_with_mospi_indices():
    cpi = [cpi_row(f"{y}-{m:02d}", 100.0 if (y, m) < (2023, 4) else 110.0, state="Kerala")
           for y in (2022, 2023, 2024) for m in range(1, 13)]
    ok = {"cpi": cpi, "rbi": [rbi_rec(108, "Kerala", "2023-24", 10.0)]}
    assert failures_of(states.check_rbi_inflation, ok) == []
    assert failures_of(states.check_rbi_inflation, {**ok, "rbi": [rbi_rec(108, "Kerala", "2023-24", 5.0)]}) == [
        "Kerala 2023-24: RBI 5.0%, MoSPI's indices give 10.00%"]


def test_rbi_totals_within_their_parts():
    unemployment = [rbi_rec(8, "Goa", "2023-24", v, f"Rural {g}") for g, v in (("Male", 50.0), ("Female", 60.0))]
    wages = [rbi_rec(112, s, "2023-24", v) for s, v in (("Goa", 400.0), ("Bihar", 300.0))]
    ok = unemployment + wages + [rbi_rec(8, "Goa", "2023-24", 55.0, "Rural Overall"), rbi_rec(112, "All India", "2023-24", 350.0)]
    assert failures_of(states.check_rbi_totals, {"rbi": ok}) == []
    bad = unemployment + wages + [rbi_rec(8, "Goa", "2023-24", 70.0, "Rural Overall"), rbi_rec(112, "All India", "2023-24", 500.0)]
    assert len(failures_of(states.check_rbi_totals, {"rbi": bad})) == 2


# ---- consumer prices, base 2024 --------------------------------------------------------------------

def six(index, inflation):
    return [index, index, index, inflation, inflation, inflation]


def release(month="2026-01") -> dict:
    """A release that passes every check: inflation 2% everywhere, 2025 at 100 and January 2026 at 102."""
    divisions = [{"code": f"{i:02d}", "name": f"Division {i}", "values": six(102.0, 2.0)} for i in range(1, 13)]
    return {
        "divisions": divisions + [{"code": "00", "name": "All India", "values": six(102.0, 2.0)}],
        "groups": [{"code": f"{i:02d}.1", "name": f"Group {i}", "values": six(102.0, 2.0)} for i in range(43)],
        "states": [{"name": f"State {i}", "values": six(102.0, 2.0)} for i in range(36)],
        "series": [{"month": f"2025-{m:02d}", "values": [100.0, 100.0, 100.0, None, None, None], "provisional": False}
                   for m in range(1, 13)] + [{"month": "2026-01", "values": six(102.0, 2.0), "provisional": True}],
        "series_combined": [], "problems": [],
        "summary": {"current": {"general_inflation": [2.0, 2.0, 2.0]}},
        "headline": {"rural": 2.0, "urban": 2.0, "combined": 2.0},
        "pdf": None,
    }


def cpi2024_ds(rel: dict | None = None, linking=0.5) -> dict:
    rel = rel or {"2026-01": release()}
    latest = max(rel)
    old = [cpi_row(f"2025-{m:02d}", 200.0, sector=s) for m in range(1, 13) for s in ("Rural", "Urban", "Combined")]
    return {"cpi": old, "cpi2024": {"releases": rel, "latest": latest, "series": rel[latest]["series"],
                                    "linking": {s: linking for s in ("Rural", "Urban", "Combined")}}}


def test_cpi2024_checks_pass_on_a_good_release():
    for check in (prices2024.check_releases_read, prices2024.check_headline_agrees, prices2024.check_inflation,
                  prices2024.check_combined, prices2024.check_revisions, prices2024.check_linking_factor,
                  prices2024.check_pdf):
        assert failures_of(check, cpi2024_ds()) == [], check.__name__
    assert failures_of(prices2024.check_cpi2024, {"cpi2024": {"releases": {}}}) == ["no releases"]


def broken(change) -> dict:
    r = release()
    change(r)
    return {"2026-01": r}


@pytest.mark.parametrize("check, change, message", [
    (prices2024.check_releases_read, lambda r: r["groups"].pop(), "read 12 divisions, 42 groups, 36 states"),
    (prices2024.check_releases_read, lambda r: r["problems"].append("2026-01: no states table found"), "no states table"),
    (prices2024.check_headline_agrees, lambda r: r["headline"].update(combined=2.1), "inflation (rural, urban, combined) differs"),
    (prices2024.check_inflation, lambda r: r["series"][-1]["values"].__setitem__(5, 2.1), "2026-01 combined: index 102.0 vs 100.0"),
    (prices2024.check_combined, lambda r: r["states"][0]["values"].__setitem__(2, 103.0), "State 0: combined 103.0 outside"),
])
def test_cpi2024_checks_fail_on_a_bad_release(check, change, message):
    fails = failures_of(check, cpi2024_ds(broken(change)))
    assert any(message in f for f in fails), fails


def test_cpi2024_a_backtick_is_allowed():
    report = run_check(prices2024.check_releases_read, cpi2024_ds(broken(lambda r: r["problems"].append("2026-01: '109.`39'"))))
    assert report.failures == 0 and report.sections[0].allowed[0]["cases"] == 1


def test_cpi2024_final_figures_must_not_change():
    earlier, later = release(), release()
    later["series"][0]["values"] = [100.5, 100.0, 100.0, None, None, None]  # January 2025, final in every release
    fails = failures_of(prices2024.check_revisions, cpi2024_ds({"2025-12": earlier, "2026-01": later}))
    assert fails and fails[0].startswith("Final figure changed: 2025-01")


def test_cpi2024_linking_factor():
    assert len(failures_of(prices2024.check_linking_factor, cpi2024_ds(linking=0.6))) == 3  # 100 / 200 = 0.5
    ds = cpi2024_ds()
    ds["cpi"] = ds["cpi"][3:]  # January 2025 missing from the old series
    assert all("cannot check" in f for f in failures_of(prices2024.check_linking_factor, ds))


def test_cpi2024_release_page_matches_its_pdf(monkeypatch):
    r = release()
    r["pdf"] = "sources/raw/cpi2024/2026-01.pdf"
    page = [f"{v:.2f}" for rows in (r["divisions"], r["groups"], r["states"]) for x in rows for v in x["values"]]
    page += [f"{v:.2f}" for x in r["series"] for v in x["values"] if v is not None]
    monkeypatch.setattr(prices2024, "pdf_numbers", lambda path: page)
    assert failures_of(prices2024.check_pdf, cpi2024_ds({"2026-01": r})) == []
    monkeypatch.setattr(prices2024, "pdf_numbers", lambda path: [x for x in page if x != "102.00"])
    fails = failures_of(prices2024.check_pdf, cpi2024_ds({"2026-01": r}))
    assert fails and "not found in its PDF: ['102.00']" in fails[0]

"""The checks' rules test_checks.py leaves out: allowed exceptions and notes (which must not fail), the failures of
each rule not yet exercised, and checks.main, which runs every check and writes the report. Uses the hand-made
datasets of test_checks.py."""

import inspect
import json

from conftest import failures_of, run_check
from test_checks import cpi2024_ds, hces_row, plfs_ds, rate, release, shares

from jobs_prices_pipeline import checks
from jobs_prices_pipeline.checks import jobs, prices, prices2024, spending, values


def allowed_of(check, ds) -> dict[str, int]:
    """reason -> number of cases allowed under it."""
    return {a["reason"]: a["cases"] for s in run_check(check, ds).sections for a in s.allowed}


def notes_of(check, ds) -> list[str]:
    return [n for s in run_check(check, ds).sections for n in s.notes]


# ---- every check runs --------------------------------------------------------------------------------

def test_every_check_function_is_run():
    """A check_* function that checks.main never calls would pass silently."""
    run = set(checks.CHECKS) | {prices2024.check_releases_read, prices2024.check_headline_agrees,
                                prices2024.check_inflation, prices2024.check_combined, prices2024.check_revisions,
                                prices2024.check_linking_factor, prices2024.check_pdf}
    for module in (values, jobs, prices, prices2024, spending, checks.states):
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("check_") and fn.__module__ == module.__name__:
                assert fn in run, f"{module.__name__}.{name} is not run"
    # check_cpi2024 runs the seven above
    assert len(run_check(prices2024.check_cpi2024, cpi2024_ds()).sections) == 7


def test_main_writes_the_report_and_fails_on_any_failure(data_dir, monkeypatch):
    def ok(ds, report):
        report.add("fine", 1, [])

    def bad(ds, report):
        report.add("broken", 1, ["something is wrong"])

    monkeypatch.setattr(checks, "CHECKS", (ok,))
    assert checks.main({}) == 0
    summary = json.loads((data_dir / "validation_summary.json").read_text())
    # the stubbed checks, then the text check on the data folder that main always runs
    assert summary["result"] == "PASSED" and [s["title"] for s in summary["sections"]][0] == "fine"
    assert (data_dir / "validation_report.md").exists()

    monkeypatch.setattr(checks, "CHECKS", (ok, bad))
    assert checks.main({}) == 1
    summary = json.loads((data_dir / "validation_summary.json").read_text())
    assert summary["result"] == "FAILED" and summary["failures"] == 1


# ---- source values ---------------------------------------------------------------------------------

def test_source_unlabelled_rows_are_allowed_and_not_compiled_indices_skipped():
    ds = {"source_problems": [], "cpi": [], "hces": [],
          "plfs": {"rates": [], "distribution": [], "conditions": [], "earnings": [], "unlabelled": ["2024 Goa: 3 values"]},
          "cpialrl": [{"month": "2025-06", "state": "Goa", "index_al": None, "index_al_as_printed": "0.00",
                       "not_compiled_al": True}]}
    assert failures_of(values.check_source, ds) == []
    assert allowed_of(values.check_source, ds) == {values.UNLABELLED: 1}  # the 0.00 index is not a bad value


def test_source_rows_kept_after_mospi_withdrew_them_are_listed():
    ds = {"source_problems": [], "cpi": [], "hces": [], "cpialrl": [],
          "plfs": {"rates": [], "distribution": [], "conditions": [], "earnings": [], "unlabelled": [],
                   "kept": ["plfs/monthly/ind01: 27 rows from sources/snapshots/x/plfs/monthly/ind01.json"]}}
    assert failures_of(values.check_source, ds) == []
    assert allowed_of(values.check_source, ds) == {values.WITHDRAWN_KEPT: 1}

# ---- jobs ------------------------------------------------------------------------------------------

def test_rural_plus_urban_lies_between_rural_and_urban():
    def rows(total):
        return [rate(sector="rural", lfpr=40.0, wpr=38.0), rate(sector="urban", lfpr=60.0, wpr=57.0),
                rate(sector="rural + urban", lfpr=total, wpr=total * 0.95)]

    assert failures_of(jobs.check_brackets, plfs_ds(rows(50.0))) == []
    fails = failures_of(jobs.check_brackets, plfs_ds(rows(65.0)))
    assert any("sector rural + urban 65.0 outside rural 40.0 and urban 60.0" in f for f in fails), fails


def test_annual_job_conditions_between_men_and_women():
    def rows(person):
        base = {"frequency": "annual", "year": "2023-24", "period": "", "state": "Goa", "sector": "rural",
                "condition": "no written contract"}
        return [{**base, "gender": g, "value": v} for g, v in (("person", person), ("male", 50.0), ("female", 60.0))]

    assert failures_of(jobs.check_brackets, plfs_ds(conditions=rows(55.0))) == []
    assert failures_of(jobs.check_brackets, plfs_ds(conditions=rows(70.0)))


def test_distribution_exceptions_are_allowed_not_failed():
    short = {"1. own account": 30.0, "2. helper": 10.0, "3. all self-employed": 40.0, "4. regular": 20.0, "5. casual": 20.0}
    cases = {
        jobs.ALL_INDIA_STATUS: shares(short, breakdown="broad_status_employment", status="PS+SS", state="All India"),
        jobs.CWS_STATUS_2025: [{**r, "year": "2025"} for r in shares(short, breakdown="broad_status_employment")],
        jobs.NO_SAMPLE: [{**r, "sector": "rural"} for r in shares({"Agriculture": 0.0, "Industry": 0.0}, state="Chandigarh")],
    }
    for reason, rows in cases.items():
        ds = plfs_ds(distribution=rows)
        assert failures_of(jobs.check_distribution, ds) == [], reason
        assert reason in allowed_of(jobs.check_distribution, ds)
    # the same shares for a state in usual status are a failure
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=shares(short, breakdown="broad_status_employment",
                                                                             status="PS+SS")))


def test_distribution_with_no_figures_fails_and_a_bad_value_is_allowed():
    nothing = shares({"Agriculture": 0.0, "Industry": 0.0, "Services": 0.0})
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=nothing)) == [
        "annual broad_industry_work: 2024, Bihar, rural, male, CWS: no figures"]
    rows = shares({"Agriculture": 40.0, "Industry": 25.0, "Services": None})
    rows[-1]["value_as_printed"] = "3S.0"  # the figure that would make 100% cannot be read
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=rows)) == []
    assert values.BAD_VALUE in allowed_of(jobs.check_distribution, plfs_ds(distribution=rows))


def test_distribution_short_of_a_category_mospi_left_out_is_allowed():
    full = shares({"Agriculture": 40.0, "Industry": 25.0, "Services": 35.0}, state="Assam")
    gap = shares({"Agriculture": 40.0, "Services": 35.0})  # no Industry figure for Bihar
    ds = plfs_ds(distribution=full + gap)
    assert failures_of(jobs.check_distribution, ds) == []
    assert allowed_of(jobs.check_distribution, ds) == {jobs.MISSING_CATEGORY: 1}
    # more than 100% is not explained by a missing category
    over = shares({"Agriculture": 70.0, "Services": 35.0})
    assert failures_of(jobs.check_distribution, plfs_ds(distribution=full + over))


def test_source_rows_with_two_breakdowns_are_listed():
    ds = {"source_problems": [], "cpi": [], "hces": [], "cpialrl": [],
          "plfs": {"rates": [], "distribution": [], "conditions": [], "earnings": [], "unlabelled": [],
                   "crossed": ["plfs/annual/ind04: 2025, All India 4.regular wage/salary × 10-33 (manufacturing)"]}}
    assert failures_of(values.check_source, ds) == []
    assert allowed_of(values.check_source, ds) == {values.CROSSED: 1}

# ---- prices ----------------------------------------------------------------------------------------

def test_cpialrl_rural_labourers_inflation_and_not_compiled_note():
    def row(month, index, inflation, **kw):
        return {"month": month, "indicator": "General Index", "base_year": "2019", "state": "Bihar",
                "index_rl": index, "index_rl_as_printed": str(index), "inflation_rl": inflation, **kw}

    ok = [row("2024-06", 200.0, None), row("2025-06", 210.0, 5.0)]
    assert failures_of(prices.check_cpialrl, {"cpialrl": ok}) == []
    fails = failures_of(prices.check_cpialrl, {"cpialrl": [row("2024-06", 200.0, None), row("2025-06", 210.0, 6.0)]})
    assert len(fails) == 1 and "RL" in fails[0] and "published 6.0%" in fails[0]
    notes = notes_of(prices.check_cpialrl, {"cpialrl": ok + [row("2025-07", None, None, not_compiled_rl=True)]})
    assert any("treated as not compiled: Bihar (RL, base 2019)" in n for n in notes)


# ---- household spending ----------------------------------------------------------------------------

def rupees(food, nonfood, items_food, items_nonfood, average=None, **kw):
    rows = [hces_row(spending.CATEGORY_VALUES, v, item_category=c, **kw)
            for c, v in (("Food Total", food), ("Non-Food Total", nonfood), ("Cereal", items_food),
                         ("Conveyance", items_nonfood))]
    if average is not None:
        rows.append(hces_row(spending.MPCE, average, **kw))
    return rows


def test_hces_rupee_categories_add_up_to_the_average():
    assert failures_of(spending.check_hces, {"hces": rupees(2000.0, 3000.0, 2000.0, 3000.0, 5000.0)}) == []
    assert failures_of(spending.check_hces, {"hces": rupees(2000.0, 3000.0, 2000.0, 2500.0, 5000.0)}) == [
        "HCES 2023-24, Goa, Rural, Without Imputation ₹: non-food items add up to 2500.00, non-food total 3000.0"]
    assert failures_of(spending.check_hces, {"hces": rupees(2000.0, 3000.0, 2000.0, 3000.0, 5500.0)}) == [
        "HCES 2023-24, Goa, Rural, Without Imputation ₹: food + non-food = 5000.00, expected 5500.0"]


def test_hces_missing_total_fails_and_left_out_cells_are_allowed():
    rows = [r for r in rupees(2000.0, 3000.0, 2000.0, 3000.0) if r["item_category"] != "Non-Food Total"]
    assert failures_of(spending.check_hces, {"hces": rows}) == [
        "HCES 2023-24, Goa, Rural, Without Imputation ₹: food or non-food total missing"]
    # categories filed under the wrong state, left out by the reader: allowed, not added up
    mismatch = rupees(9000.0, 3000.0, 2000.0, 3000.0, 5000.0, left_out="adds up to ₹12,000")
    mismatch[-1]["left_out"] = ""  # the average itself is shown
    assert failures_of(spending.check_hces, {"hces": mismatch}) == []
    assert allowed_of(spending.check_hces, {"hces": mismatch}) == {spending.HCES_MISMATCH: 1}


def test_hces_all_class_equals_the_average():
    classes = [hces_row(spending.MPCE + " Over 12 Fractile Classes", 1000.0, mpce_fractile_classes=c)
               for c in ("0-5", "5-10", "10-20", "20-30", "30-40", "40-50", "50-60", "60-70", "70-80", "80-90",
                         "90-95", "95-100")]
    rows = [hces_row(spending.MPCE, 1000.0), *classes]
    all_class = hces_row(spending.MPCE + " Over 12 Fractile Classes", 1000.0, mpce_fractile_classes="All")
    assert failures_of(spending.check_hces, {"hces": rows + [all_class]}) == []
    all_class["value"] = 1100.0
    assert failures_of(spending.check_hces, {"hces": rows + [all_class]}) == [
        "HCES 2023-24, Goa, Rural, Without Imputation: 'All' spending class ₹1,100 ≠ average ₹1,000"]
    # a class missing: not checked, a note
    assert failures_of(spending.check_hces, {"hces": rows[:-1]}) == []
    assert any("not checked" in n for n in notes_of(spending.check_hces, {"hces": rows[:-1]}))


def test_hces_overall_needs_the_data_service_average_for_each_table_a2_row():
    pop = [{"year": "2023-24", "state": st, "sector": s, "persons_00": 100, "mpce_a2": 1000.0}
           for st in ("Goa", "All India") for s in ("Rural", "Urban")]
    api = [hces_row(spending.MPCE, 1000.0, state=st, sector=s) for st in ("Goa", "All India") for s in ("Rural", "Urban")]
    ds = {"hces_population": pop, "hces": api, "hces_overall": []}
    assert failures_of(spending.check_hces_overall, ds) == []
    assert failures_of(spending.check_hces_overall, {**ds, "hces": api[:-1]}) == [
        "Table A2 2023-24 All India Urban: no matching average in MoSPI's data service"]


# ---- consumer prices, base 2024 --------------------------------------------------------------------

def test_cpi2024_all_seven_checks_pass_on_a_good_release():
    report = run_check(prices2024.check_cpi2024, cpi2024_ds())
    assert report.failures == 0 and report.checks > 0


def test_cpi2024_a_release_with_no_all_india_series_fails():
    r = release()
    r["series"] = []
    fails = failures_of(prices2024.check_releases_read, cpi2024_ds({"2026-01": r}))
    assert fails == ["2026-01: no All-India series"]


def test_cpi2024_inflation_needs_two_places_to_compare():
    r = release()
    r["headline"] = {}
    r["summary"] = {}
    r["divisions"] = [d for d in r["divisions"] if d["code"] != "00"]
    assert failures_of(prices2024.check_headline_agrees, cpi2024_ds({"2026-01": r})) == [
        "2026-01: inflation found in only ['Annexure IV']"]


def test_cpi2024_a_revised_provisional_month_is_a_note():
    earlier, later = release(), release()
    earlier["series"][-1]["values"] = [101.9, 102.0, 102.0, 1.9, 2.0, 2.0]  # January 2026, provisional in its own release
    ds = cpi2024_ds({"2026-01": earlier, "2026-02": later})
    assert failures_of(prices2024.check_revisions, ds) == []
    assert any(n.startswith("Provisional figure revised: 2026-01") for n in notes_of(prices2024.check_revisions, ds))


def test_cpi2024_a_release_without_a_pdf_is_a_note():
    assert failures_of(prices2024.check_pdf, cpi2024_ds()) == []
    assert notes_of(prices2024.check_pdf, cpi2024_ds()) == ["2026-01: no PDF attached to the release; page only"]

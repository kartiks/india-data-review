"""Every test writes its outputs under its own tmp_path, never to the committed jobs-prices/data/ (whose
validation_summary.json gates the site build)."""

import pytest
from pipeline_common.report import Report

from jobs_prices_pipeline import build, checks


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    out = tmp_path / "data"
    monkeypatch.setattr(build, "DATA", out)
    monkeypatch.setattr(checks, "DATA", out)
    return out


def run_check(check, ds: dict) -> Report:
    """One check function run on its own report."""
    report = Report("test")
    check(ds, report)
    return report


def failures_of(check, ds: dict) -> list[str]:
    """The failures one check function reports on ds."""
    return [f for s in run_check(check, ds).sections for f in s.failures]

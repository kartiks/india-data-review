"""Every test writes its outputs under its own tmp_path, never to the committed jobs-prices/data/ (whose
validation_summary.json gates the site build)."""

import pytest

from jobs_prices_pipeline import build, checks


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    out = tmp_path / "data"
    monkeypatch.setattr(build, "DATA", out)
    monkeypatch.setattr(checks, "DATA", out)
    return out

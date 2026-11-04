"""Shared fixtures. The tests never write to budget/data/ (the committed data and the report the site's build
gate reads): a test that builds the dataset writes it to a temporary folder instead."""

import hashlib
import importlib
import pkgutil
from pathlib import Path

import pytest

import budget_pipeline

REAL_DATA = Path(__file__).resolve().parents[2] / "data"


def _pipeline_modules() -> list:
    names = [m.name for m in pkgutil.walk_packages(budget_pipeline.__path__, "budget_pipeline.")
             if not m.name.endswith("__main__")]
    return [budget_pipeline, *(importlib.import_module(n) for n in names)]


def _fingerprint(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}


@pytest.fixture(scope="session", autouse=True)
def committed_data_untouched():
    """Fail the run if any test changed a file in budget/data/."""
    before = _fingerprint(REAL_DATA)
    yield
    assert _fingerprint(REAL_DATA) == before, "a test rewrote files in budget/data/"


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    """A temporary data/ folder that the pipeline writes to and reads back from instead of budget/data/:
    every pipeline module's DATA path points to it while the requesting test module runs."""
    out = tmp_path_factory.mktemp("data")
    with pytest.MonkeyPatch.context() as mp:
        for module in _pipeline_modules():
            if getattr(module, "DATA", None) == REAL_DATA:
                mp.setattr(module, "DATA", out)
        yield out

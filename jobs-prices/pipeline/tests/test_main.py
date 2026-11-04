"""Command-line options of `python -m jobs_prices_pipeline`, with fetch, build and checks replaced by stubs."""

from datetime import date

import pytest

from jobs_prices_pipeline import __main__ as cli
from jobs_prices_pipeline.sources import cpi2024_overdue

LATEST = "2026-09"  # released about 2026-10-12


@pytest.fixture
def calls(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.fetch, "main", lambda **kw: calls.append(("fetch", kw)))
    monkeypatch.setattr(cli.build, "main", lambda: calls.append(("build",)) or {"cpi2024": {"latest": LATEST}})
    monkeypatch.setattr(cli.checks, "main", lambda ds: calls.append(("checks",)) or 0)
    return calls


def run(monkeypatch, *args, today=date(2026, 11, 3)):
    monkeypatch.setattr(cli.sys, "argv", ["jobs_prices_pipeline", *args])
    return cli.main(today)


@pytest.mark.parametrize("args", [["--refrsh"], ["--refresh-nas"], ["--fetch", "extra"]])
def test_unknown_option_builds_nothing(monkeypatch, capsys, calls, args):
    assert run(monkeypatch, *args) == 2
    assert calls == []
    assert "unknown option" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help(monkeypatch, capsys, calls, flag):
    assert run(monkeypatch, flag) == 0
    assert calls == []
    assert "--refresh-api" in capsys.readouterr().out


@pytest.mark.parametrize("args, fetched", [
    ([], None),
    (["--fetch"], {"force": False, "force_api": False}),
    (["--refresh"], {"force": True, "force_api": False}),
    (["--refresh-api"], {"force": False, "force_api": True}),
])
def test_known_options(monkeypatch, calls, args, fetched):
    assert run(monkeypatch, *args) == 0
    assert calls == ([("fetch", fetched)] if fetched else []) + [("build",), ("checks",)]


def test_cpi2024_overdue():
    assert cpi2024_overdue("2026-09", date(2026, 11, 26)) is None  # 45 days after 2026-10-12
    assert "2026-09" in cpi2024_overdue("2026-09", date(2026, 11, 27))
    assert cpi2024_overdue("2026-12", date(2027, 2, 26)) is None  # December's release: January 12
    assert cpi2024_overdue("2026-12", date(2027, 2, 27))
    assert cpi2024_overdue(None, date(2026, 1, 1))


@pytest.mark.parametrize("args, code", [([], 0), (["--fetch"], 0), (["--refresh"], 10), (["--refresh-api"], 10)])
def test_out_of_date_cpi2024_fails_only_the_refresh(monkeypatch, capsys, calls, args, code):
    # The offline build (and scripts/ci.sh) must keep passing on committed data however much time has passed.
    assert run(monkeypatch, *args, today=date(2027, 3, 1)) == code
    assert calls[-2:] == [("build",), ("checks",)]  # the data is built and checked either way
    assert ("out of date" in capsys.readouterr().err) == bool(code)

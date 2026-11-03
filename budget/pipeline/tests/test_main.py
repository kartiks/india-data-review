"""Command-line options of `python -m budget_pipeline`, with the download, build and checks replaced by stubs."""

import pytest

from budget_pipeline import __main__ as cli


@pytest.fixture
def calls(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.fetch, "main", lambda **kw: calls.append(("fetch", kw)))
    monkeypatch.setattr(cli.reference, "fetch", lambda: calls.append(("reference",)))
    monkeypatch.setattr(cli.build, "main", lambda: calls.append(("build",)))
    monkeypatch.setattr(cli.datasets, "build_all", lambda: calls.append(("datasets",)) or {})
    monkeypatch.setattr(cli.checks, "main", lambda ds: calls.append(("checks",)) or 0)
    return calls


def run(monkeypatch, *args):
    monkeypatch.setattr(cli.sys, "argv", ["budget_pipeline", *args])
    return cli.main()


BUILD = [("build",), ("datasets",), ("checks",)]


@pytest.mark.parametrize("args", [["--force"], ["--refresh-nas"], ["--fetch", "extra"]])
def test_unknown_option_builds_nothing(monkeypatch, capsys, calls, args):
    assert run(monkeypatch, *args) == 2
    assert calls == []
    assert "unknown option" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help(monkeypatch, capsys, calls, flag):
    assert run(monkeypatch, flag) == 0
    assert calls == []
    assert "--refresh" in capsys.readouterr().out


@pytest.mark.parametrize("args, force", [([], None), (["--fetch"], False), (["--refresh"], True)])
def test_known_options(monkeypatch, calls, args, force):
    assert run(monkeypatch, *args) == 0
    fetched = [("fetch", {"force": force}), ("reference",)] if force is not None else []
    assert calls == fetched + BUILD

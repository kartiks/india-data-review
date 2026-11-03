"""Command-line options of `python -m gdp_pipeline`, with fetch, build and checks replaced by stubs."""

import pytest

from gdp_pipeline import __main__ as cli


@pytest.fixture
def calls(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.fetch, "main", lambda **kw: calls.append(("fetch", kw)))
    monkeypatch.setattr(cli.build, "main", lambda: calls.append(("build",)) or {})
    monkeypatch.setattr(cli.checks, "main", lambda ds: calls.append(("checks",)) or 0)
    return calls


def run(monkeypatch, *args):
    monkeypatch.setattr(cli.sys, "argv", ["gdp_pipeline", *args])
    return cli.main()


@pytest.mark.parametrize("args", [["--refrsh"], ["--refresh-api"], ["--fetch", "extra"]])
def test_unknown_option_builds_nothing(monkeypatch, capsys, calls, args):
    assert run(monkeypatch, *args) == 2
    assert calls == []
    assert "unknown option" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help(monkeypatch, capsys, calls, flag):
    assert run(monkeypatch, flag) == 0
    assert calls == []
    assert "--refresh-nas" in capsys.readouterr().out


@pytest.mark.parametrize("args, fetched", [
    ([], None),
    (["--fetch"], {"force": False, "force_nas": False}),
    (["--refresh"], {"force": True, "force_nas": False}),
    (["--refresh-nas"], {"force": False, "force_nas": True}),
])
def test_known_options(monkeypatch, calls, args, fetched):
    assert run(monkeypatch, *args) == 0
    assert calls == ([("fetch", fetched)] if fetched else []) + [("build",), ("checks",)]

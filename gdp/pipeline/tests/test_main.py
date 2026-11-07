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
    try:
        return cli.main(list(args))
    except SystemExit as e:  # argparse: --help (0), a mistake (2)
        return e.code


@pytest.mark.parametrize("args, message", [
    (["--refrsh"], "unrecognized arguments: --refrsh"),
    (["--fetch", "extra"], "unrecognized arguments: extra"),
    (["--refresh", "--refresh-api"], "not allowed with argument --refresh"),
    (["--refresh-nas"], "--refresh-nas was renamed: use --refresh-api"),
    (["--force-nas"], "--force-nas was renamed: use --refresh-api"),
])
def test_unknown_option_builds_nothing(monkeypatch, capsys, calls, args, message):
    assert run(monkeypatch, *args) == 2
    assert calls == []
    assert message in capsys.readouterr().err


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

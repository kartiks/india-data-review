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
    try:
        return cli.main(list(args))
    except SystemExit as e:  # argparse: --help (0), a mistake (2)
        return e.code


BUILD = [("build",), ("datasets",), ("checks",)]


@pytest.mark.parametrize("args, message", [
    (["--refrsh"], "unrecognized arguments: --refrsh"),
    (["--refresh-api"], "unrecognized arguments: --refresh-api"),  # the budget has no sources revised in place
    (["--fetch", "extra"], "unrecognized arguments: extra"),
    (["--fetch", "--refresh"], "not allowed with argument --fetch"),
    (["--force"], "--force was renamed: use --refresh"),
])
def test_unknown_option_builds_nothing(monkeypatch, capsys, calls, args, message):
    assert run(monkeypatch, *args) == 2
    assert calls == []
    assert message in capsys.readouterr().err


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


def test_a_budget_not_downloaded_stops_with_what_is_missing(monkeypatch, tmp_path, capsys):
    """Raising LATEST_BUDGET before the new budget's documents are downloaded names them, instead of failing deep in
    the parser (it used to stop with KeyError: 'summary')."""
    import json

    from budget_pipeline import build, sources

    monkeypatch.setattr(sources, "BUDGETS", [*sources.BUDGETS, sources.LATEST_BUDGET + 1])
    nxt = sources.fy(sources.LATEST_BUDGET + 1)
    manifest = json.loads(build.MANIFEST.read_text())
    assert sources.missing_documents(manifest) == {nxt: ["summary", "receipts", "ministries", "css", "central_sector"]}
    manifest[nxt] = {"summary": {"files": {"pdf": {}}}}  # only the headline table found so far
    assert sources.missing_documents(manifest) == {nxt: ["receipts", "ministries", "css", "central_sector"]}

    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(build, "MANIFEST", tmp_path / "manifest.json")
    with pytest.raises(build.MissingDocuments, match=f"not downloaded \\({nxt}: receipts, ministries, css, central_sector\\)"):
        build.parse_all()

    def missing():
        raise build.MissingDocuments("Budget documents not downloaded (…)")

    monkeypatch.setattr(cli.build, "main", missing)
    assert run(monkeypatch) == 1
    assert capsys.readouterr().err == "FAIL: Budget documents not downloaded (…)\n"

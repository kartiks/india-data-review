"""pipeline_common.log: plain lines, info on stdout, warnings and errors on stderr; and the shared options."""

import logging

import pytest

from pipeline_common import cli
from pipeline_common import log as pipeline_log
from pipeline_common.due import DUE, Findings


def test_plain_lines_on_stdout_and_stderr(capsys):
    pipeline_log.setup("some_pipeline.sub")
    logging.getLogger("some_pipeline.fetch").info("nas/ind01: 10 rows")
    logging.getLogger("some_pipeline.fetch").warning("nas/ind02: NO ROWS")
    logging.getLogger("__main__").error("FAIL: out of date: x")
    logging.getLogger("pipeline_common.download").debug("not shown")
    assert capsys.readouterr() == ("nas/ind01: 10 rows\n", "nas/ind02: NO ROWS\nFAIL: out of date: x\n")


def test_setup_twice_adds_one_handler(capsys):
    pipeline_log.setup()
    pipeline_log.setup()
    assert sum(isinstance(h, pipeline_log.PlainHandler) for h in logging.getLogger().handlers) == 1
    logging.getLogger("pipeline_common").info("once")
    assert capsys.readouterr().out == "once\n"


def test_other_libraries_keep_to_warnings(capsys):
    pipeline_log.setup()
    logging.getLogger("pdfminer.pdfpage").info("noise")
    logging.getLogger("pdfminer.pdfpage").warning("CropBox missing")
    assert capsys.readouterr() == ("", "CropBox missing\n")


def test_release_due_lines_are_unchanged(capsys):
    """The weekly refresh (scripts/refresh/check-due.sh, package.sh) reads these lines as they are."""
    pipeline_log.setup()
    assert Findings(due=["a: b. c"], ok=["d"], warnings=["e"]).finish() == DUE
    assert capsys.readouterr() == ("ok: d\nDUE: a: b. c\n", "WARNING: e\n")


@pytest.mark.parametrize("argv, expected", [
    ([], (False, False, False)),
    (["--fetch"], (True, False, False)),
    (["--refresh"], (False, True, False)),
    (["--refresh-api"], (False, False, True)),
])
def test_shared_options(argv, expected):
    a = cli.parser("doc", refresh_api="api").parse_args(argv)
    assert (a.fetch, a.refresh, a.refresh_api) == expected


@pytest.mark.parametrize("argv, message", [
    (["--refresh-nas"], "--refresh-nas was renamed: use --refresh-api"),
    (["--force"], "--force was renamed: use --refresh"),
    (["--force-api"], "--force-api was renamed: use --refresh-api"),
    (["--refr"], "unrecognized arguments: --refr"),  # no abbreviations
    (["--fetch", "--refresh"], "not allowed with argument --fetch"),
    (["--fetch", "extra"], "unrecognized arguments: extra"),
])
def test_old_and_unknown_options_are_refused(argv, message, capsys):
    with pytest.raises(SystemExit) as e:
        cli.parser("doc", refresh_api="api").parse_args(argv)
    assert e.value.code == 2 and message in capsys.readouterr().err


def test_an_area_without_refresh_api(capsys):
    p = cli.parser("doc")
    assert p.parse_args([]).refresh_api is False
    with pytest.raises(SystemExit):
        p.parse_args(["--refresh-nas"])  # not "use --refresh-api": this area has none
    assert "unrecognized arguments: --refresh-nas" in capsys.readouterr().err


def test_fetch_command_options(capsys):
    p = cli.parser("doc", fetch=False, refresh_api="api")
    assert p.parse_args(["--refresh"]).refresh
    with pytest.raises(SystemExit):
        p.parse_args(["--fetch"])
    with pytest.raises(SystemExit) as e:
        p.parse_args(["--help"])
    assert e.value.code == 0 and "--refresh-api" in capsys.readouterr().out

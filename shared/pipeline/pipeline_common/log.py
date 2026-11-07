"""Logging for every pipeline command: plain lines, as print() would write them.

Each module logs through its own logger (`log = logging.getLogger(__name__)`), and each command calls setup() once
before it does anything, so that output looks the same in every area:

- info and below: the message alone, on stdout (progress, "ok  <checks>" lines, "DUE: ..." lines);
- warnings and errors: the message alone, on stderr. The message carries its own prefix where one is needed
  ("FAIL: ...", "WARNING: ..."): the weekly refresh's scripts and the tests read some of these lines as they are.

Only the pipelines' own loggers (`__main__`, `pipeline_common` and the packages passed to setup) log at info level;
other libraries' loggers keep Python's default (warnings and above), as before.
"""

import logging
import sys

PIPELINE_LOGGERS = ("__main__", "pipeline_common")


class PlainHandler(logging.Handler):
    """Writes each record's message to sys.stdout (below WARNING) or sys.stderr, looked up at each line (so pytest's
    capsys, which replaces them, sees the output), and flushes it at once (the weekly refresh tees it to a log)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            stream = sys.stderr if record.levelno >= logging.WARNING else sys.stdout
            stream.write(self.format(record) + "\n")
            stream.flush()
        except Exception:  # noqa: BLE001 - logging's own convention: report, never raise
            self.handleError(record)


def setup(*packages: str) -> None:
    """Send the pipelines' log records to stdout and stderr as plain lines. packages: the area's package, whose
    modules log at info level: pass the calling module's __package__ (e.g. "gdp_pipeline" or
    "budget_pipeline.schemes": the top-level package is used). Calling it again adds no second handler."""
    root = logging.getLogger()
    if not any(isinstance(h, PlainHandler) for h in root.handlers):
        handler = PlainHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(handler)
    for name in (*PIPELINE_LOGGERS, *(p.split(".")[0] for p in packages if p)):
        logging.getLogger(name).setLevel(logging.INFO)

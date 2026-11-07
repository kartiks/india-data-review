"""Releases added by hand that are due: the output and exit code every area's `due` command shares.

Some sources are added by hand (a new Union Budget, an Economic Survey, an RBI policy statement, a year's population).
Each area's `python -m <area>_pipeline.due` works out, from dates and at most a cheap probe of the source's site,
which of them are probably out but not yet in the repository. The weekly refresh runs it after committing the data
it downloaded, and fails the run when something is due, so GitHub emails someone to add it.

Output, one line each: "DUE: <what>: <why>. <where to add it>" for each item due; "ok: ..." for each item checked
and not due; "WARNING: ..." (on stderr) when a probe could not tell, such as a network error. Exit code DUE (11) if
anything is due, else 0: a warning alone never fails the run.
"""

import sys
from dataclasses import dataclass, field

DUE = 11  # something is due (data-refresh.yml commits the data first, then fails the run with these lines)


@dataclass
class Findings:
    due: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def finish(self) -> int:
        """Print every line and return the exit code."""
        for line in self.ok:
            print(f"ok: {line}")
        for line in self.warnings:
            print(f"WARNING: {line}", file=sys.stderr)
        for line in self.due:
            print(f"DUE: {line}")
        return DUE if self.due else 0

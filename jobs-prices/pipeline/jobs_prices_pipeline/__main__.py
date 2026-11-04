"""Run the whole pipeline: (download) -> build datasets -> checks.

    uv run python -m jobs_prices_pipeline            # use files already in sources/
    uv run python -m jobs_prices_pipeline --fetch    # download anything missing
    uv run python -m jobs_prices_pipeline --refresh  # re-download everything (after a MoSPI release);
                                                     # changed files are kept in sources/snapshots/
    uv run python -m jobs_prices_pipeline --refresh-api  # re-download only MoSPI's API and the RBI handbook
                                                         # tables (what the weekly refresh runs)

Exits non-zero if any check fails, so it can gate a website build. When every check
passes but the base-2024 CPI releases, added by hand, are out of date
(sources.cpi2024_overdue), --refresh and --refresh-api exit with STALE (10) instead:
the weekly refresh still commits the other data, then fails the run so someone adds
the new month. The data written is the same either way.
"""

import sys
from datetime import date

from . import build, checks, fetch
from .sources import cpi2024_overdue

OPTIONS = {"--fetch", "--refresh", "--refresh-api"}
REFRESH = {"--refresh", "--refresh-api"}
STALE = 10  # every check passed, but the base-2024 CPI is out of date (data-refresh.yml commits, then fails)


def main(today: date | None = None) -> int:
    args = sys.argv[1:]
    if {"-h", "--help"} & set(args):
        print(__doc__)
        return 0
    if unknown := [a for a in args if a not in OPTIONS]:
        print(f"unknown option: {' '.join(unknown)} (options: {', '.join(sorted(OPTIONS))}; --help for more)", file=sys.stderr)
        return 2
    if OPTIONS & set(args):
        fetch.main(force="--refresh" in args, force_api="--refresh-api" in args)
    ds = build.main()
    code = checks.main(ds)
    if REFRESH & set(args) and (why := cpi2024_overdue(ds["cpi2024"]["latest"], today or date.today())):
        print(f"FAIL: out of date: {why}", file=sys.stderr)
        code = code or STALE
    return code


if __name__ == "__main__":
    sys.exit(main())

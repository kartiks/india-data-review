"""Run the whole pipeline: (download) -> build datasets -> checks.

    uv run python -m jobs_prices_pipeline                # use files already in sources/
    uv run python -m jobs_prices_pipeline --fetch        # download anything missing
    uv run python -m jobs_prices_pipeline --refresh      # re-download everything (after a MoSPI release);
                                                         # changed files are kept in sources/snapshots/
    uv run python -m jobs_prices_pipeline --refresh-api  # re-download only MoSPI's API and the RBI handbook
                                                         # tables (what the weekly refresh runs)

Exits non-zero if any check fails, so it can gate a website build. When every check
passes but the base-2024 CPI releases, added by hand, are out of date
(sources.cpi2024_overdue), --refresh and --refresh-api exit with STALE (10) instead:
the weekly refresh still commits the other data, then fails the run so someone adds
the new month. The data written is the same either way.
"""

import logging
import sys
from datetime import date

from pipeline_common import cli
from pipeline_common import log as pipeline_log

from . import build, checks, fetch
from .sources import cpi2024_overdue

STALE = 10  # every check passed, but the base-2024 CPI is out of date (data-refresh.yml commits, then fails)
REFRESH_API = ("download again only what is published as data and revised in place (MoSPI's API and the RBI "
               "handbook tables), and anything missing, then build (what the weekly refresh runs)")

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    pipeline_log.setup(__package__)
    args = cli.parser(__doc__, refresh_api=REFRESH_API).parse_args(argv)
    if args.fetch or args.refresh or args.refresh_api:
        fetch.main(force=args.refresh, force_api=args.refresh_api)
    ds = build.main()
    code = checks.main(ds)
    if (args.refresh or args.refresh_api) and (why := cpi2024_overdue(ds["cpi2024"]["latest"], today or date.today())):
        log.error(f"FAIL: out of date: {why}")
        code = code or STALE
    return code


if __name__ == "__main__":
    sys.exit(main())

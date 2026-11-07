"""Run the whole pipeline: (download) -> build datasets -> checks.

    uv run python -m gdp_pipeline                # use files already in sources/
    uv run python -m gdp_pipeline --fetch        # download anything missing
    uv run python -m gdp_pipeline --refresh      # re-download everything (after a MoSPI release);
                                                 # changed files are kept in sources/snapshots/
    uv run python -m gdp_pipeline --refresh-api  # re-download only MoSPI's national accounts API files
                                                 # (what the weekly refresh runs)

Exits non-zero if any check fails, so it can gate a website build.
"""

import sys

from pipeline_common import cli
from pipeline_common import log as pipeline_log

from . import build, checks, fetch

REFRESH_API = ("download again only MoSPI's national accounts API files, which are revised in place, and anything "
               "missing, then build (what the weekly refresh runs)")


def main(argv: list[str] | None = None) -> int:
    pipeline_log.setup(__package__)
    args = cli.parser(__doc__, refresh_api=REFRESH_API).parse_args(argv)
    if args.fetch or args.refresh or args.refresh_api:
        fetch.main(force=args.refresh, force_api=args.refresh_api)
    return checks.main(build.main())


if __name__ == "__main__":
    sys.exit(main())

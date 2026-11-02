"""Run the whole pipeline: (download) -> build datasets -> checks.

    uv run python -m jobs_prices_pipeline            # use files already in sources/
    uv run python -m jobs_prices_pipeline --fetch    # download anything missing
    uv run python -m jobs_prices_pipeline --refresh  # re-download everything (after a MoSPI release);
                                                     # changed files are kept in sources/snapshots/
    uv run python -m jobs_prices_pipeline --refresh-api  # re-download only MoSPI's API and the RBI handbook
                                                         # tables (what the weekly refresh runs)

Exits non-zero if any check fails, so it can gate a website build.
"""

import sys

from . import build, checks, fetch


def main() -> int:
    if {"--fetch", "--refresh", "--refresh-api"} & set(sys.argv):
        fetch.main(force="--refresh" in sys.argv, force_api="--refresh-api" in sys.argv)
    return checks.main(build.main())


if __name__ == "__main__":
    sys.exit(main())

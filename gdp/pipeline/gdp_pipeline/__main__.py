"""Run the whole pipeline: (download) -> build datasets -> checks.

    uv run python -m gdp_pipeline            # use files already in sources/
    uv run python -m gdp_pipeline --fetch    # download anything missing
    uv run python -m gdp_pipeline --refresh  # re-download everything (after a MoSPI release);
                                             # changed files are kept in sources/snapshots/
    uv run python -m gdp_pipeline --refresh-nas  # re-download only MoSPI's API files (the scheduled job)

Exits non-zero if any check fails, so it can gate a website build.
"""

import sys

from . import build, checks, fetch


def main() -> int:
    if {"--fetch", "--refresh", "--refresh-nas"} & set(sys.argv):
        fetch.main(force="--refresh" in sys.argv, force_nas="--refresh-nas" in sys.argv)
    return checks.main(build.main())


if __name__ == "__main__":
    sys.exit(main())

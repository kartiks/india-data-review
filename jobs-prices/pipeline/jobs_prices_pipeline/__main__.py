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

OPTIONS = {"--fetch", "--refresh", "--refresh-api"}


def main() -> int:
    args = sys.argv[1:]
    if {"-h", "--help"} & set(args):
        print(__doc__)
        return 0
    if unknown := [a for a in args if a not in OPTIONS]:
        print(f"unknown option: {' '.join(unknown)} (options: {', '.join(sorted(OPTIONS))}; --help for more)", file=sys.stderr)
        return 2
    if OPTIONS & set(args):
        fetch.main(force="--refresh" in args, force_api="--refresh-api" in args)
    return checks.main(build.main())


if __name__ == "__main__":
    sys.exit(main())

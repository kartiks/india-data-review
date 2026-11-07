"""Run the whole pipeline: (download) -> parse -> build datasets -> checks.

Builds data/fiscal.json (headline), taxes.json, ministries.json, schemes.json
and data/validation_report.md.

    uv run python -m budget_pipeline            # use files already in sources/
    uv run python -m budget_pipeline --fetch    # also download anything missing
    uv run python -m budget_pipeline --refresh  # re-download every budget file (after a new budget or a
                                                # corrected file); overwrites the files in sources/raw/

Both --fetch and --refresh also re-download the RBI reference tables (sources/reference/). The budget has no
sources revised in place, so it has no --refresh-api (pipeline_common.cli).
Exits non-zero if any check fails, so it can gate a website build.
"""

import logging
import sys

from pipeline_common import cli
from pipeline_common import log as pipeline_log

from . import build, checks, datasets, fetch, reference

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    pipeline_log.setup(__package__)
    args = cli.parser(__doc__).parse_args(argv)
    if args.fetch or args.refresh:
        fetch.main(force=args.refresh)
        reference.fetch()
    try:
        build.main()
    except build.MissingDocuments as exc:
        log.error(f"FAIL: {exc}")
        return 1
    return checks.main(datasets.build_all())


if __name__ == "__main__":
    sys.exit(main())

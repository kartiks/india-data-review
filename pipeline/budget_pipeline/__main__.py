"""Run the whole pipeline: (download) -> parse -> build datasets -> checks.

Builds data/fiscal.json (headline), taxes.json, ministries.json, schemes.json
and data/validation_report.md.

    uv run python -m budget_pipeline            # use files already in sources/
    uv run python -m budget_pipeline --fetch    # also download anything missing

Exits non-zero if any check fails, so it can gate a website build.
"""

import sys

from . import build, checks, datasets, fetch, reference


def main() -> int:
    if "--fetch" in sys.argv:
        fetch.main()
        reference.fetch()
    build.main()
    return checks.main(datasets.build_all())


if __name__ == "__main__":
    sys.exit(main())

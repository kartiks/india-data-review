"""Run the whole pipeline: (download) -> parse -> build datasets -> checks.

Builds data/fiscal.json (headline), taxes.json, ministries.json, schemes.json
and data/validation_report.md.

    uv run python -m budget_pipeline            # use files already in sources/
    uv run python -m budget_pipeline --fetch    # also download anything missing
    uv run python -m budget_pipeline --refresh  # re-download every budget file (after a new budget or a
                                                # corrected file); overwrites the files in sources/raw/

Both --fetch and --refresh also re-download the RBI reference tables (sources/reference/).
Exits non-zero if any check fails, so it can gate a website build.
"""

import sys

from . import build, checks, datasets, fetch, reference

OPTIONS = {"--fetch", "--refresh"}


def main() -> int:
    args = sys.argv[1:]
    if {"-h", "--help"} & set(args):
        print(__doc__)
        return 0
    if unknown := [a for a in args if a not in OPTIONS]:
        print(f"unknown option: {' '.join(unknown)} (options: {', '.join(sorted(OPTIONS))}; --help for more)", file=sys.stderr)
        return 2
    if OPTIONS & set(args):
        fetch.main(force="--refresh" in args)
        reference.fetch()
    build.main()
    return checks.main(datasets.build_all())


if __name__ == "__main__":
    sys.exit(main())

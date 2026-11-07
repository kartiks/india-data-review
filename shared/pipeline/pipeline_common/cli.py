"""The options every area's pipeline command takes, with the same names everywhere.

    python -m <area>_pipeline [--fetch | --refresh | --refresh-api]

    (none)         build data/ from the files already in sources/ and run every check; nothing is downloaded
    --fetch        first download every source that is missing
    --refresh      first download every source again
    --refresh-api  first download again only the sources published as data and revised in place (an API, or a
                   spreadsheet re-issued at the same address), and any source that is missing: what the weekly
                   refresh runs. Only areas with such sources have it (gdp, jobs-prices).

`python -m <area>_pipeline.fetch` only downloads: what is missing, or with --refresh or --refresh-api as above.
Options that were renamed are refused with their new name; any other unknown option is refused too.
"""

import argparse
import sys

# Options from before, and the option that replaced each.
RENAMED = {
    "--force": "--refresh",
    "--refresh-nas": "--refresh-api",
    "--force-nas": "--refresh-api",
    "--force-api": "--refresh-api",
}


class Parser(argparse.ArgumentParser):
    """argparse, refusing a renamed option with its new name (exit 2, as for any other mistake)."""

    def parse_args(self, args=None, namespace=None):
        args = sys.argv[1:] if args is None else list(args)
        options = {s for a in self._actions for s in a.option_strings}
        for a in args:
            new = RENAMED.get(a.split("=", 1)[0])
            if new in options:
                self.error(f"{a} was renamed: use {new}")
        return super().parse_args(args, namespace)


def parser(doc: str | None, *, fetch: bool = True, refresh_api: str | None = None) -> Parser:
    """A parser with the shared options; parse_args() as usual (--help prints doc and the options, and exits 0; a
    mistake exits 2). doc: the command's docstring. fetch: False for a fetch module's own command, which always
    downloads (so it has no --fetch). refresh_api: the help text of --refresh-api, in an area that has sources
    revised in place (None leaves the option out). The result always has .fetch, .refresh and .refresh_api."""
    p = Parser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    group = p.add_mutually_exclusive_group()
    if fetch:
        group.add_argument("--fetch", action="store_true", help="download every source that is missing, then build")
    group.add_argument("--refresh", action="store_true", help="download every source again"
                       + (", then build" if fetch else " (without it, only those that are missing)"))
    if refresh_api:
        group.add_argument("--refresh-api", action="store_true", help=refresh_api)
    p.set_defaults(fetch=False, refresh_api=False)
    return p

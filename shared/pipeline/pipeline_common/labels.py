"""Text that is new in an area's data/: what makes the weekly refresh open a pull request instead of pushing.

    uv run python -m pipeline_common.labels <old data dir> <new data dir>

The weekly refresh (.github/workflows/data-refresh.yml) pushes new figures straight to main, but new text (a state,
an item, a unit, a note, a source address) is something a person should look at first, so it goes to a pull
request. This compares every JSON and CSV file in two copies of a data/ folder and lists the text in the new copy
that the old copy does not have. Exit status: 0 if there is none, 1 if there is (listed on stdout as Markdown),
2 if a file cannot be read.

Every string is compared, and every JSON key and CSV header; `generated_at` is left out. So that new figures and
new periods do not count, each string is first reduced to a pattern: dates and times, SHA-256 hashes, month names,
quarters (Q1-Q4, H1-H2) and numbers (years, fiscal years such as 2025-26, months such as 2026-01, figures) all
become '#', and a run of them with only separators between ('Jan-Mar 2026', '2025-26') becomes one '#'. A string
whose pattern has nothing left but '#', spaces and punctuation (a figure, a year, 'Q2 2025-26', 'Jan 2026') is
not text. Anything else is text, and it is new if no string in the same file of the old copy has the same pattern:
'Q3 2025-26' is not new when 'Q2 2025-26' was there, and 'cpi/all_india/2027' is not new next to
'cpi/all_india/2026', but 'Ladakh' or a changed unit is.

validation_report.md and other files that are not JSON or CSV are not compared. The report is written by the
checks' code, which a refresh does not change; its lines repeat figures and labels from the data (already compared
here) and counts that change every time, so comparing it would only add noise. The figures it prints are reviewed
the usual way (README, "The weekly refresh").
"""

import csv
import json
import re
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

IGNORED_KEYS = {"generated_at"}  # its value is the build time
SUFFIXES = {".json", ".csv"}

_MONTHS = ("january|february|march|april|may|june|july|august|september|october|november|december"
           "|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec")
_PERIOD_PARTS = [
    # dates and times: 2026-11-06T09:30:00+00:00, 2026-11-06T093000Z (snapshot folders), 2026-11-06 09:30
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:?\d{2}(?::?\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?",
    r"\b[0-9a-f]{32,}\b",  # SHA-256 and other hashes
    rf"\b(?:{_MONTHS})\b\.?",
    r"\b[QH]\d\b",  # quarters and halves: Q2, H1
    # numbers, with their sign unless it follows a word: -0.4, −1, 1,00,000, 12.5, years, 2025-26, 2026-01, 1/2026
    r"(?:(?<![\w#])[-+−])?\d+(?:[.,:/-]\d+)*",
]
_PERIOD = re.compile("|".join(_PERIOD_PARTS), re.IGNORECASE)
_RUN = re.compile(r"#(?:[\s\-–—/,.:]*#)+")  # '#-# #' ('Jan-Mar 2026') is one '#'


def pattern(text: str) -> str:
    """The string with figures and periods each turned into '#': 'Q2 2025-26 estimate' -> '# estimate'."""
    return _RUN.sub("#", _PERIOD.sub("#", text)).strip()


def is_text(pat: str) -> bool:
    """Whether a pattern has anything but '#', spaces and punctuation in it (letters, symbols such as ₹)."""
    return any(c != "#" and not c.isspace() and not unicodedata.category(c).startswith("P") for c in pat)


def strings(obj, *, key: str | None = None) -> Iterator[str]:
    """Every key and string value in parsed JSON, depth first, leaving out the values of IGNORED_KEYS."""
    if key in IGNORED_KEYS:
        return
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from strings(v, key=str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def file_strings(path: Path) -> Iterator[str]:
    """Every string in a JSON file (keys and values) or a CSV file (header and cells)."""
    if path.suffix == ".json":
        with path.open(encoding="utf-8") as f:
            yield from strings(json.load(f))
        return
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, [])
        yield from header
        skip = {i for i, h in enumerate(header) if h in IGNORED_KEYS}
        for row in reader:
            yield from (cell for i, cell in enumerate(row) if i not in skip)


def text_patterns(path: Path) -> dict[str, str]:
    """{pattern: the first string seen with it} for every string in the file that is text."""
    out: dict[str, str] = {}
    seen: set[str] = set()
    for s in file_strings(path):
        if s in seen:
            continue
        seen.add(s)
        p = pattern(s)
        if is_text(p):
            out.setdefault(p, s)
    return out


def data_files(folder: Path) -> list[Path]:
    """The JSON and CSV files in a data/ folder (and its subfolders), relative to it."""
    if not folder.is_dir():
        return []
    return sorted(p.relative_to(folder) for p in folder.rglob("*") if p.is_file() and p.suffix in SUFFIXES)


def new_labels(old: Path, new: Path) -> dict[str, list[str]]:
    """{file: new text, in the order first seen} for each file in `new` with text the same file in `old` lacks.

    A file only in `new` has all its text new; a file only in `old` is not listed (nothing new)."""
    out = {}
    for rel in data_files(new):
        before = text_patterns(old / rel) if (old / rel).is_file() else {}
        added = [s for p, s in text_patterns(new / rel).items() if p not in before]
        if added:
            out[rel.as_posix()] = added
    return out


def markdown(found: dict[str, list[str]], *, limit: int = 40) -> str:
    """The new text as a Markdown list per file, at most `limit` strings each."""
    lines = []
    for rel, added in found.items():
        lines.append(f"- `{rel}`: {len(added)} new")
        for s in added[:limit]:
            one_line = " ".join(s.split())
            shown = one_line if len(one_line) <= 200 else one_line[:199] + "…"
            lines.append(f"  - `{shown.replace('`', "'")}`")
        if len(added) > limit:
            lines.append(f"  - … and {len(added) - limit} more")
    return "\n".join(lines) + ("\n" if lines else "")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or {"-h", "--help"} & set(args):
        print(__doc__, file=sys.stderr if len(args) != 2 else sys.stdout)
        return 0 if {"-h", "--help"} & set(args) else 2
    old, new = (Path(a) for a in args)
    if not new.is_dir():
        print(f"not a folder: {new}", file=sys.stderr)
        return 2
    try:
        found = new_labels(old, new)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, csv.Error) as e:
        print(f"cannot read the data: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(markdown(found))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

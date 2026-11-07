"""Text in the data the site reads: no markup and no control characters.

Much of the text in an area's data/ comes from its sources (state names, labels, notes in budget papers), and the
weekly refresh can bring new text in without anyone reading it. The site escapes what it shows, but a stray `<` or
`>` is never part of a label in these sources, and a control character (or U+2028/U+2029, which end a line inside a
script) means a garbled download. So every string in every data file, keys and values, must be free of them; a case
that is real must be listed by the area with its reason (`allowed`).

No field in any area's data needs a line break today, so a newline or tab fails like any other control character.
"""

import csv
import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path

from .report import BUILD_TIME_KEY, REPORT_FILE, SUMMARY_FILE, Allowed, Report

# '<', '>', the C0 and C1 control characters (tab, newline and carriage return among them), DEL, and the Unicode line
# and paragraph separators
BAD = re.compile(r"[<>\x00-\x1f\x7f-\x9f\u2028\u2029]")
MAX_LISTED = 50  # failures listed one by one; the rest are counted in one more
TITLE = "Text in the data: no '<', '>' or control characters"


def strings(value, where: str) -> Iterator[tuple[str, str]]:
    """(where, string) for every string in a JSON value: object keys and values, at any depth. The build time's value
    (BUILD_TIME_KEY) is left out: it differs from file to file by chance (two files written in the same second share
    one distinct text), so counting it would make the number of checks change from build to build."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield f"{where}: key", str(k)
            if k != BUILD_TIME_KEY:
                yield from strings(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from strings(v, f"{where}[{i}]")


def file_strings(path: Path) -> Iterator[tuple[str, str]]:
    """(where, string) for every string in a .json or .csv data file (for a CSV, the header and every cell)."""
    if path.suffix == ".json":
        yield from strings(json.loads(path.read_text(encoding="utf-8")), path.name)
    elif path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as f:
            rows = csv.reader(f)
            header = next(rows, [])
            for col in header:
                yield f"{path.name} header", col
            skip = {i for i, h in enumerate(header) if h == BUILD_TIME_KEY}
            for n, row in enumerate(rows, start=2):
                for i, cell in enumerate(row):
                    if i in skip:
                        continue
                    yield f"{path.name} line {n}, {header[i] if i < len(header) else f'column {i + 1}'}", cell


def data_files(data_dir: Path) -> list[Path]:
    """Every .json and .csv data file in data_dir, apart from the validation summary the checks write (none if the
    folder does not exist yet: checks run on their own, without a build, write only the report)."""
    if not data_dir.is_dir():
        return []
    return [p for p in sorted(data_dir.iterdir())
            if p.is_file() and p.suffix in (".json", ".csv") and p.name not in (REPORT_FILE, SUMMARY_FILE)]


def bad_characters(text: str) -> str:
    return ", ".join(repr(c) for c in sorted(set(BAD.findall(text))))


def is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def problems(data_dir: Path) -> tuple[int, list[tuple[str, str, int]]]:
    """(distinct texts checked, [(where it is first, text, times it occurs)]) for every text with a character it
    must not have. Numbers and empty strings (most CSV cells) are not text and are not counted."""
    seen: dict[str, list] = {}
    for path in data_files(data_dir):
        for where, text in file_strings(path):
            if text in seen:
                seen[text][1] += 1
            elif text and not is_number(text):
                seen[text] = [where, 1]
    return len(seen), [(where, text, n) for text, (where, n) in seen.items() if BAD.search(text)]


def check_data_text(data_dir: Path, report: Report, allowed: Callable[[str, str], str | None] | None = None) -> None:
    """One group of checks in the area's report, one check per distinct text in its data files. `allowed(where,
    text)` gives the reason a case is allowed, or None (a failure). Call it after every data file is written."""
    checked, found = problems(data_dir)
    failures, ok = [], Allowed(more_hint="")
    for where, text, n in found:
        case = f"{where}: {text[:120]!r} has {bad_characters(text)}{f' ({n} times)' if n > 1 else ''}"
        reason = allowed(where, text) if allowed else None
        if reason:
            ok.add(reason, case)
        else:
            failures.append(case)
    if len(failures) > MAX_LISTED:
        failures[MAX_LISTED:] = [f"and {len(failures) - MAX_LISTED} more texts with these characters"]
    files = ", ".join(p.name for p in data_files(data_dir))
    note = (f"Every key and text value (each distinct text counted once) in {files}." if files
            else f"No data files in {data_dir} to check.")
    report.add(TITLE, checked, failures, [note], allowed=ok, limit=20)

"""Small text helpers every area uses: ids made from labels, and fiscal-year labels.

India's fiscal year runs April to March and is written '2023-24': the year it starts, a hyphen and the last two
digits of the year it ends. Some sources write the century in full ('1999-2000'); fy_start reads both, and the
helpers that make a label always write the short form ('1999-00').
"""

import re

FY_RE = re.compile(r"(\d{4})-(\d{2}|\d{4})")


def slug(text: str, *, ascii_only: bool = False, max_len: int | None = None) -> str:
    """An id made from a label: lower case, every run of other characters one '_', none at either end.

    'Trade & Repair Services' -> 'trade_repair_services'. Letters and digits are Unicode ones unless ascii_only,
    which keeps only a-z and 0-9. max_len cuts the id to that many characters (after the rest, so a cut id can end
    in '_').
    """
    text = text.lower()
    keep = (lambda c: c.isascii() and c.isalnum()) if ascii_only else str.isalnum
    out = re.sub("_+", "_", "".join(c if keep(c) else "_" for c in text)).strip("_")
    return out[:max_len] if max_len is not None else out


def fy(start: int) -> str:
    """The fiscal year starting in April of `start`: 2011 -> '2011-12', 1999 -> '1999-00'."""
    return f"{start}-{str(start + 1)[-2:]}"


def fy_start(label: str) -> int:
    """The year a fiscal year starts: '2011-12' -> 2011; '1999-00' and '1999-2000' -> 1999.

    Raises ValueError for anything else, including a label whose two years do not follow each other."""
    m = FY_RE.fullmatch(label)
    if not m:
        raise ValueError(f"not a fiscal year: {label!r}")
    start, end = int(m[1]), m[2]
    if end != (str(start + 1) if len(end) == 4 else str(start + 1)[-2:]):
        raise ValueError(f"not a fiscal year (the years do not follow each other): {label!r}")
    return start


def next_fy(label: str, years: int = 1) -> str:
    """The fiscal year `years` after this one: '1999-00' -> '2000-01' (always the short form)."""
    return fy(fy_start(label) + years)


def prev_fy(label: str, years: int = 1) -> str:
    """The fiscal year `years` before this one: '2000-01' -> '1999-00' (always the short form)."""
    return fy(fy_start(label) - years)

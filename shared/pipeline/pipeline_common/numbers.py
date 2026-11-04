"""Reading numbers as the sources print them ('1,23,456.7', '12.5*', '-', '').

Three readers, for three kinds of source:

- number: lenient, for data services and tables whose cells may hold anything (MoSPI's API, press release tables).
  Anything that is not a number is None; the caller decides whether that is a problem (and usually keeps the cell
  as printed beside it).
- blank_or_number: for our own files and parsed tokens, where a cell is either blank (or one of the given
  "not available" markers) or a number. Anything else raises: it is a bug, not a gap.
- strict_number: for text a regular expression has already matched as a number. Raises if it is not one.

All three ignore thousands separators (Indian '1,23,456' or Western '123,456') and surrounding whitespace, and
none takes 'nan' or 'inf' (which float() reads) as a number.
"""

import math
from collections.abc import Collection


def _clean(text: str, strip: str) -> str:
    text = text.replace(",", "")
    for c in strip:
        text = text.replace(c, "")
    return text.strip()


def _finite(text: str) -> float:
    x = float(text)
    if not math.isfinite(x):
        raise ValueError(f"not a finite number: {text!r}")
    return x


def number(value, *, strip: str = "") -> float | None:
    """value as a float, or None when it is not a number.

    None, blank, NaN, infinity and anything float() cannot read ('-', 'NA', 'l0.8') are None. Numbers (int, float) pass
    through as floats. `strip` lists characters removed first, such as '*' for footnote marks ('12.5*' -> 12.5).
    """
    if value is None:
        return None
    try:
        return _finite(_clean(str(value), strip))
    except ValueError:
        return None


def blank_or_number(value, *, missing: Collection[str] = ()) -> float | None:
    """None for None, a blank cell or one of the `missing` markers (for example '-' or 'NA'); otherwise the number,
    raising ValueError if it is not one."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text in missing:
        return None
    return strict_number(text)


def strict_number(text: str) -> float:
    """The number in text ('1,76,50,591' -> 17650591.0). Raises ValueError if it is not a finite number."""
    return _finite(_clean(text, ""))

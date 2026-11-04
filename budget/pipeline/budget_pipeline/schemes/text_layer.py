"""Cells and names missing from (or garbled in) a PDF's text layer, read from the rendered page."""

import re

from ..parse import ParseError
from .common import Line

# A few PDFs draw some text without a usable text layer (the glyphs are on the
# page but not extractable). These cells were read from the page rendered as an
# image (pdfplumber .to_image at 170-200 dpi) and are applied only when the text
# layer shows exactly the broken fragment noted below, so a corrected file will
# not be silently overridden. Each row is then verified by the same checks as
# every other row (Revenue + Capital = Total, rows add up to totals).

IMAGE_READINGS: list[dict] = [
    {
        "budget": "2025-26", "scheme_type": "css", "page": 5,
        "label_re": r"^(Others|82\. Others)", "expect": {3: r"\.?4?2?"},
        "cells": {3: "-8034.42"},
        "reason": "Budget 2025-26 Statement 4A, 'Others' group and item 82: the text layer has only '-' and "
                  "'.42' for BE 2024-25 revenue (the digits are drawn but not extractable); the page image "
                  "shows -8034.42, which also equals the row's printed total.",
    },
    {
        "budget": "2025-26", "scheme_type": "css", "page": 5, "insert_grand_total": True,
        "cells": dict(enumerate(["444416.49", "130.71", "444547.20", "505941.24", "36.83", "505978.07",
                                 "415322.05", "34.20", "415356.25", "536826.78", "23.43", "541850.21"])),
        "reason": "Budget 2025-26 Statement 4A: the Grand Total row is printed (page image) but absent from "
                  "the PDF text layer and from the Excel copy. Values read from the page image.",
    },
    {
        "budget": "2025-26", "scheme_type": "central_sector", "page": 25,
        "label_re": r"^Grand Total", "expect": {1: r"734166\.62"},
        "cells": dict(enumerate(["689270.79", "734166.62", "1423437.41", "750579.03", "765596.72", "1516175.75",
                                 "761222.21", "751597.54", "1512819.75", "787524.99", "834373.91", "1621898.90"])),
        "reason": "Budget 2025-26 Statement 4B: the text layer (and the Excel copy) has only one of the 12 "
                  "Grand Total figures; the rest read from the page image.",
    },
]

IMAGE_READINGS.append({
    "budget": "2017-18", "scheme_type": "central_sector", "page": 12,
    "label_re": r"^313\. Gross Exp\. on Schemes for Safety of Women", "expect": {10: r"22\.69\.*"},
    "cells": {10: "22.69"},
    "reason": "Budget 2017-18 Statement 4B item 313: the text layer has '22.69..' for BE 2017-18 capital "
              "(dots from an overprinted '...'); the page image shows 22.69, and 340.61 + 22.69 = 363.30 "
              "as printed.",
})

# Names missing from the text layer: (budget, scheme_type, page, first value printed) -> name.
MISSING_LABELS: dict[tuple[str, str, int, str], tuple[str, str]] = {
    ("2020-21", "css", 2, "2224.47"): (
        "30. Pradhan Mantri Jan Arogya Yojana (including RSBY)",
        "Budget 2020-21 Statement 4A: the name of item 30 is printed but absent from the text layer; read "
        "from the page image. Budget 2021-22 prints the same 2019-20 RE (3,314.00) for this scheme.",
    ),
}


# Names garbled in the text layer (two overprinted strings interleaved): (budget, scheme_type, page,
# garbled label regex) -> (replacement label, text the previous row's name lost, reason).
GARBLED_LABELS: list[tuple[tuple[str, str, int, str], tuple[str, str, str]]] = [
    (("2022-23", "css", 2, r"^45\.\s*mGraeregnin R uenvodleurt iNoFnSA$"), (
        "45. Green Revolution", "Margin under NFSA",
        "Budget 2022-23 Statement 4A: the text layer interleaves item 45's name 'Green Revolution' with the "
        "last line of item 44's name ('Margin under NFSA'); both read from the page image.")),
]


def apply_text_layer_fixes(lines: list[Line], budget: str, scheme_type: str) -> tuple[list[Line], list[str]]:
    used: list[str] = []
    for (b_, t_, page, pat), (new_label, lost, reason) in GARBLED_LABELS:
        if (b_, t_) != (budget, scheme_type):
            continue
        idx = next((k for k, ln in enumerate(lines) if ln.page == page and re.match(pat, ln.label)), None)
        if idx is None:
            raise ParseError(f"{budget} {scheme_type}: garbled label {pat!r} not found; review GARBLED_LABELS")
        lines[idx].label = new_label
        lines.insert(idx, Line(lost, [None] * 12, page, lines[idx].bottom - 0.1, lost))
        used.append(reason)
    for fix in IMAGE_READINGS:
        if fix["budget"] != budget or fix["scheme_type"] != scheme_type:
            continue
        if fix.get("insert_grand_total"):
            if any(re.match(r"^grand\s*total", ln.label, re.I) for ln in lines):
                raise ParseError(f"{budget} {scheme_type}: a Grand Total row is now readable; review IMAGE_READINGS")
            last = max((ln for ln in lines if ln.page == fix["page"]), key=lambda ln: ln.bottom)
            cells = [fix["cells"][k] for k in range(12)]
            lines.append(Line("Grand Total", cells, fix["page"], last.bottom + 10, "Grand Total (from page image)"))
            used.append(fix["reason"])
            continue
        hits = 0
        for ln in lines:
            if ln.page == fix["page"] and re.match(fix["label_re"], ln.label):
                if any(not re.fullmatch(v, ln.cells[k] or "") for k, v in fix["expect"].items()):
                    raise ParseError(f"{budget} {scheme_type} p{ln.page} {ln.label!r}: text layer changed "
                                     f"({[ln.cells[k] for k in fix['expect']]}); review IMAGE_READINGS")
                for k, v in fix["cells"].items():
                    ln.cells[k] = v
                ln.label = re.sub(r"\s+-$", "", ln.label)
                hits += 1
        if not hits:
            raise ParseError(f"{budget} {scheme_type}: image reading {fix['label_re']!r} matched no row")
        used.append(fix["reason"])
    for ln in lines:
        key = (budget, scheme_type, ln.page, ln.cells[0] or "")
        if not ln.label and key in MISSING_LABELS:
            ln.label = MISSING_LABELS[key][0]
            used.append(MISSING_LABELS[key][1])
    return lines, used

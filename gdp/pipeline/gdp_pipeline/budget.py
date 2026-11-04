"""The Union Budget's assumption for nominal GDP.

Budget at a Glance prints, under its headline table, the GDP used for the
% of GDP figures, e.g. "GDP for BE 2023-2024 has been projected at
₹3,01,75,065 crore assuming 10.5% growth over the estimated Nominal GDP of
₹2,73,07,751 crore as per the First Advance Estimates". This is the
government's working forecast of nominal (not real) GDP for the budget year.

The sentence is found and read by pipeline_common.budget_glance, which the
budget area uses for the same figure.
"""

from pathlib import Path

from pipeline_common.budget_glance import parse_sentence, texts
from pipeline_common.text import fy


ROOT = Path(__file__).resolve().parents[2]


def assumption(start: int, manifest: dict) -> dict | None:
    year = fy(start)
    entry = manifest.get(f"budget/{year}/bag1")
    if not entry:
        return None
    src = {"url": entry["url"], "sha256": entry["sha256"], "document": f"Budget at a Glance {year}"}
    found, note = texts(year, ROOT / entry["file"])
    for text in found:
        parsed = parse_sentence(text)
        if parsed:
            return {"budget": year, **parsed, **src, **({"note": note} if note else {})}
    return None

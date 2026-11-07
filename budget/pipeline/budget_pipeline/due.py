"""Whether the next Union Budget is out and not yet added (pipeline_common.due has the output and exit codes).

    uv run --locked python -m budget_pipeline.due

The latest budget's documents are at indiabudget.gov.in's root (pipeline_common.budget_glance.site), so its Budget
at a Glance headline table (one PDF, under 1.5 MB) shows which budget is the newest there:
- the same file as the committed copy of LATEST_BUDGET's: nothing new;
- a newer budget year printed on it: due (an interim budget, in an election year, is not: the pipeline skips it and
  waits for the full budget);
- the year cannot be read: due if the current budget has moved to its own folder (budget<year>/doc/, where earlier
  budgets live), which happens when the next one is published;
- the same year in a different file: a warning (a corrected copy, to compare with the committed one).
A network error or an unexpected answer is a warning, never a failure. Whatever the probe says, the next budget is
due from 1 August of its year (1 February, or July after an election, has long passed).
"""

import argparse
import io
import json
import re
import sys
from collections.abc import Callable
from datetime import date
from hashlib import sha256
from pathlib import Path

from pipeline_common import budget_glance
from pipeline_common import log as pipeline_log
from pipeline_common.download import file_kind, get
from pipeline_common.due import Findings
from pipeline_common.text import fy, fy_start, is_fy

from .sources import LATEST_BUDGET, manifest_key

MANIFEST = Path(__file__).resolve().parents[2] / "sources" / "manifest.json"

WHERE = ("Add it: budget/README.md, 'Adding a new budget' (raise LATEST_BUDGET in "
         "shared/pipeline/pipeline_common/budget_glance.py, then --fetch).")
YEAR_RE = re.compile(r"(?<!\d)(\d{4})\s*-\s*(\d{4}|\d{2})(?!\d)")
INTERIM_RE = re.compile(r"\binterim\b", re.I)
BACKSTOP = (8, 1)  # (month, day) of the next budget's year from which it is due whatever the probe says


def budget_year(text: str) -> int | None:
    """The newest fiscal year printed in a Budget at a Glance headline table (the budget's own year: its last
    column is that year's Budget Estimate), as the year it starts."""
    return max((fy_start(f"{a}-{b}") for a, b in YEAR_RE.findall(text) if is_fy(f"{a}-{b}")), default=None)


def pdf_text(content: bytes) -> str:
    """The text of every page (and of each page's English column), as the budget area reads the table."""
    return "\n".join(budget_glance.page_texts(io.BytesIO(content)))


def committed_sha(manifest: dict, start: int) -> str | None:
    return manifest.get(manifest_key(fy(start), "summary", "pdf"), {}).get("sha256")


def fetch_pdf(url: str, fetch: Callable[[str], bytes]) -> tuple[bytes | None, str | None]:
    """(the PDF at url, None), or (None, why not)."""
    try:
        content = fetch(url)
    except Exception as exc:  # noqa: BLE001 - any failure to reach the site is a warning, not a failure
        if hasattr(exc, "close"):
            exc.close()  # an HTTPError holds the server's answer open
        return None, f"{url}: {exc}"
    if file_kind(content) != "pdf":
        return None, f"{url} is not a PDF (the site's addresses may have changed)"
    return content, None


def check(today: date, fetch: Callable[[str], bytes] = get, manifest: dict | None = None,
          latest: int = LATEST_BUDGET) -> Findings:
    out = Findings()
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    nxt = latest + 1
    what = f"Union Budget {fy(nxt)}"
    root = budget_glance.url(nxt, nxt)
    content, problem = fetch_pdf(root, fetch)
    if content is None:
        out.warnings.append(f"{what}: could not check indiabudget.gov.in: {problem}")
    elif sha256(content).hexdigest() == committed_sha(manifest, latest):
        out.ok.append(f"{what}: not out yet (indiabudget.gov.in's Budget at a Glance is the committed {fy(latest)} copy)")
        return backstop(out, today, nxt)
    else:
        try:
            text = pdf_text(content)
        except Exception as exc:  # noqa: BLE001 - a PDF that cannot be read: its year is unknown, as below
            out.warnings.append(f"{what}: could not read the PDF at {root}: {exc}")
            text = ""
        year = budget_year(text)
        if year is not None and year > latest and INTERIM_RE.search(text):
            out.ok.append(f"Interim Budget {fy(year)} is out at {root}; the pipeline skips interim budgets and waits "
                          "for the full budget after the election")
            return backstop(out, today, nxt)
        if year is not None and year > latest:
            out.due.append(f"{what}: Budget at a Glance for {fy(year)} is on indiabudget.gov.in ({root}); the site has "
                           f"{fy(latest)}. {WHERE}")
            return out
        if year == latest:
            out.warnings.append(f"Budget at a Glance {fy(latest)} at {root} differs from the committed copy: a corrected "
                                "file? Compare it, and run --refresh if it is")
            out.ok.append(f"{what}: not out yet (indiabudget.gov.in's Budget at a Glance is still {fy(latest)})")
            return backstop(out, today, nxt)
        # The year cannot be read: has the current budget moved out of the site's root?
        moved = budget_glance.url(latest, nxt)
        archived, _ = fetch_pdf(moved, fetch)
        if archived is not None:
            out.due.append(f"{what}: indiabudget.gov.in has a new Budget at a Glance ({root}; its year could not be "
                           f"read) and has moved {fy(latest)} to {moved}. {WHERE}")
            return out
        out.warnings.append(f"{what}: Budget at a Glance at {root} differs from the committed {fy(latest)} copy, "
                            f"but its year could not be read and {fy(latest)} has not moved to {moved}")
    return backstop(out, today, nxt)


def backstop(out: Findings, today: date, nxt: int) -> Findings:
    if today >= date(nxt, *BACKSTOP):
        out.due.append(f"Union Budget {fy(nxt)}: due since 1 February {nxt} (or July after an election), and it is "
                       f"{today.day} {today:%B %Y}. {WHERE}")
    return out


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    pipeline_log.setup(__package__)
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    return check(today or date.today()).finish()


if __name__ == "__main__":
    sys.exit(main())

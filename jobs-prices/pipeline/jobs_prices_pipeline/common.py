"""What the readers of the downloaded files share: where the files are, the files themselves, and month names."""

import json
import logging
from pathlib import Path

from .sources import WITHDRAWN, queries

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sources" / "manifest.json"
log = logging.getLogger(__name__)

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
MONTH_NO = {m: i + 1 for i, m in enumerate(MONTHS)}


def matches(row: dict, fields: dict) -> bool:
    return all(row.get(k) == v for k, v in fields.items())


def withdrawn_rows(key: str, entry: dict, rows: list[dict]) -> tuple[list[dict], str | None]:
    """The rows of `key` listed in sources.WITHDRAWN that `rows` (the current download) lacks, from the newest
    earlier download in the manifest entry's history that has them, and that file. Nothing if the current download
    has them."""
    fields = WITHDRAWN.get(key)
    if not fields:
        return [], None
    if any(matches(r, fields) for r in rows):
        log.info(f"{key}: the current download has the rows listed in WITHDRAWN ({fields}); none kept from earlier")
        return [], None
    for old in reversed(entry.get("history", [])):
        kept = [r for r in json.loads((ROOT / old["file"]).read_text())["rows"] if matches(r, fields)]
        if kept:
            return kept, old["file"]
    raise RuntimeError(f"{key}: no download has the rows listed in sources.WITHDRAWN ({fields})")


def load(manifest: dict, prefix: str) -> list[tuple[str, dict, dict]]:
    """(key, manifest entry, file body) for every file downloaded from MoSPI's data service under a prefix. Rows
    MoSPI has withdrawn and the site keeps (sources.WITHDRAWN) are added to the body's rows, and listed in its
    "kept": {"file", "rows"}."""
    out = []
    for key, _, _ in queries():
        if not key.startswith(prefix):
            continue
        entry = manifest.get(key)
        if not entry or entry.get("empty"):
            continue
        body = json.loads((ROOT / entry["file"]).read_text())
        kept, file = withdrawn_rows(key, entry, body["rows"])
        if kept:
            body["rows"] = body["rows"] + kept
            body["kept"] = {"file": file, "rows": len(kept)}
        out.append((key, entry, body))
    return out

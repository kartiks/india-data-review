"""What the readers of the downloaded files share: where the files are, the files themselves, and month names."""

import json
from pathlib import Path

from .sources import queries

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "sources" / "manifest.json"

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
MONTH_NO = {m: i + 1 for i, m in enumerate(MONTHS)}


def load(manifest: dict, prefix: str) -> list[tuple[str, dict, dict]]:
    """(key, manifest entry, file body) for every file downloaded from MoSPI's data service under a prefix."""
    out = []
    for key, _, _ in queries():
        if not key.startswith(prefix):
            continue
        entry = manifest.get(key)
        if not entry or entry.get("empty"):
            continue
        out.append((key, entry, json.loads((ROOT / entry["file"]).read_text())))
    return out

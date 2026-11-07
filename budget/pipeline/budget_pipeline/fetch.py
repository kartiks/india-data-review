"""Download every official table, in every available format.

Files are saved as budget/sources/raw/<budget year>/<document>.<ext> and described
in budget/sources/manifest.json (URL, SHA-256, size, download time), so every
number we publish can be traced back to an exact official file. A file only
counts if its text contains the table's title (see sources.TITLE_MUST_CONTAIN).

Run: uv run python -m budget_pipeline.fetch [--force]
"""

import hashlib
import json
import re
import sys
import tempfile
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

from pipeline_common.download import POLITE_PAUSE_S, file_kind, get
from pipeline_common.text import fy

from .readers import read_any
from .sources import BUDGETS, DOC_TYPES, TITLE_MUST_CONTAIN, candidate_urls

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "sources" / "raw"
MANIFEST = ROOT / "sources" / "manifest.json"


MIN_BYTES = 500  # smaller than any real table: an empty or error answer


def looks_valid(ext: str, content: bytes) -> bool:
    """Whether a download is the kind of file its address says (.pdf, .xlsx, .xls, else a web page) and not the
    site's 404 page. A mismatch means the candidate address does not hold the table: it is skipped, not an error."""
    if len(content) < MIN_BYTES:
        return False
    if ext in ("pdf", "xlsx", "xls"):
        return file_kind(content) == ext
    return file_kind(content) == "html" and b"404 - file or directory not found" not in content[:3000].lower()


def has_title(doc: str, ext: str, content: bytes) -> bool:
    with tempfile.NamedTemporaryFile(suffix=f".{ext}") as tmp:
        tmp.write(content)
        tmp.flush()
        try:
            rows = read_any(Path(tmp.name))
        except Exception:
            return False
    text = " ".join(" ".join(r) for r in rows[:80]).lower()
    return re.search(TITLE_MUST_CONTAIN[doc], text) is not None


def main(force: bool = False, docs: list[str] | None = None) -> None:
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    for start in BUDGETS:
        year = fy(start)
        entry = manifest.setdefault(year, {})
        for doc in docs or DOC_TYPES:
            files = entry.get(doc, {}).get("files", {})
            # One file per format: the first candidate address that holds the table (Statement 3A before
            # Statement 3). --force downloads it again but never lets a later candidate replace it.
            saved_now: set[str] = set()
            for url in candidate_urls(start, doc):
                ext = url.rsplit(".", 1)[-1]
                if ext in saved_now or (ext in files and not force):
                    continue
                content = None
                try:
                    content = get(url)
                except urllib.error.HTTPError as exc:
                    if exc.code != 404:  # most candidate addresses do not exist
                        print(f"{year} {doc}: {url} -> {exc}")
                except Exception as exc:  # noqa: BLE001 - a network error after get()'s retries: report and carry on
                    print(f"{year} {doc}: {url} -> {exc}")
                time.sleep(POLITE_PAUSE_S)
                if content is None or not looks_valid(ext, content):
                    continue
                if not has_title(doc, ext, content):
                    print(f"{year} {doc}: {url} is not the expected table, skipped")
                    continue
                dest = RAW / year / f"{doc}.{ext}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                files[ext] = {
                    "url": url,
                    "file": str(dest.relative_to(ROOT)),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": len(content),
                    "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                }
                saved_now.add(ext)
                print(f"{year} {doc}: saved {dest.name} ({len(content):,} bytes)")
            if files:
                entry[doc] = {"files": files}
            elif candidate_urls(start, doc):
                print(f"{year} {doc}: NO SOURCE FOUND")
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")


if __name__ == "__main__":
    main(force="--force" in sys.argv)

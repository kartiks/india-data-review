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
from datetime import datetime, timezone
from pathlib import Path

import requests

from .readers import read_any
from .sources import BUDGETS, DOC_TYPES, TITLE_MUST_CONTAIN, candidate_urls, fy

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "sources" / "raw"
MANIFEST = ROOT / "sources" / "manifest.json"

HEADERS = {"User-Agent": "india-data-review-budget-pipeline/0.1 (python-requests)"}


def looks_valid(ext: str, content: bytes) -> bool:
    if len(content) < 500:
        return False
    head = content[:8]
    if ext == "pdf":
        return head.startswith(b"%PDF")
    if ext == "xlsx":
        return head.startswith(b"PK")
    if ext == "xls":
        return head.startswith(b"\xd0\xcf\x11\xe0")  # OLE2 container
    lowered = content[:3000].lower()
    return b"<html" in lowered and b"404 - file or directory not found" not in lowered


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
    session = requests.Session()
    session.headers.update(HEADERS)
    for start in BUDGETS:
        year = fy(start)
        entry = manifest.setdefault(year, {})
        for doc in docs or DOC_TYPES:
            files = entry.get(doc, {}).get("files", {})
            for url in candidate_urls(start, doc):
                ext = url.rsplit(".", 1)[-1]
                if ext in files and not force:
                    continue
                try:
                    resp = session.get(url, timeout=60)
                except requests.RequestException as exc:
                    print(f"{year} {doc}: {url} -> {exc}")
                    continue
                time.sleep(0.5)  # be polite to the government server
                if resp.status_code != 200 or not looks_valid(ext, resp.content):
                    continue
                if not has_title(doc, ext, resp.content):
                    print(f"{year} {doc}: {url} is not the expected table, skipped")
                    continue
                dest = RAW / year / f"{doc}.{ext}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                files[ext] = {
                    "url": url,
                    "file": str(dest.relative_to(ROOT)),
                    "sha256": hashlib.sha256(resp.content).hexdigest(),
                    "bytes": len(resp.content),
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                print(f"{year} {doc}: saved {dest.name} ({len(resp.content):,} bytes)")
            if files:
                entry[doc] = {"files": files}
            elif candidate_urls(start, doc):
                print(f"{year} {doc}: NO SOURCE FOUND")
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")


if __name__ == "__main__":
    main(force="--force" in sys.argv)

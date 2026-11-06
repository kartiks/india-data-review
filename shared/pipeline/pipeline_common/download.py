"""Downloading sources: HTTP with retries, saving with snapshots, the manifest, and MoSPI's paged API.

Every area keeps its downloads under <area>/sources/: raw/ (the files), manifest.json (one entry per file: URL,
SHA-256, size, time) and snapshots/<time fetched>/ (earlier versions of files that are revised in place; see
snapshot_name). The areas pass their own paths, so these functions hold no state.
"""

import hashlib
import json
import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "india-data-review-data-pipeline/0.1 (python-urllib)"
TRIES = 5
BACKOFF_S = 5  # waits 5, 10, 15, 20 s between the tries
TIMEOUT_S = 120

# api.mospi.gov.in needs TLS legacy renegotiation, which Python turns off by default, so it is turned on for that
# host only. Certificates are still verified everywhere.
TLS = ssl.create_default_context()
LEGACY_TLS_HOSTS = {"api.mospi.gov.in"}
LEGACY_TLS = ssl.create_default_context()
LEGACY_TLS.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)

# The first bytes of each kind of file, to tell a document from an error page saved under its address.
MAGIC = {"pdf": b"%PDF", "xlsx": b"PK", "xls": b"\xd0\xcf\x11\xe0"}  # xlsx: a zip; xls: an OLE2 container


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_type(content: bytes, ext: str) -> bool:
    """Whether the content starts like a file of this kind (pdf, xlsx or xls)."""
    return content.startswith(MAGIC[ext])


def _retryable(exc: Exception) -> bool:
    """Network faults, timeouts (incl. HTTP 408), rate limits and server errors are tried again; other HTTP
    errors (404 …) are an answer."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code in (408, 429)
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError))


def tls_for(url: str) -> ssl.SSLContext:
    return LEGACY_TLS if urllib.parse.urlsplit(url).hostname in LEGACY_TLS_HOSTS else TLS


def _open(req: urllib.request.Request, timeout: float):
    return urllib.request.urlopen(req, timeout=timeout, context=tls_for(req.full_url))


def get(url: str, tries: int = TRIES, opener: Callable = _open) -> bytes:
    """The body at url. Raises urllib.error.HTTPError for a 4xx answer, and the last error after `tries` tries."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with opener(req, timeout=TIMEOUT_S) as resp:
                return resp.read()
        except Exception as exc:
            if not _retryable(exc) or attempt == tries - 1:
                raise
            print(f"  retry {attempt + 1} for {url}: {exc}", flush=True)
            time.sleep(BACKOFF_S * (attempt + 1))
    raise AssertionError


def fetch_pages(page_url: Callable[[int], str], what: str) -> list[dict]:
    """Every row of one query to MoSPI's API (api.mospi.gov.in), across all pages: page_url(n) is the address of
    page n, from 1. Rows are sorted, so an unchanged dataset gives identical rows. Raises if the rows do not add up to
    the totalRecords the API reports."""
    rows: list[dict] = []
    page, total = 1, None
    while True:
        body = json.loads(get(page_url(page)))
        data = body.get("data") or []
        meta = body.get("meta_data") or {}
        if total is None:
            total = meta.get("totalRecords") or 0
        rows += data
        if not data or page >= (meta.get("totalPages") or 1):
            break
        if page % 20 == 0:
            print(f"  {what}: page {page} of {meta.get('totalPages')}", flush=True)
        page += 1
        time.sleep(0.3)
    if len(rows) != total:
        raise RuntimeError(f"{what}: got {len(rows)} rows, API says {total}")
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    return rows


MAX_DROP = 0.05  # a re-download with more than 5% fewer records than the saved file is refused


class RecordsDropped(RuntimeError):
    """A re-download has far fewer records than the file saved before."""


def check_records(manifest: dict, key: str, records: int, max_drop: float = MAX_DROP) -> None:
    """Raise RecordsDropped if a re-download of `key` has more than max_drop (a fraction) fewer records than the
    saved file (the manifest's "records"). Revisions add or change rows; a much shorter answer is more likely a
    partial or faulty one, so the caller keeps the saved file. If the source really did drop the rows, remove the
    entry's "records" from the manifest and download again."""
    before = (manifest.get(key) or {}).get("records")
    if before and records < before * (1 - max_drop):
        raise RecordsDropped(
            f"{key}: {records:,} records, {before:,} before ({(before - records) / before:.0%} fewer, more than "
            f"{max_drop:.0%}); kept the saved file. If the source really dropped them, remove \"records\" from this "
            "entry in sources/manifest.json and download again.")


def snapshot_name(fetched_at: str) -> str:
    """The folder under snapshots/ for a version fetched at `fetched_at` (ISO 8601): its UTC time to the second,
    '2026-01-05T093000Z' (no colons, which some file systems refuse), so two versions fetched on the same day never
    share a folder. Folders made before were named by the date only ('2026-01-05') and keep their names; sorted as
    text, both kinds are in time order. The build reads versions in the order of the manifest entry's history, not
    by folder name."""
    return datetime.fromisoformat(fetched_at).astimezone(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def save(manifest: dict, key: str, dest: Path, content: bytes, url: str, extra: dict | None = None, *,
         root: Path, raw: Path, snapshots: Path) -> bool:
    """Write the file (dest, under raw) and its manifest entry; paths in the manifest are relative to root. If the
    file changed, the previous version is kept under snapshots/<time it was fetched>/ (snapshot_name) and listed at
    the end of the entry's history (oldest first). Returns True if the file is new or changed."""
    sha = hashlib.sha256(content).hexdigest()
    old = manifest.get(key)
    if old and old.get("sha256") == sha and dest.exists():
        old["checked_at"] = now()
        return False
    history = old.get("history", []) if old else []
    if old and old.get("sha256") and dest.exists():
        snap = snapshots / snapshot_name(old["fetched_at"]) / dest.relative_to(raw)
        snap.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, snap)
        history.append({"sha256": old["sha256"], "fetched_at": old["fetched_at"], "file": str(snap.relative_to(root))})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    manifest[key] = {
        "url": url,
        "file": str(dest.relative_to(root)),
        "sha256": sha,
        "bytes": len(content),
        "fetched_at": now(),
        **(extra or {}),
        **({"history": history} if history else {}),
    }
    return True


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def write_manifest(path: Path, manifest: dict) -> None:
    """Keys sorted, one level of indent: an unchanged manifest gives an identical file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1, ensure_ascii=False) + "\n")

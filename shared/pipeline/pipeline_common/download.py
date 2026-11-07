"""Downloading sources: HTTP with retries, saving with snapshots, the manifest, and MoSPI's paged API.

Every area keeps its downloads under <area>/sources/: raw/ (the files), manifest.json (one entry per file: URL,
SHA-256, size, time) and snapshots/<time fetched>/ (earlier versions of files that are revised in place; see
snapshot_name). The areas pass their own paths, so these functions hold no state.

The manifest, the same in every area (save() writes an entry, write_manifest() the file):

    {"<key>": {entry}, ...}     one object; keys sorted; indent 1; UTF-8 as is (ensure_ascii off); a final newline

<key> names one downloaded file: its path under sources/raw/ (or sources/) without the extension, e.g.
"nas/2011-12/Back/Annually/ind01", "reference/rbi/table86_key_deficit_indicators", with the format added when one
document is kept in several, e.g. "2016-17/summary/pdf" and "2016-17/summary/xls" (budget) or "cpi2024/2026-01/pdf".
An entry has these fields, the first five always and in this order:

    url          the address it was downloaded from
    file         where it is saved, relative to the area's folder ("sources/raw/...")
    sha256       of the file
    bytes        its size
    fetched_at   when this version was downloaded (ISO 8601, UTC, to the second)
    ...          fields of the area's own, e.g. records (rows in an API answer, see check_records), document,
                 edition, title, publisher, downloaded_by_hand
    checked_at   when a later download found the same file (only once one has)
    history      earlier versions, oldest first, each {"sha256", "fetched_at", "file"} (its copy under snapshots/);
                 only once the file has changed

A query that answered with nothing is recorded as {"url", "empty": true, "checked_at"} (and an optional "note"), so
it is not asked again on every --fetch.
"""

import hashlib
import http.client
import json
import logging
import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

USER_AGENT = "india-data-review-data-pipeline/0.1 (python-urllib)"

# Network timing, in one place for every area.
TRIES = 5
BACKOFF_S = 5  # waits 5, 10, 15, 20 s between the tries: long enough for a briefly overloaded server to recover
TIMEOUT_S = 120  # seconds without an answer before a try fails: the largest files (tens of MB) come from slow servers
PAGE_PAUSE_S = 0.3  # between pages or queries of MoSPI's API: hundreds of requests in a row, so go gently
POLITE_PAUSE_S = 0.5  # between documents from one government or RBI web server, to be polite
RELEASE_PAUSE_S = 1.0  # between PIB press-release pages (each also fetches its PDF)

# The largest file any area keeps is about 30 MB (a MoSPI API answer); anything far larger is not a source we want
# (a wrong address, or a server streaming without end), so get() stops reading and raises.
MAX_BYTES = 200 * 1024 * 1024

# api.mospi.gov.in needs TLS legacy renegotiation, which Python turns off by default, so it is turned on for that
# host only. Certificates are still verified everywhere.
TLS = ssl.create_default_context()
LEGACY_TLS_HOSTS = {"api.mospi.gov.in"}
LEGACY_TLS = ssl.create_default_context()
LEGACY_TLS.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


class TooLarge(RuntimeError):
    """A download larger than MAX_BYTES."""


class DowngradeRefused(urllib.error.HTTPError):
    """An https address redirected to a plain http one. Not tried again."""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def file_kind(content: bytes) -> str | None:
    """What a file is, from its first bytes: "pdf", "xlsx" (a zip, as .xlsx files are), "xls" (an OLE2 container,
    as .xls files are), "html", "json", or None if none of these. Every area tells a document from a web page or an
    error page saved under its address with this one test; what a mismatch means (skip the file, or stop) is up to
    each caller."""
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"PK"):
        return "xlsx"
    if content.startswith(b"\xd0\xcf\x11\xe0"):
        return "xls"
    head = content[:3000].lower()
    if b"<html" in head or head.lstrip().startswith(b"<!doctype html"):
        return "html"
    if content.lstrip()[:1] in (b"{", b"["):
        return "json"
    return None


def _retryable(exc: Exception) -> bool:
    """Network faults, timeouts (incl. HTTP 408), rate limits and server errors are tried again; other HTTP
    errors (404 …) are an answer."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code in (408, 429)
    return isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead))


def tls_for(url: str) -> ssl.SSLContext:
    return LEGACY_TLS if urllib.parse.urlsplit(url).hostname in LEGACY_TLS_HOSTS else TLS


class _NoDowngrade(urllib.request.HTTPRedirectHandler):
    """Follows redirects, except from https to anything else."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(req.full_url).scheme == "https" and urllib.parse.urlsplit(newurl).scheme != "https":
            raise DowngradeRefused(req.full_url, code, f"refused a redirect from https to {newurl}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(req: urllib.request.Request, timeout: float):
    handlers = (urllib.request.HTTPSHandler(context=tls_for(req.full_url)), _NoDowngrade())
    return urllib.request.build_opener(*handlers).open(req, timeout=timeout)


def _check_complete(resp, body: bytes) -> None:
    """Raise IncompleteRead if the body is shorter than the Content-Length header says. read(n) returns a short body
    without an error when the connection drops (read() with no size would raise), and a cut-off PDF or Excel file
    still starts with the right bytes, so it would otherwise be saved over the good copy."""
    headers = getattr(resp, "headers", None)
    expected = headers.get("Content-Length") if headers is not None else None
    if expected and expected.strip().isdigit() and len(body) < int(expected):
        raise http.client.IncompleteRead(body, int(expected) - len(body))


def get(url: str, tries: int = TRIES, opener: Callable = _open) -> bytes:
    """The body at url. Raises urllib.error.HTTPError for a 4xx answer, DowngradeRefused for a redirect from https to
    http, TooLarge past MAX_BYTES, and the last error (a cut-off download is tried again) after `tries` tries."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with opener(req, timeout=TIMEOUT_S) as resp:
                body = resp.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise TooLarge(f"{url}: more than {MAX_BYTES:,} bytes (download.MAX_BYTES); not a source we expect")
            _check_complete(resp, body)
            return body
        except Exception as exc:
            if not _retryable(exc) or attempt == tries - 1:
                raise
            if isinstance(exc, urllib.error.HTTPError):
                exc.close()  # it holds the server's response open
            log.info(f"  retry {attempt + 1} for {url}: {exc}")
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
            log.info(f"  {what}: page {page} of {meta.get('totalPages')}")
        page += 1
        time.sleep(PAGE_PAUSE_S)
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
    return datetime.fromisoformat(fetched_at).astimezone(UTC).strftime("%Y-%m-%dT%H%M%SZ")


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

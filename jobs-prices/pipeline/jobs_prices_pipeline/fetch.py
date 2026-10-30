"""Download every source file and record it in sources/manifest.json.

One file per query in sources.queries(), with every page of the API response
combined, saved as sources/raw/<key>.json. Rows are sorted and written one per
line, so an unchanged dataset gives an identical file (and SHA-256) and a
changed one gives a readable diff.

MoSPI's API keeps only the latest figures. When a re-download differs from the
saved file, the old file is kept under sources/snapshots/<date it was fetched>/
before being replaced, so revisions build up over time.

Run: uv run python -m jobs_prices_pipeline.fetch [--force]
"""

import hashlib
import json
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import re

from .sources import API, CPI2024_RELEASES, PAGE_LIMIT, queries

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "sources" / "raw"
SNAPSHOTS = ROOT / "sources" / "snapshots"
MANIFEST = ROOT / "sources" / "manifest.json"
HEADERS = {"User-Agent": "india-data-review-data-pipeline/0.1 (python-urllib)"}
SOURCE = "Ministry of Statistics and Programme Implementation (MoSPI), official data API"

# api.mospi.gov.in needs TLS legacy renegotiation, which Python turns off by default.
# Certificates are still verified.
_CTX = ssl.create_default_context()
_CTX.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(url: str, tries: int = 5) -> bytes:
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120, context=_CTX) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == tries - 1:
                raise
            print(f"  retry {attempt + 1} for {url}: {exc}")
            time.sleep(5 * (attempt + 1))
    raise AssertionError


def url_for(path: str, params: dict, **extra) -> str:
    return f"{API}/{path}?{urllib.parse.urlencode({**params, 'Format': 'JSON', **extra})}"


def fetch_query(path: str, params: dict) -> dict:
    """Every row for one query, across all pages."""
    rows: list[dict] = []
    page, total = 1, None
    while True:
        body = json.loads(get(url_for(path, params, limit=PAGE_LIMIT, page=page)))
        data = body.get("data") or []
        meta = body.get("meta_data") or {}
        if total is None:
            total = meta.get("totalRecords") or 0
        rows += data
        if not data or page >= (meta.get("totalPages") or 1):
            break
        if page % 20 == 0:
            print(f"  {path} {params}: page {page} of {meta.get('totalPages')}", flush=True)
        page += 1
        time.sleep(0.3)
    if len(rows) != total:
        raise RuntimeError(f"{path} {params}: got {len(rows)} rows, API says {total}")
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    return {"source": SOURCE, "query": {"endpoint": path, **params}, "url": url_for(path, params),
            "total_records": len(rows), "rows": rows}


def encode(result: dict) -> bytes:
    """JSON with one row per line."""
    head = {k: v for k, v in result.items() if k != "rows"}
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in result["rows"]]
    text = json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "rows": [\n' + ",\n".join(lines) + "\n ]\n}\n"
    assert json.loads(text) == result
    return text.encode()


def save(manifest: dict, key: str, dest: Path, content: bytes, url: str, extra: dict | None = None) -> bool:
    """Write the file and its manifest entry. Keeps the previous version if it changed. Returns True if new/changed."""
    sha = hashlib.sha256(content).hexdigest()
    old = manifest.get(key)
    if old and old.get("sha256") == sha and dest.exists():
        old["checked_at"] = now()
        return False
    history = old.get("history", []) if old else []
    if old and old.get("sha256") and dest.exists():
        snap = SNAPSHOTS / old["fetched_at"][:10] / dest.relative_to(RAW)
        snap.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, snap)
        history.append({"sha256": old["sha256"], "fetched_at": old["fetched_at"], "file": str(snap.relative_to(ROOT))})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    manifest[key] = {
        "url": url,
        "file": str(dest.relative_to(ROOT)),
        "sha256": sha,
        "bytes": len(content),
        "fetched_at": now(),
        **(extra or {}),
        **({"history": history} if history else {}),
    }
    return True


def release_content(html: str) -> str:
    """The press release itself, cut from the PIB page: from its title to just before the page's visitor counter
    and language links, which change on every visit. Keeping only this makes an unchanged release give the
    same file (and SHA-256)."""
    i = html.find("CONSUMER PRICE INDEX ON BASE 2024")
    if i < 0:
        raise RuntimeError("release title not found")
    start = html.rfind("<", 0, i)
    end = html.find('<div id="reel_pic">', i)
    if end < 0:
        raise RuntimeError("end of release not found")
    return html[start:end].strip() + "\n"


def fetch_cpi2024(manifest: dict, force: bool) -> None:
    """Each month's CPI (base 2024) press release on PIB: the release's text and tables, and its PDF where it has one."""
    for month, page in CPI2024_RELEASES.items():
        key = f"cpi2024/{month}"
        if key in manifest and not force:
            continue
        html = get(page).decode("utf-8", "ignore")
        content = release_content(html).encode()
        changed = save(manifest, key, RAW / f"{key}.html", content, page)
        print(f"{key}: release page, {len(content):,} bytes{' (changed)' if changed else ''}", flush=True)
        links = sorted(set(re.findall(r"https://static\.pib\.gov\.in/WriteReadData/specificdocs/documents/[^\"'&\s]+\.pdf", html)))
        if len(links) > 1:
            raise RuntimeError(f"{key}: more than one PDF on {page}: {links}")
        if links:
            pdf = get(links[0])
            if not pdf.startswith(b"%PDF"):
                raise RuntimeError(f"{key}: {links[0]} is not a PDF")
            save(manifest, f"{key}/pdf", RAW / f"{key}.pdf", pdf, links[0], {"release_page": page})
            print(f"{key}: PDF {len(pdf):,} bytes", flush=True)
        else:
            manifest[f"{key}/pdf"] = {"url": page, "empty": True, "note": "no PDF attached to this release", "checked_at": now()}
        time.sleep(1)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def write_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=1, ensure_ascii=False) + "\n")


def main(force: bool = False) -> None:
    manifest = load_manifest()
    try:
        for key, path, params in queries():
            if key in manifest and not force:
                continue
            result = fetch_query(path, params)
            if not result["rows"]:
                manifest[key] = {"url": result["url"], "empty": True, "checked_at": now()}
                print(f"{key}: no data")
                continue
            changed = save(manifest, key, RAW / f"{key}.json", encode(result), result["url"],
                           {"records": result["total_records"]})
            print(f"{key}: {result['total_records']} rows{' (changed)' if changed else ''}", flush=True)
            write_manifest(manifest)
            time.sleep(0.3)
        fetch_cpi2024(manifest, force)
    finally:
        write_manifest(manifest)


if __name__ == "__main__":
    main(force="--force" in sys.argv)

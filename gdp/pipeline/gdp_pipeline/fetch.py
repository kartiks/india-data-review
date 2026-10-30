"""Download every source file and record it in sources/manifest.json.

National accounts: one file per (base year, series, frequency, indicator), with
every page of the API response combined, saved as
sources/raw/nas/<base>/<series>/<frequency>/ind<NN>.json. Rows are sorted so an
unchanged dataset gives an identical file (and SHA-256).

MoSPI's API keeps only the latest estimate for the new 2022-23 series and for
quarters. So when a re-download differs from the saved file, the old file is
kept under sources/snapshots/<date it was fetched>/ before being replaced: run
after every release and the revision history builds up.

Run: uv run python -m gdp_pipeline.fetch [--force]
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

from .sources import BUDGETS, NAS_API, NAS_INDICATORS, NAS_PAGE_LIMIT, NAS_SERIES, budget_glance_urls, fy

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "sources" / "raw"
SNAPSHOTS = ROOT / "sources" / "snapshots"
MANIFEST = ROOT / "sources" / "manifest.json"
HEADERS = {"User-Agent": "india-gdp-review-data-pipeline/0.1 (python-urllib)"}

# api.mospi.gov.in needs TLS legacy renegotiation, which Python turns off by default.
# Certificates are still verified.
_CTX = ssl.create_default_context()
_CTX.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(url: str, tries: int = 4) -> bytes:
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120, context=_CTX) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == tries - 1:
                raise
            print(f"  retry {attempt + 1} for {url}: {exc}")
            time.sleep(3 * (attempt + 1))
    raise AssertionError


def nas_query(base: str, series: str, freq: str, code: int) -> dict:
    return {"base_year": base, "series": series, "frequency_code": freq, "indicator_code": code}


def fetch_nas(base: str, series: str, freq: str, code: int) -> dict:
    """Every row for one indicator, across all pages."""
    query = nas_query(base, series, freq, code)
    rows: list[dict] = []
    page, total = 1, None
    while True:
        url = f"{NAS_API}?{urllib.parse.urlencode({**query, 'limit': NAS_PAGE_LIMIT, 'page': page})}"
        body = json.loads(get(url))
        data = body.get("data") or []
        meta = body.get("meta_data") or {}
        if total is None:
            total = meta.get("totalRecords", 0)
        rows += data
        if not data or page >= meta.get("totalPages", 1):
            break
        page += 1
        time.sleep(0.3)
    if len(rows) != (total or 0):
        raise RuntimeError(f"{query}: got {len(rows)} rows, API says {total}")
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    return {
        "source": "Ministry of Statistics and Programme Implementation (MoSPI), National Accounts Statistics API",
        "query": query,
        "url": f"{NAS_API}?{urllib.parse.urlencode(query)}",
        "total_records": len(rows),
        "rows": rows,
    }


def save(manifest: dict, key: str, dest: Path, content: bytes, url: str, extra: dict | None = None) -> bool:
    """Write the file and its manifest entry. Keeps the previous version if it changed. Returns True if new/changed."""
    sha = hashlib.sha256(content).hexdigest()
    old = manifest.get(key)
    if old and old["sha256"] == sha and dest.exists():
        old["checked_at"] = now()
        return False
    history = old.get("history", []) if old else []
    if old and dest.exists():
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


def fetch_all_nas(manifest: dict, force: bool) -> None:
    for base, series, freq in NAS_SERIES:
        for code in NAS_INDICATORS:
            key = f"nas/{base}/{series}/{freq}/ind{code:02d}"
            if key in manifest and not force:
                continue
            result = fetch_nas(base, series, freq, code)
            if not result["rows"]:
                manifest[key] = {"url": result["url"], "empty": True, "checked_at": now()}
                print(f"{key}: no data")
                continue
            content = (json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode()
            changed = save(manifest, key, RAW / f"{key}.json", content, result["url"], {"records": result["total_records"]})
            print(f"{key}: {result['total_records']} rows{' (changed)' if changed else ''}")
            time.sleep(0.3)


def fetch_budgets(manifest: dict, force: bool) -> None:
    for start in BUDGETS:
        key = f"budget/{fy(start)}/bag1"
        if key in manifest and not force:
            continue
        for url in budget_glance_urls(start):
            try:
                content = get(url)
            except urllib.error.HTTPError as exc:
                print(f"{key}: {url} -> {exc.code}")
                continue
            if not content.startswith(b"%PDF"):
                print(f"{key}: {url} is not a PDF")
                continue
            save(manifest, key, RAW / f"{key}.pdf", content, url)
            print(f"{key}: saved ({len(content):,} bytes)")
            break
        else:
            print(f"{key}: NO SOURCE FOUND")
        time.sleep(0.5)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def write_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(dict(sorted(manifest.items())), indent=1, ensure_ascii=False) + "\n")


def main(force: bool = False) -> None:
    manifest = load_manifest()
    try:
        fetch_all_nas(manifest, force)
        fetch_budgets(manifest, force)
        from . import forecasts

        forecasts.fetch(manifest, force)
    finally:
        write_manifest(manifest)


if __name__ == "__main__":
    main(force="--force" in sys.argv)

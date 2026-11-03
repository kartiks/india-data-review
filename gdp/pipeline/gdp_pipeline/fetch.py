"""Download every source file and record it in sources/manifest.json.

National accounts: one file per (base year, series, frequency, indicator), with
every page of the API response combined, saved as
sources/raw/nas/<base>/<series>/<frequency>/ind<NN>.json. Rows are sorted so an
unchanged dataset gives an identical file (and SHA-256).

MoSPI's API keeps only the latest estimate for the new 2022-23 series and for
quarters. So when a re-download differs from the saved file, the old file is
kept under sources/snapshots/<date it was fetched>/ before being replaced: run
after every release and the revision history builds up.

Run: uv run python -m gdp_pipeline.fetch [--force | --force-nas]
"""

import json
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

from pipeline_common import download
from pipeline_common.download import fetch_pages, get, is_type, now

from .sources import (BUDGETS, NAS_API, NAS_INDICATORS, NAS_PAGE_LIMIT, NAS_SERIES, STATE_INDICATORS, STATE_SERIES,
                      budget_glance_urls, fy)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "sources" / "raw"
SNAPSHOTS = ROOT / "sources" / "snapshots"
MANIFEST = ROOT / "sources" / "manifest.json"


def save(manifest: dict, key: str, dest: Path, content: bytes, url: str, extra: dict | None = None) -> bool:
    """Write the file and its manifest entry, keeping the previous version as a snapshot if it changed (see
    pipeline_common.download.save), then the manifest: a run cut short keeps what it downloaded. Returns True if
    new/changed."""
    changed = download.save(manifest, key, dest, content, url, extra, root=ROOT, raw=RAW, snapshots=SNAPSHOTS)
    write_manifest(manifest)
    return changed


def load_manifest() -> dict:
    return download.load_manifest(MANIFEST)


def write_manifest(manifest: dict) -> None:
    download.write_manifest(MANIFEST, manifest)


def nas_query(base: str, series: str, freq: str, code: int) -> dict:
    return {"base_year": base, "series": series, "frequency_code": freq, "indicator_code": code}


def fetch_nas(base: str, series: str, freq: str, code: int) -> dict:
    """Every row for one indicator, across all pages."""
    query = nas_query(base, series, freq, code)

    def page_url(page: int) -> str:
        return f"{NAS_API}?{urllib.parse.urlencode({**query, 'limit': NAS_PAGE_LIMIT, 'page': page})}"

    rows = fetch_pages(page_url, str(query))
    return {
        "source": "Ministry of Statistics and Programme Implementation (MoSPI), National Accounts Statistics API",
        "query": query,
        "url": f"{NAS_API}?{urllib.parse.urlencode(query)}",
        "total_records": len(rows),
        "rows": rows,
    }


def nas_queries():
    """(base, series, frequency, indicator code) for every national and state query."""
    for base, series, freq in NAS_SERIES:
        for code in NAS_INDICATORS:
            yield base, series, freq, code
    for base, series, freq in STATE_SERIES:
        for code in STATE_INDICATORS:
            yield base, series, freq, code


def fetch_all_nas(manifest: dict, force: bool) -> None:
    vanished = []
    for base, series, freq, code in nas_queries():
        key = f"nas/{base}/{series}/{freq}/ind{code:02d}"
        if key in manifest and not force:
            continue
        result = fetch_nas(base, series, freq, code)
        if not result["rows"]:
            if manifest.get(key, {}).get("sha256"):
                # Data MoSPI served before has gone: most likely a fault on their side, not a revision.
                # Keep the saved file, fetch the rest, and fail at the end.
                print(f"{key}: NO ROWS, but it had data before; keeping the saved file")
                vanished.append(key)
                continue
            manifest[key] = {"url": result["url"], "empty": True, "checked_at": now()}
            print(f"{key}: no data")
            continue
        content = (json.dumps(result, ensure_ascii=False, indent=1) + "\n").encode()
        changed = save(manifest, key, RAW / f"{key}.json", content, result["url"], {"records": result["total_records"]})
        print(f"{key}: {result['total_records']} rows{' (changed)' if changed else ''}")
        time.sleep(0.3)
    if vanished:
        raise RuntimeError(f"MoSPI returned no rows for indicators that had data: {', '.join(vanished)}")


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
            if not is_type(content, "pdf"):
                print(f"{key}: {url} is not a PDF")
                continue
            save(manifest, key, RAW / f"{key}.pdf", content, url)
            print(f"{key}: saved ({len(content):,} bytes)")
            break
        else:
            print(f"{key}: NO SOURCE FOUND")
        time.sleep(0.5)


def main(force: bool = False, force_nas: bool = False) -> None:
    """force: re-download everything. force_nas: re-download only the MoSPI API files (they are the ones that
    change after a release; budget, forecast and population documents are fixed), and anything else that is
    missing."""
    manifest = load_manifest()
    try:
        fetch_all_nas(manifest, force or force_nas)
        fetch_budgets(manifest, force)
        from . import forecasts, population

        forecasts.fetch(manifest, force)
        population.fetch(manifest, force)
    finally:
        write_manifest(manifest)


if __name__ == "__main__":
    main(force="--force" in sys.argv, force_nas="--force-nas" in sys.argv)

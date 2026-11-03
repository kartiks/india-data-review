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

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

from pipeline_common import download
from pipeline_common.download import fetch_pages, get, is_type, now

from . import forecasts, population_read
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


def fetch_forecasts(manifest: dict, force: bool) -> None:
    """Every document a forecast is quoted from (forecasts.py)."""
    for name in forecasts.SOURCES:
        for r in forecasts.load(name):
            for url in forecasts.urls(r):
                key = forecasts.doc_key(url)
                if key in manifest and not force:
                    continue
                try:
                    content = get(url)
                except Exception as exc:  # noqa: BLE001 - report and carry on; the check will fail
                    print(f"{key}: {url} -> {exc}")
                    continue
                ext = "pdf" if is_type(content, "pdf") else "html"
                save(manifest, key, RAW / f"{key}.{ext}", content, url, {"document": f"{name} {r['fiscal_year']}"})
                print(f"{key}: saved {url} ({len(content):,} bytes)")
                time.sleep(0.5)


def fetch_population(manifest: dict, force: bool) -> None:
    """The documents population is read from (population_read.py). NAS statements are added by hand (add_by_hand)."""
    for n in population_read.NAS_STATEMENTS:  # downloaded by hand: never fetched, only reported if missing
        if n["key"] not in manifest:
            print(f"{n['key']}: not added. Download it from {n['url']} and run "
                  "`uv run python -m gdp_pipeline.population --add <file>` (gdp/README.md).")

    for key, url, ext in population_read.documents():
        if key in manifest and not force:
            continue
        try:
            content = get(url)
        except Exception as exc:  # noqa: BLE001 - report and carry on; the checks will fail
            print(f"{key}: {url} -> {exc}")
            continue
        if not is_type(content, ext):
            print(f"{key}: {url} is not a {ext} file (a web page or an error); not saved")
            continue
        save(manifest, key, RAW / f"{key}.{ext}", content, url)
        print(f"{key}: saved {url} ({len(content):,} bytes)")


def add_by_hand(source: Path, key: str, replace: bool = False) -> None:
    """Copy a hand-downloaded NAS statement into sources/ and record it in the manifest. Refuses to put a different
    file under an edition that already has one (add the new edition to NAS_STATEMENTS first), unless replace."""
    n = next(x for x in population_read.NAS_STATEMENTS if x["key"] == key)
    if not source.is_file():
        raise SystemExit(f"{source}: no such file")
    content = source.read_bytes()
    if not is_type(content, "xlsx"):
        raise SystemExit(f"{source} is not an xlsx file")
    manifest = load_manifest()
    old = manifest.get(key)
    if old and old.get("sha256") != hashlib.sha256(content).hexdigest() and not replace:
        raise SystemExit(f"{key} already holds another file ({old.get('file_name') or old['file']}). For a new edition, "
                         "add its entry to NAS_STATEMENTS in population_read.py first; to replace this one, pass "
                         "--replace.")
    changed = save(manifest, key, RAW / f"{key}.xlsx", content, n["url"],
                   {"downloaded_by_hand": f"from {n['url']} (the publication page needs a browser)",
                    "file_name": source.name})
    write_manifest(manifest)
    print(f"{key}: {'added' if changed else 'unchanged'} {source} ({len(content):,} bytes)")


def main(force: bool = False, force_nas: bool = False) -> None:
    """force: re-download everything. force_nas: re-download only the MoSPI API files (they are the ones that
    change after a release; budget, forecast and population documents are fixed), and anything else that is
    missing."""
    manifest = load_manifest()
    try:
        fetch_all_nas(manifest, force or force_nas)
        fetch_budgets(manifest, force)
        fetch_forecasts(manifest, force)
        fetch_population(manifest, force)
    finally:
        write_manifest(manifest)


if __name__ == "__main__":
    main(force="--force" in sys.argv, force_nas="--force-nas" in sys.argv)

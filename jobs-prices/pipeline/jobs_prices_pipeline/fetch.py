"""Download every source file and record it in sources/manifest.json.

One file per query in sources.queries(), with every page of the API response
combined, saved as sources/raw/<key>.json. Rows are sorted and written one per
line, so an unchanged dataset gives an identical file (and SHA-256) and a
changed one gives a readable diff.

MoSPI's API keeps only the latest figures. When a re-download differs from the
saved file, the old file is kept under sources/snapshots/<time it was fetched>/
(UTC, e.g. 2026-11-06T093000Z)
before being replaced, so revisions build up over time. A re-download with no
rows, or with more than 5% fewer rows than the saved file, is more likely a
fault than a revision: the saved file is kept, the rest is downloaded, and the
run fails at the end. Rows listed in sources.WITHDRAWN are the exception: MoSPI
took them out, the build keeps them from the earlier download, and they do not
count as missing.

Run: uv run python -m jobs_prices_pipeline.fetch [--refresh | --refresh-api]   (downloads only; see __main__.py)
"""

import json
import logging
import re
import time
import urllib.parse
from pathlib import Path

from pipeline_common import cli, download
from pipeline_common import log as pipeline_log
from pipeline_common.download import PAGE_PAUSE_S, POLITE_PAUSE_S, RELEASE_PAUSE_S, fetch_pages, file_kind, get, now

from .common import matches
from .sources import API, CPI2024_RELEASES, HCES_REPORT_TABLES, PAGE_LIMIT, WITHDRAWN, queries

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "sources" / "raw"
SNAPSHOTS = ROOT / "sources" / "snapshots"
MANIFEST = ROOT / "sources" / "manifest.json"
log = logging.getLogger(__name__)

SOURCE = "Ministry of Statistics and Programme Implementation (MoSPI), official data API"


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


def url_for(path: str, params: dict, **extra) -> str:
    return f"{API}/{path}?{urllib.parse.urlencode({**params, 'Format': 'JSON', **extra})}"


def fetch_query(path: str, params: dict) -> dict:
    """Every row for one query, across all pages."""
    rows = fetch_pages(lambda page: url_for(path, params, limit=PAGE_LIMIT, page=page), f"{path} {params}")
    return {"source": SOURCE, "query": {"endpoint": path, **params}, "url": url_for(path, params),
            "total_records": len(rows), "rows": rows}


def withdrawn_count(key: str, rows: list[dict]) -> int:
    """How many of the rows listed in sources.WITHDRAWN the saved file has and this download lacks. The build keeps
    them from the earlier download, so the download is not short by them."""
    fields = WITHDRAWN.get(key)
    saved = RAW / f"{key}.json"
    if not fields or not saved.exists() or any(matches(r, fields) for r in rows):
        return 0
    return sum(matches(r, fields) for r in json.loads(saved.read_text())["rows"])


def encode(result: dict) -> bytes:
    """JSON with one row per line."""
    head = {k: v for k, v in result.items() if k != "rows"}
    lines = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in result["rows"]]
    text = json.dumps(head, ensure_ascii=False, indent=1)[:-2] + ',\n "rows": [\n' + ",\n".join(lines) + "\n ]\n}\n"
    assert json.loads(text) == result
    return text.encode()


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
    """Each month's CPI (base 2024) press release on PIB: the release's text and tables, and its PDF where it has one.
    The PDF is downloaded and checked before anything is saved, and the release page is recorded last, so a release
    whose PDF failed is not in the manifest and is fetched again by the next run."""
    for month, page in CPI2024_RELEASES.items():
        key = f"cpi2024/{month}"
        if key in manifest and f"{key}/pdf" in manifest and not force:
            continue
        html = get(page).decode("utf-8", "ignore")
        content = release_content(html).encode()
        links = sorted(set(re.findall(r"https://static\.pib\.gov\.in/WriteReadData/specificdocs/documents/[^\"'&\s]+\.pdf", html)))
        if len(links) > 1:
            raise RuntimeError(f"{key}: more than one PDF on {page}: {links}")
        if links:
            pdf = get(links[0])
            if file_kind(pdf) != "pdf":  # stop: a release without its PDF must not be saved
                raise RuntimeError(f"{key}: {links[0]} is not a PDF")
            save(manifest, f"{key}/pdf", RAW / f"{key}.pdf", pdf, links[0], {"release_page": page})
            log.info(f"{key}: PDF {len(pdf):,} bytes")
        else:
            manifest[f"{key}/pdf"] = {"url": page, "empty": True, "note": "no PDF attached to this release", "checked_at": now()}
        changed = save(manifest, key, RAW / f"{key}.html", content, page)
        log.info(f"{key}: release page, {len(content):,} bytes{' (changed)' if changed else ''}")
        time.sleep(RELEASE_PAUSE_S)


def fetch_hces_tables(manifest: dict, force: bool) -> None:
    """Excel tables from MoSPI's full HCES report."""
    for name, url in HCES_REPORT_TABLES.items():
        key = f"hces_report/{name}"
        if key in manifest and not force:
            continue
        content = get(url)
        if file_kind(content) != "xlsx":  # stop: these tables are required
            raise RuntimeError(f"{key}: {url} is not an Excel file")
        changed = save(manifest, key, RAW / f"{key}.xlsx", content, url)
        log.info(f"{key}: {len(content):,} bytes{' (changed)' if changed else ''}")


def fetch_rbi(manifest: dict, force: bool) -> None:
    """The RBI Handbook of Statistics on Indian States: the tables in rbi.RBI_STATE_TABLES, from the latest edition."""
    from . import rbi

    if not force and all(f"rbi/table{n:03d}" in manifest for n in rbi.RBI_STATE_TABLES):
        return
    edition, links = rbi.table_links(get(rbi.HANDBOOK_PAGE).decode("utf-8", "ignore"))
    for n, spec in rbi.RBI_STATE_TABLES.items():
        key = f"rbi/table{n:03d}"
        if key in manifest and not force:
            continue
        if n not in links:
            raise RuntimeError(f"{key}: table {n} not on the handbook page")
        title, url = links[n]
        if spec.words not in title.upper():
            raise RuntimeError(f"{key}: expected a title with {spec.words!r}, found {title!r}")
        content = get(url)
        if file_kind(content) != "xlsx":  # stop: these tables are required
            raise RuntimeError(f"{key}: {url} is not an Excel file")
        changed = save(manifest, key, RAW / f"{key}.xlsx", content, url,
                       {"edition": edition, "title": title, "page": rbi.HANDBOOK_PAGE})
        log.info(f"{key}: {title} ({edition}){' (changed)' if changed else ''}")
        time.sleep(POLITE_PAUSE_S)


def main(force: bool = False, force_api: bool = False) -> None:
    """force: re-download everything. force_api: re-download only what is published as data and revised in place
    (MoSPI's API and the RBI handbook tables), and anything else that is missing. Press releases and report tables
    are fixed documents."""
    manifest = load_manifest()
    vanished, dropped = [], []
    try:
        for key, path, params in queries():
            if key in manifest and not (force or force_api):
                continue
            result = fetch_query(path, params)
            if not result["rows"]:
                if manifest.get(key, {}).get("sha256"):
                    # Data MoSPI served before has gone: most likely a fault on their side, not a revision.
                    # Keep the saved file, fetch the rest, and fail at the end.
                    log.warning(f"{key}: NO ROWS, but it had data before; keeping the saved file")
                    vanished.append(key)
                    continue
                manifest[key] = {"url": result["url"], "empty": True, "checked_at": now()}
                log.info(f"{key}: no data")
                continue
            try:  # far fewer rows than before: kept, like a vanished query (rows MoSPI withdrew do not count)
                download.check_records(manifest, key, result["total_records"] + withdrawn_count(key, result["rows"]))
            except download.RecordsDropped as e:
                log.warning(str(e))
                dropped.append(str(e))
                continue
            changed = save(manifest, key, RAW / f"{key}.json", encode(result), result["url"],
                           {"records": result["total_records"]})
            log.info(f"{key}: {result['total_records']} rows{' (changed)' if changed else ''}")
            time.sleep(PAGE_PAUSE_S)
        fetch_cpi2024(manifest, force)
        fetch_hces_tables(manifest, force)
        fetch_rbi(manifest, force or force_api)
    finally:
        write_manifest(manifest)
    errors = [f"MoSPI returned no rows for queries that had data: {', '.join(vanished)}"] if vanished else []
    if errors := errors + dropped:
        raise RuntimeError("\n".join(errors))


if __name__ == "__main__":
    pipeline_log.setup(__package__)
    args = cli.parser(__doc__, fetch=False,
                      refresh_api="download again only MoSPI's API files and the RBI handbook tables").parse_args()
    main(force=args.refresh, force_api=args.refresh_api)

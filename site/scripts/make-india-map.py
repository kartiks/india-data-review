"""Make the simplified state outlines the site's maps use (src/data/india-states.json).

Source: DataMeet India community, "States/Admin2" shapefile (https://github.com/datameet/maps), licensed CC BY 4.0.
Its Jammu & Kashmir and Ladakh boundaries were updated "as per latest SOI Map" (Survey of India) in 2021, and it has
all 36 states and union territories after the 2020 merger of Dadra & Nagar Haveli and Daman & Diu.

Run (from site/), with the five Admin2.* files downloaded from that repository into a folder:

    uv run --with pyshp --with shapely python scripts/make-india-map.py <folder with Admin2.shp> <datameet commit sha>

Each outline is simplified to about 0.02 degrees (around 2 km; under a pixel at the site's map size) and coordinates
are rounded to 3 decimals. Tiny islands are dropped unless they are the largest part of their state (Lakshadweep).
"""

import hashlib
import json
import sys
from pathlib import Path

import shapefile  # pyshp
from shapely.geometry import MultiPolygon, Polygon, shape

TOLERANCE = 0.02  # degrees
MIN_AREA = 0.0004  # square degrees: smaller islands are dropped (the largest part of a state is always kept)
OUT = Path(__file__).resolve().parents[1] / "src" / "data" / "india-states.json"


def rings(geom) -> list[list[list[float]]]:
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    largest = max(polys, key=lambda p: p.area)
    out = []
    for p in polys:
        if p.area < MIN_AREA and p is not largest:
            continue
        s = p.simplify(TOLERANCE, preserve_topology=True)
        if s.is_empty:
            s = p
        for poly in (s.geoms if isinstance(s, MultiPolygon) else [s]):
            if not isinstance(poly, Polygon):
                continue
            ring = [[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords]
            if len(ring) >= 4:
                out.append(ring)
    return out


def main(folder: str, commit: str) -> None:
    base = Path(folder) / "Admin2"
    shp = base.with_suffix(".shp").read_bytes()
    reader = shapefile.Reader(str(base))
    states = []
    for sr in reader.shapeRecords():
        name = sr.record["ST_NM"].strip()
        states.append({"name": name, "rings": rings(shape(sr.shape.__geo_interface__))})
    states.sort(key=lambda s: s["name"])
    data = {
        "source": "DataMeet India community, States/Admin2 (https://github.com/datameet/maps/tree/"
                  f"{commit}/States), CC BY 4.0. Simplified for display.",
        "source_commit": commit,
        "source_sha256": hashlib.sha256(shp).hexdigest(),
        "tolerance_degrees": TOLERANCE,
        "states": states,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"{len(states)} states, {sum(len(s['rings']) for s in states)} rings, {OUT.stat().st_size:,} bytes -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

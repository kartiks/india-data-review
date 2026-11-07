// The site's areas, and where each one's verified data lives. The list is src/data/areas.json, which
// scripts/copy-data.mjs (the build gate) and ../scripts/ci.sh read too: a new area is added there. Each area is a
// folder of the repository, ../<id>, whose pipeline writes ../<id>/data. Only Node's own modules and erasable
// TypeScript, so that scripts/copy-data.mjs (plain Node) can import this file.
import fs from "node:fs";
import path from "node:path";
import AREA_LIST from "../data/areas.json" with { type: "json" };

export interface Area {
  id: string; // folder and URL path: /<id>/
  label: string; // tab and title text, e.g. "Budget"
  name: string; // full name, e.g. "Union Budget"
}
export const AREAS: readonly Area[] = AREA_LIST;
export const AREA_IDS: readonly string[] = AREAS.map((a) => a.id);

/** An area's data folder, or a file in it: ../<area>/data (the site is built, tested and run from the site folder). */
export function areaDataPath(area: string, ...file: string[]): string {
  return path.resolve(process.cwd(), "..", area, "data", ...file);
}

/** A text file from an area's data folder. */
export function readAreaText(area: string, file: string): string {
  return fs.readFileSync(areaDataPath(area, file), "utf8");
}

/** A JSON file from an area's data folder. */
export function readAreaJson<T>(area: string, file: string): T {
  return JSON.parse(readAreaText(area, file)) as T;
}

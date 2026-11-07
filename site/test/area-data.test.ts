// The list of areas (src/data/areas.json), which the site, its build gate, scripts/vercel-ignore-build.sh and
// ../scripts/ci.sh all read, and the paths to each area's data.
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { AREAS, AREA_IDS, areaDataPath, readAreaJson, readAreaText } from "../src/lib/area-data";
import { SUMMARY_FILE } from "../src/lib/validation";

const repo = path.resolve("..");

describe("AREAS", () => {
  it("names each area once, with a label and a full name", () => {
    expect(AREA_IDS.length).toBeGreaterThan(0);
    expect(new Set(AREA_IDS).size).toBe(AREA_IDS.length);
    for (const a of AREAS) {
      expect(a.id).toMatch(/^[a-z][a-z0-9-]*$/); // a folder name and a URL path
      expect(a.label).not.toBe("");
      expect(a.name).not.toBe("");
    }
  });
  it("lists exactly the repository folders that have a pipeline and data", () => {
    const folders = fs.readdirSync(repo).filter((d) =>
      fs.existsSync(path.join(repo, d, "pipeline")) && fs.existsSync(path.join(repo, d, "data")));
    expect([...AREA_IDS].sort()).toEqual(folders.sort());
  });
  it("has a page folder for each area", () => {
    for (const id of AREA_IDS) expect(fs.existsSync(path.join("src", "pages", id, "sources", "index.astro"))).toBe(true);
  });
});

describe("areaDataPath", () => {
  it("is the area's data folder beside the site folder, or a file in it", () => {
    expect(areaDataPath("gdp")).toBe(path.join(repo, "gdp", "data"));
    expect(areaDataPath("gdp", "gdp.json")).toBe(path.join(repo, "gdp", "data", "gdp.json"));
  });
});

describe("readAreaJson and readAreaText", () => {
  it("read a file from an area's data folder", () => {
    for (const id of AREA_IDS) {
      const text = readAreaText(id, SUMMARY_FILE);
      expect(readAreaJson<{ result: string }>(id, SUMMARY_FILE)).toEqual(JSON.parse(text));
    }
  });
  it("throw for a file that is not there", () => {
    expect(() => readAreaText("gdp", "no-such-file.json")).toThrow();
  });
});

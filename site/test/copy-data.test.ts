// The build gate in scripts/copy-data.mjs: an area's data goes live only if its checks passed on exactly these files.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { copyData, gateErrors, isPublished } from "../scripts/copy-data.mjs";
import { dataHash, REPORT_FILE, SUMMARY_FILE } from "../src/lib/validation";

let root: string, out: string;
beforeEach(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "copy-data-"));
  out = path.join(root, "out");
});
afterEach(() => fs.rmSync(root, { recursive: true, force: true }));

/** An area's data folder with one data file, a report, a file that is not published, and a summary saying `result`. */
function area(name: string, result: "PASSED" | "FAILED" | null = "PASSED"): string {
  const dir = path.join(root, name, "data");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "data.json"), '{"generated_at": "2026-01-01", "x": 1}');
  fs.writeFileSync(path.join(dir, "data.csv"), "a,b\n1,2\n");
  fs.writeFileSync(path.join(dir, REPORT_FILE), "# Report\n");
  fs.writeFileSync(path.join(dir, "notes.txt"), "not for download");
  fs.writeFileSync(path.join(dir, "data.xlsx"), "binary");
  if (result) {
    const failures = result === "PASSED" ? 0 : 1;
    const files = Object.fromEntries(["data.json", "data.csv"].map((f) => [f, dataHash(path.join(dir, f))]));
    fs.writeFileSync(path.join(dir, SUMMARY_FILE), JSON.stringify({
      result, checks: 3, failures, allowed: 0, files,
      sections: [{ title: "Checks", checks: 3, failures, allowed: 0, allowed_reasons: [] }],
    }));
  }
  return dir;
}
const quiet = () => {};

describe("isPublished", () => {
  it("publishes data files, the report and the summary, and nothing else", () => {
    for (const f of ["gdp.json", "state_accounts.csv", REPORT_FILE, SUMMARY_FILE]) expect(isPublished(f)).toBe(true);
    for (const f of ["data.xlsx", "notes.txt", ".DS_Store", "data.json.bak", "csv", "README"]) expect(isPublished(f)).toBe(false);
  });
});

describe("copyData", () => {
  it("copies an area that passed its checks, only its published files", () => {
    area("a");
    expect(copyData(root, out, ["a"], quiet)).toEqual([]);
    expect(fs.readdirSync(path.join(out, "a")).sort()).toEqual(["data.csv", "data.json", REPORT_FILE, SUMMARY_FILE].sort());
  });

  it("stops at an area whose checks FAILED and copies nothing of it", () => {
    area("a");
    area("b", "FAILED");
    const errors = copyData(root, out, ["a", "b"], quiet);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toMatch(`b/data/${SUMMARY_FILE} does not say PASSED`);
    expect(fs.existsSync(path.join(out, "a", "data.json"))).toBe(true);
    expect(fs.existsSync(path.join(out, "b"))).toBe(false);
  });

  it("stops at an area with no summary", () => {
    area("a", null);
    const errors = copyData(root, out, ["a"], quiet);
    expect(errors).toHaveLength(1);
    expect(errors[0]).toMatch(`a/data/${SUMMARY_FILE} could not be read`);
    expect(errors[0]).toMatch("run the a pipeline first");
    expect(fs.existsSync(path.join(out, "a"))).toBe(false);
  });

  it("empties the output folder first", () => {
    area("a");
    fs.mkdirSync(path.join(out, "old"), { recursive: true });
    copyData(root, out, ["a"], quiet);
    expect(fs.existsSync(path.join(out, "old"))).toBe(false);
  });
});

describe("gateErrors", () => {
  it("names a data file changed after its checks ran, and one they never saw", () => {
    const dir = area("a");
    fs.writeFileSync(path.join(dir, "data.csv"), "a,b\n1,3\n");
    fs.writeFileSync(path.join(dir, "extra.json"), "{}");
    const errors = gateErrors("a", dir);
    expect(errors).toContain("a/data/data.csv changed after its checks ran");
    expect(errors.some((e) => e.startsWith("a/data/extra.json was not checked"))).toBe(true);
    expect(errors[errors.length - 1]).toMatch("is not what its checks validated");
  });

  it("ignores a changed build time", () => {
    const dir = area("a");
    fs.writeFileSync(path.join(dir, "data.json"), '{"generated_at": "2026-11-06", "x": 1}');
    expect(gateErrors("a", dir)).toEqual([]);
  });
});

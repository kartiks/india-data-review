// Copy each verified dataset into public/data/<area> so visitors can download exactly what the site shows.
// Refuses to build the site from data that failed its checks (each area's data/validation_summary.json), or that
// changed after they ran (the summary's SHA-256 of each data file, build time aside, must match the file).
// Run as a script before every dev and build; the functions are exported for test/copy-data.test.ts.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AREA_IDS } from "../src/lib/area-data.ts";
import { dataMismatches, passed, readValidation, SUMMARY_FILE } from "../src/lib/validation.ts";

/** A file copied for download: the data files, the check report and its summary (.json, .csv or .md). */
export const isPublished = (name) => /\.(json|csv|md)$/.test(name);

/**
 * Why an area's data folder may not go live, one line each (none if it may): its summary is missing or unreadable,
 * does not say PASSED, or records hashes that do not match the files.
 * @param {string} area
 * @param {string} src the area's data folder
 * @returns {string[]}
 */
export function gateErrors(area, src) {
  let validation;
  try {
    validation = readValidation(src);
  } catch (err) {
    return [`${area}/data/${SUMMARY_FILE} could not be read (${err.message}): run the ${area} pipeline first.`];
  }
  if (!passed(validation)) {
    return [`${area}/data/${SUMMARY_FILE} does not say PASSED: run the ${area} pipeline and fix the failures first (see validation_report.md).`];
  }
  // The PASSED must be for these files: the summary records a hash of each data file its checks validated.
  const mismatches = dataMismatches(src, validation);
  if (mismatches.length) {
    return [
      ...mismatches.map((m) => `${area}/data/${m}`),
      `${area}/data/ is not what its checks validated: run the ${area} pipeline (it rebuilds data/ and checks it) and commit data/.`,
    ];
  }
  return [];
}

/**
 * Empty `out`, then check each area's `<root>/<area>/data` and copy its published files to `<out>/<area>`. Stops at
 * the first area that fails the gate and returns its errors (areas before it are already copied); none if all passed.
 * @param {string} root the folder holding the area folders (the repository)
 * @param {string} out
 * @param {string[]} areas
 * @param {(msg: string) => void} log
 * @returns {string[]}
 */
export function copyData(root, out, areas = AREA_IDS, log = console.log) {
  fs.rmSync(out, { recursive: true, force: true });
  for (const area of areas) {
    const src = path.join(root, area, "data");
    const dst = path.join(out, area);
    const errors = gateErrors(area, src);
    if (errors.length) return errors;
    fs.mkdirSync(dst, { recursive: true });
    for (const f of fs.readdirSync(src)) {
      if (isPublished(f)) fs.copyFileSync(path.join(src, f), path.join(dst, f));
    }
    log(`copied ${area} datasets to ${dst}`);
  }
  return [];
}

// Run as a script (not imported by the tests). Compare real paths, so a symlink in the path cannot skip the gate.
const real = (p) => fs.realpathSync(p);
if (process.argv[1] && real(path.resolve(process.argv[1])) === real(fileURLToPath(import.meta.url))) {
  const errors = copyData(path.resolve(".."), path.resolve("public", "data"));
  if (errors.length) {
    for (const e of errors) console.error(e);
    process.exit(1);
  }
}

// Copy each verified dataset into public/data/<area> so visitors can download exactly what the site shows.
// Refuses to build the site from data that failed its checks (each area's data/validation_summary.json), or that
// changed after they ran (the summary's SHA-256 of each data file, build time aside, must match the file).
import fs from "node:fs";
import path from "node:path";
import { dataMismatches, passed, readValidation, SUMMARY_FILE } from "../src/lib/validation.ts";

const AREAS = ["budget", "gdp", "jobs-prices"];
fs.rmSync(path.resolve("public", "data"), { recursive: true, force: true });
for (const area of AREAS) {
  const src = path.resolve("..", area, "data");
  const dst = path.resolve("public", "data", area);
  let validation;
  try {
    validation = readValidation(src);
  } catch (err) {
    console.error(`${area}/data/${SUMMARY_FILE} could not be read (${err.message}): run the ${area} pipeline first.`);
    process.exit(1);
  }
  if (!passed(validation)) {
    console.error(`${area}/data/${SUMMARY_FILE} does not say PASSED: run the ${area} pipeline and fix the failures first (see validation_report.md).`);
    process.exit(1);
  }
  // The PASSED must be for these files: the summary records a hash of each data file its checks validated.
  const mismatches = dataMismatches(src, validation);
  if (mismatches.length) {
    for (const m of mismatches) console.error(`${area}/data/${m}`);
    console.error(`${area}/data/ is not what its checks validated: run the ${area} pipeline (it rebuilds data/ and checks it) and commit data/.`);
    process.exit(1);
  }
  fs.mkdirSync(dst, { recursive: true });
  for (const f of fs.readdirSync(src)) {
    if (/\.(json|csv|md)$/.test(f)) fs.copyFileSync(path.join(src, f), path.join(dst, f));
  }
  console.log(`copied ${area} datasets to ${dst}`);
}

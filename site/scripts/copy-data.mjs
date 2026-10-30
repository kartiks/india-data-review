// Copy the verified datasets into public/data so visitors can download exactly what the site shows.
import fs from "node:fs";
import path from "node:path";
const src = path.resolve("..", "data");
const dst = path.resolve("public", "data");
// Refuse to build the site from data that failed its checks.
const report = fs.readFileSync(path.join(src, "validation_report.md"), "utf8");
if (!/\*\*Result: PASSED\*\*/.test(report)) {
  console.error("data/validation_report.md does not say PASSED: run the pipeline and fix the failures first.");
  process.exit(1);
}
fs.mkdirSync(dst, { recursive: true });
for (const f of fs.readdirSync(src)) {
  if (/\.(json|csv|md)$/.test(f)) fs.copyFileSync(path.join(src, f), path.join(dst, f));
}
console.log(`copied datasets to ${dst}`);

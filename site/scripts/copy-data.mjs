// Copy each verified dataset into public/data/<area> so visitors can download exactly what the site shows.
// Refuses to build the site from data that failed its checks.
import fs from "node:fs";
import path from "node:path";

const AREAS = ["budget", "gdp"];
fs.rmSync(path.resolve("public", "data"), { recursive: true, force: true });
for (const area of AREAS) {
  const src = path.resolve("..", area, "data");
  const dst = path.resolve("public", "data", area);
  const report = fs.readFileSync(path.join(src, "validation_report.md"), "utf8");
  if (!/\*\*Result: PASSED\*\*/.test(report)) {
    console.error(`${area}/data/validation_report.md does not say PASSED: run the ${area} pipeline and fix the failures first.`);
    process.exit(1);
  }
  fs.mkdirSync(dst, { recursive: true });
  for (const f of fs.readdirSync(src)) {
    if (/\.(json|csv|md)$/.test(f)) fs.copyFileSync(path.join(src, f), path.join(dst, f));
  }
  console.log(`copied ${area} datasets to ${dst}`);
}

// The result of each area's checks, from <area>/data/validation_summary.json. Each pipeline writes it next to
// validation_report.md (shared/pipeline/pipeline_common/report.py), so pages and the build gate read numbers here
// instead of parsing the report's wording. Only Node's own modules and erasable TypeScript, so that
// scripts/copy-data.mjs (plain Node) can import this file too.
import fs from "node:fs";
import path from "node:path";

export const SUMMARY_FILE = "validation_summary.json";

/** Exceptions allowed under one written reason. */
export interface AllowedReason { reason: string; cases: number }
/** One group of checks: a "## ✅ title" section of the report. */
export interface CheckGroup { title: string; checks: number; failures: number; allowed: number; allowed_reasons: AllowedReason[] }
export interface Validation {
  result: "PASSED" | "FAILED";
  checks: number;
  failures: number;
  allowed: number; // cases allowed with a written reason, in the groups that count them
  sections: CheckGroup[];
}

/** The summary in an area's data folder. Throws if it is missing or not a validation summary. */
export function readValidation(dataDir: string): Validation {
  const file = path.join(dataDir, SUMMARY_FILE);
  const v = JSON.parse(fs.readFileSync(file, "utf8"));
  if ((v.result !== "PASSED" && v.result !== "FAILED") || typeof v.checks !== "number" || !Array.isArray(v.sections)) {
    throw new Error(`${file} is not a validation summary`);
  }
  return v as Validation;
}

/** An area's summary, read from ../<area>/data (the site is built from the site folder). */
export function validation(area: string): Validation {
  return readValidation(path.resolve(process.cwd(), "..", area, "data"));
}

export function passed(v: Validation): boolean {
  return v.result === "PASSED" && v.failures === 0;
}

/** How many cases are allowed under the reasons that start with `start`. */
export function allowedCases(v: Validation, start: string): number {
  return v.sections.flatMap((s) => s.allowed_reasons).filter((a) => a.reason.startsWith(start)).reduce((n, a) => n + a.cases, 0);
}

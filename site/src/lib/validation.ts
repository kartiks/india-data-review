// The result of each area's checks, from <area>/data/validation_summary.json. Each pipeline writes it next to
// validation_report.md (shared/pipeline/pipeline_common/report.py), so pages and the build gate read numbers here
// instead of parsing the report's wording. Only Node's own modules and erasable TypeScript, so that
// scripts/copy-data.mjs (plain Node) can import this file too.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export const SUMMARY_FILE = "validation_summary.json";
export const REPORT_FILE = "validation_report.md";

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
  files?: Record<string, string>; // file name -> SHA-256 of each data file the checks validated (see dataHash)
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

/** A data file whose hash the summary records: .json, .csv or .md, apart from the report and the summary. */
export function isDataFile(name: string): boolean {
  return /\.(json|csv|md)$/.test(name) && name !== SUMMARY_FILE && name !== REPORT_FILE;
}

/**
 * SHA-256 of a data file with every "generated_at" field (the build time) removed, as
 * shared/pipeline/pipeline_common/report.py works it out: rebuilding the same data changes no hash.
 */
export function dataHash(file: string): string {
  // latin1 maps each byte to one character and back, so only the matched bytes are removed.
  const text = fs.readFileSync(file).toString("latin1").replace(/"generated_at": ?"[^"]*"/g, "");
  return crypto.createHash("sha256").update(Buffer.from(text, "latin1")).digest("hex");
}

/**
 * Every way the data files in dataDir differ from the ones the checks validated, one line each (none if they
 * match): a file changed since, missing, or not checked at all.
 */
export function dataMismatches(dataDir: string, v: Validation): string[] {
  if (!v.files || typeof v.files !== "object") return [`${SUMMARY_FILE} records no file hashes`];
  const out: string[] = [];
  for (const [name, hash] of Object.entries(v.files)) {
    const file = path.join(dataDir, name);
    if (!fs.existsSync(file)) out.push(`${name} is missing`);
    else if (dataHash(file) !== hash) out.push(`${name} changed after its checks ran`);
  }
  for (const name of fs.readdirSync(dataDir).sort()) {
    if (isDataFile(name) && fs.statSync(path.join(dataDir, name)).isFile() && !Object.hasOwn(v.files, name)) {
      out.push(`${name} was not checked (it is not in ${SUMMARY_FILE})`);
    }
  }
  return out;
}

export function passed(v: Validation): boolean {
  return v.result === "PASSED" && v.failures === 0 && v.sections.every((s) => s.failures === 0);
}

/** How many cases are allowed under the reasons that start with `start`. */
export function allowedCases(v: Validation, start: string): number {
  return v.sections.flatMap((s) => s.allowed_reasons).filter((a) => a.reason.startsWith(start)).reduce((n, a) => n + a.cases, 0);
}

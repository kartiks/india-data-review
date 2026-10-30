// Build-time access to the verified datasets in ../data (produced by the pipeline).
// Nothing here changes a number: it only picks, sums and labels published values.
import fs from "node:fs";
import path from "node:path";

const DATA_DIR = path.resolve(process.cwd(), "..", "data");
const load = <T>(name: string): T => JSON.parse(fs.readFileSync(path.join(DATA_DIR, name), "utf8"));

export type Kind = "be" | "re" | "actual";
export const KIND_LABEL: Record<Kind, string> = {
  be: "Budget Estimate",
  re: "Revised Estimate",
  actual: "Actual",
};
export const KIND_SHORT: Record<Kind, string> = { be: "BE", re: "RE", actual: "Actual" };

export interface Source {
  budget: string; // budget the number was printed in, e.g. "2026-27"
  document: string; // human name of the table
  url?: string;
  label?: string; // line label as printed
  note?: string;
}
export interface Value {
  value: number;
  kind: Kind;
  source: Source;
  pctGdp?: number | null;
}

// ---------- raw files ----------
interface FiscalItem {
  value: number;
  pct_gdp: number | null;
  source_budget: string;
  label_as_printed: string;
  note?: string;
}
interface FiscalJson {
  fields: Record<string, string>;
  sources: Record<string, Record<string, { url: string }>>;
  years: Record<string, Record<string, Partial<Record<Kind | "be_restated", FiscalItem>>>>;
}
interface DetailItem {
  source_budget: string;
  document?: string;
  label_as_printed?: string;
  source_url?: string;
  note?: string;
  [k: string]: unknown;
}
interface DetailJson {
  items: Record<string, any>;
  years: Record<string, Record<string, Partial<Record<Kind | "be_restated", DetailItem>>>>;
}

const fiscal = load<FiscalJson>("fiscal.json");
const taxes = load<DetailJson>("taxes.json");
const ministries = load<DetailJson>("ministries.json");
const schemes = load<DetailJson>("schemes.json");

export const YEARS = Object.keys(fiscal.years).sort();
export const LATEST_YEAR = YEARS[YEARS.length - 1];
export const KINDS: Kind[] = ["be", "re", "actual"];

const DOC_NAMES: Record<string, string> = {
  summary: "Budget at a Glance",
  receipts: "Budget at a Glance, Receipts",
  receipt_budget: "Receipt Budget, Annex 7",
  ministries: "Expenditure Budget / Expenditure Profile, Statement on ministries",
  css: "Expenditure Profile, Statement 4A (Centrally Sponsored Schemes)",
  central_sector: "Expenditure Profile, Statement 4B (Central Sector Schemes)",
};

function fiscalSourceUrl(budget: string): string | undefined {
  const files = fiscal.sources[budget] ?? {};
  return (files.pdf ?? files.xlsx ?? files.xls ?? files.htm)?.url;
}

// ---------- headline figures ----------
export const FIELD_LABELS = fiscal.fields;

export function headline(year: string, field: string, kind: Kind): Value | undefined {
  const it = fiscal.years[year]?.[field]?.[kind];
  if (!it) return undefined;
  return {
    value: it.value,
    kind,
    pctGdp: it.pct_gdp,
    source: {
      budget: it.source_budget,
      document: DOC_NAMES.summary,
      url: fiscalSourceUrl(it.source_budget),
      label: it.label_as_printed,
      note: it.note,
    },
  };
}

/** Actual if published, else Revised, else Budget Estimate. */
export function best<T extends Value>(get: (k: Kind) => T | undefined): T | undefined {
  return get("actual") ?? get("re") ?? get("be");
}
export const headlineBest = (year: string, field: string) => best((k) => headline(year, field, k));

/** The estimate type available for every dataset in a year: the one a year page shows. */
export function yearKind(year: string): Kind {
  for (const k of ["actual", "re", "be"] as Kind[]) {
    const ok =
      fiscal.years[year]?.total_expenditure?.[k] &&
      taxes.years[year]?.gross_tax_revenue?.[k] &&
      ministries.years[year]?.grand_total?.[k];
    if (ok) return k;
  }
  return "be";
}

// ---------- detailed tables ----------
function detail(
  table: DetailJson,
  year: string,
  id: string,
  kind: Kind,
  field: string,
): Value | undefined {
  const it = table.years[year]?.[id]?.[kind];
  const v = it?.[field];
  if (it == null || typeof v !== "number") return undefined;
  return {
    value: v,
    kind,
    source: {
      budget: it.source_budget,
      document: DOC_NAMES[it.document ?? ""] ?? String(it.document ?? ""),
      url: it.source_url,
      label: it.label_as_printed,
      note: it.note,
    },
  };
}
export const tax = (year: string, id: string, kind: Kind) => detail(taxes, year, id, kind, "value");

// ---------- taxes ----------
export const TAX_TYPES: { id: string; label: string }[] = [
  { id: "income_tax", label: "Income tax" },
  { id: "corporation_tax", label: "Corporation tax" },
  { id: "gst", label: "GST" },
  { id: "union_excise", label: "Excise duties" },
  { id: "customs", label: "Customs" },
  { id: "service_tax", label: "Service tax" },
];

/** Gross tax by type for one year and estimate; "Other taxes" is gross minus the named types. */
export function taxMix(year: string, kind: Kind) {
  const gross = tax(year, "gross_tax_revenue", kind);
  if (!gross) return undefined;
  const parts = TAX_TYPES.map((t) => ({ ...t, v: tax(year, t.id, kind) })).filter(
    (p) => p.v && p.v.source.budget === gross.source.budget,
  );
  const named = parts.reduce((s, p) => s + (p.v?.value ?? 0), 0);
  return {
    gross,
    parts: [
      ...parts.map((p) => ({ id: p.id, label: p.label, value: p.v!.value, source: p.v!.source })),
      { id: "other", label: "Other taxes", value: gross.value - named, source: gross.source },
    ],
  };
}

export function statesShare(year: string, kind: Kind): Value | undefined {
  const s = tax(year, "states_share", kind);
  if (!s) return undefined;
  const adj = tax(year, "states_share_adjustment", kind);
  return adj && adj.source.budget === s.source.budget ? { ...s, value: s.value + adj.value } : s;
}

// ---------- ministries ----------
export interface Department {
  id: string;
  name: string;
  ministryId: string;
  ministryName: string;
  level: string;
}
const DEPT_LEVELS = new Set(["department", "union_territory", "state_plan_assistance"]);
export const DEPARTMENTS: Department[] = Object.entries(ministries.items)
  .filter(([, v]) => DEPT_LEVELS.has(v.level))
  .map(([id, v]) => ({
    id,
    name: v.level === "state_plan_assistance" ? `State Plan assistance via ${v.department_name}` : v.department_name,
    ministryId: v.ministry_id,
    ministryName: v.ministry_name,
    level: v.level,
  }));

export interface Ministry {
  id: string;
  name: string;
  departments: Department[];
}
export const MINISTRIES: Ministry[] = Object.values(
  DEPARTMENTS.reduce<Record<string, Ministry>>((acc, d) => {
    (acc[d.ministryId] ??= { id: d.ministryId, name: d.ministryName, departments: [] }).departments.push(d);
    return acc;
  }, {}),
).sort((a, b) => a.name.localeCompare(b.name));

export const deptValue = (year: string, id: string, kind: Kind, field = "total_crore") =>
  detail(ministries, year, id, kind, field);

/** A ministry's total = its departments' lines (plus State Plan assistance routed through it, before 2017-18). */
export function ministryTotal(year: string, m: Ministry, kind: Kind): Value | undefined {
  const vals = m.departments.map((d) => deptValue(year, d.id, kind)).filter((v): v is Value => !!v);
  if (!vals.length) return undefined;
  return {
    value: vals.reduce((s, v) => s + v.value, 0),
    kind,
    source: { ...vals[0].source, label: undefined, note: undefined },
  };
}
export const ministryBest = (year: string, m: Ministry) => best((k) => ministryTotal(year, m, k));

// ---------- schemes ----------
export interface Scheme {
  key: string; // dataset key, e.g. "css/css:samagra_shiksha"
  slug: string; // URL-safe
  name: string;
  aliases: string[];
  type: "css" | "central_sector";
  department: string;
}
export const SCHEME_TYPE_LABEL = {
  css: "Centrally Sponsored Scheme",
  central_sector: "Central Sector Scheme",
} as const;

function hash(s: string): string {
  let h = 2166136261; // FNV-1a, stable across builds
  for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0;
  return h.toString(36).slice(0, 5);
}
function schemeSlug(key: string) {
  const s = key
    .replace(/^(css|central_sector)\/\1:/, "$1-")
    .replace(/[^a-z0-9-]+/gi, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
  return s.length <= 80 ? s : `${s.slice(0, 72).replace(/-$/, "")}-${hash(key)}`;
}
/** Names a scheme was printed under, by budget (shows renames). */
export const SCHEME_NAMES: Map<string, { budget: string; name: string }[]> = (() => {
  const out = new Map<string, Map<string, string>>();
  for (const r of readCsv("schemes.csv")) {
    if (r.level !== "scheme") continue;
    const key = `${r.scheme_type}/${r.item_id}`;
    const name = r.label_as_printed.replace(/^\d+\.\s*/, "");
    (out.get(key) ?? out.set(key, new Map()).get(key)!).set(r.source_budget, name);
  }
  return new Map([...out].map(([k, m]) => [k, [...m].sort().map(([budget, name]) => ({ budget, name }))]));
})();

// Lines that are accounting adjustments rather than schemes ("Actual Recoveries", "Others ...").
const NOT_A_SCHEME = /^(actual\s+)?recoveries\b|^others\b|suspense/i;
export const SCHEMES: Scheme[] = Object.entries(schemes.items)
  .filter(([, v]) => v.level === "scheme" && !NOT_A_SCHEME.test(v.name ?? ""))
  .map(([key, v]) => ({
    key,
    slug: schemeSlug(key),
    // Show the latest official name; search also matches every earlier name.
    name: SCHEME_NAMES.get(key)?.at(-1)?.name ?? v.name,
    aliases: [...new Set((SCHEME_NAMES.get(key) ?? []).map((n) => n.name))],
    type: v.scheme_type,
    department: v.department ?? "",
  }));
{
  const seen = new Set<string>();
  for (const s of SCHEMES) {
    if (seen.has(s.slug)) throw new Error(`duplicate scheme slug ${s.slug}`);
    seen.add(s.slug);
  }
}
export const schemeValue = (year: string, key: string, kind: Kind) => detail(schemes, year, key, kind, "total_crore");
export const SCHEME_YEARS = YEARS.filter((y) => Object.keys(schemes.years[y] ?? {}).length > 0);

// ---------- helpers ----------
export const yearIndex = (y: string) => YEARS.indexOf(y);
export const nextYear = (y: string) => {
  const s = Number(y.slice(0, 4)) + 1;
  return `${s}-${String(s + 1).slice(2)}`;
};

// ---------- series over years ----------
export interface SeriesPoint { value: number | null; kind?: string; estimate?: boolean }

/** Two lines over years: what was announced (BE) and how it turned out (Actual, else RE). */
export function announcedVsOutcome(
  years: string[],
  get: (year: string, kind: Kind) => number | undefined,
): { outcome: SeriesPoint[]; announced: SeriesPoint[] } {
  const outcome = years.map((y) => {
    const a = get(y, "actual");
    if (a != null) return { value: a, kind: "Actual" };
    const r = get(y, "re");
    if (r != null) return { value: r, kind: "RE", estimate: true };
    return { value: null };
  });
  const announced = years.map((y) => {
    const b = get(y, "be");
    return b != null ? { value: b, kind: "BE" } : { value: null };
  });
  return { outcome, announced };
}

/** One line: the best figure available each year (estimates flagged). */
export function bestSeries(years: string[], get: (year: string, kind: Kind) => number | undefined): SeriesPoint[] {
  return years.map((y) => {
    for (const [k, label] of [["actual", "Actual"], ["re", "RE"], ["be", "BE"]] as [Kind, string][]) {
      const v = get(y, k);
      if (v != null) return { value: v, kind: label, estimate: k !== "actual" };
    }
    return { value: null };
  });
}

// ---------- scheme -> department link, via Demand number in the same budget ----------
function readCsv(name: string): Record<string, string>[] {
  const text = fs.readFileSync(path.join(DATA_DIR, name), "utf8");
  const rows: string[][] = [];
  let row: string[] = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i] ?? ""])));
}

/** Scheme key -> department id, using the Demand number printed in the most recent budget that lists the scheme. */
export const SCHEME_DEPARTMENT: Map<string, string> = (() => {
  const demandToDept = new Map<string, string>();
  for (const r of readCsv("ministries.csv")) {
    if (r.demand_no && (r.level === "department" || r.level === "union_territory")) {
      demandToDept.set(`${r.source_budget}|${Number(r.demand_no)}`, r.item_id);
    }
  }
  const latest = new Map<string, { budget: string; dept: string }>();
  for (const r of readCsv("schemes.csv")) {
    if (r.level !== "scheme" || !r.demand_no) continue;
    const key = `${r.scheme_type}/${r.item_id}`;
    const dept = demandToDept.get(`${r.source_budget}|${Number(r.demand_no)}`);
    if (!dept) continue;
    const cur = latest.get(key);
    if (!cur || r.source_budget > cur.budget) latest.set(key, { budget: r.source_budget, dept });
  }
  const out = new Map([...latest].map(([k, v]) => [k, v.dept]));
  // Fallback for years whose statement is grouped by category (no Demand number): match the department name.
  const norm = (x: string) => x.toLowerCase().replace(/&/g, "and").replace(/[^a-z]/g, "");
  const byName = new Map(DEPARTMENTS.map((d) => [norm(d.name), d.id]));
  for (const s of SCHEMES) {
    if (!out.has(s.key) && byName.has(norm(s.department))) out.set(s.key, byName.get(norm(s.department))!);
  }
  return out;
})();

export const schemesOfMinistry = (m: Ministry) => {
  const ids = new Set(m.departments.map((d) => d.id));
  return SCHEMES.filter((s) => ids.has(SCHEME_DEPARTMENT.get(s.key) ?? ""));
};

export const ministryOfScheme = (s: Scheme): Ministry | undefined => {
  const dept = SCHEME_DEPARTMENT.get(s.key);
  return dept ? MINISTRIES.find((m) => m.departments.some((d) => d.id === dept)) : undefined;
};

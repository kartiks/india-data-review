// Read-only access to the verified dataset in ../jobs-prices/data/jobs_prices.json (built and checked by its pipeline).
// This file only picks and labels published figures. The only arithmetic, each labelled where it is shown:
// - yearly averages of published monthly price indices, and the change between two such averages;
// - earnings divided by a price index (earnings "after inflation");
// - differences between two published figures.
import fs from "node:fs";
import path from "node:path";

type Num = number | null;
interface Table { fields: string[]; labels: Record<string, string[]>; rows: (number | null)[][] }
interface Dataset {
  generated_at: string;
  sources: Record<string, { url: string; sha256: string; fetched_at: string; records: number }>;
  plfs: { indicators: Record<string, string>; rates: Table; workers: Table; conditions: Table; earnings: Table };
  cpi: { all_india: Record<string, Record<string, [string, Num, Num][]>>; states: Record<string, Record<string, [string, Num, Num][]>> };
  cpialrl: Table;
  hces: Table;
  cpi2024: {
    latest: string;
    series: [string, number, number, number, Num, Num, Num, boolean][];
    cfpi: Record<string, { index: (Num)[] | null; inflation: (Num)[] | null; provisional: boolean }>;
    divisions: Record<string, [string, string, ...Num[]][]>;
    groups: Record<string, [string, string, ...Num[]][]>;
    states: Record<string, [string, string, ...Num[]][]>;
    releases: Record<string, { page: string; pdf: string | null }>;
    linking: Record<string, number>;
    weights: { division: string; rural_2012: number; rural_2024: number; urban_2012: number; urban_2024: number; combined_2012: number; combined_2024: number }[];
  };
  hces_overall: { year: string; state: string; imputation_type: string; persons_rural_00: number; persons_urban_00: number;
    mpce_rural: number; mpce_urban: number; mpce: number; food_share?: number }[];
  source_problems: string[];
}

const file = path.resolve(process.cwd(), "..", "jobs-prices", "data", "jobs_prices.json");
export const DS: Dataset = JSON.parse(fs.readFileSync(file, "utf8"));
export const GENERATED = DS.generated_at;
export const SOURCES = DS.sources;

/** Rows of a compact table as objects (text columns are stored once in `labels`). */
function objects<T>(t: Table): T[] {
  return t.rows.map((r) => Object.fromEntries(t.fields.map((f, i) => [f, t.labels[f] && r[i] != null ? t.labels[f][r[i] as number] : r[i]])) as T);
}

// ---- jobs (PLFS) --------------------------------------------------------------------------------

export type Sector = "rural" | "urban" | "rural + urban";
export type Gender = "male" | "female" | "person";
export interface Rate {
  frequency: "annual" | "quarterly" | "monthly"; year: string; period: string; state: string; sector: Sector;
  gender: Gender; age: string; status: string; religion: string; social_group: string; education: string;
  lfpr: Num; wpr: Num; ur: Num;
}
export const RATES = objects<Rate>(DS.plfs.rates);
export const AGE15 = "15 years and above";
export const USUAL = "PS+SS"; // usual status: principal + subsidiary activity over the past year
export const WEEKLY = "CWS"; // current weekly status: the past 7 days

export interface RateQuery {
  frequency?: Rate["frequency"]; year?: string; period?: string; state?: string; sector?: Sector; gender?: Gender;
  age?: string; status?: string; religion?: string; social_group?: string; education?: string;
}
const RATE_DEFAULTS: Required<Omit<RateQuery, "year" | "period">> = {
  frequency: "annual", state: "All India", sector: "rural + urban", gender: "person", age: AGE15, status: USUAL,
  religion: "all", social_group: "all", education: "all",
};
// Quarterly and monthly figures carry no status (they are current weekly status) and no religion/group/education breakdown.
const SUB_YEAR_DEFAULTS = { status: "", religion: "", social_group: "", education: "" };
export function rates(q: RateQuery): Rate[] {
  const base = q.frequency && q.frequency !== "annual" ? { ...RATE_DEFAULTS, ...SUB_YEAR_DEFAULTS } : RATE_DEFAULTS;
  const want = { ...base, ...q } as Record<string, string>;
  return RATES.filter((r) => Object.entries(want).every(([k, v]) => (r as unknown as Record<string, string>)[k] === v));
}
export function rate(q: RateQuery & { year: string }): Rate | undefined {
  return rates({ period: "", ...q })[0];
}

/** Distinct values of one field among annual (or other) rate rows matching a partial filter, without defaults. */
export function distinct(field: keyof Rate, where: Partial<Record<keyof Rate, string>>): string[] {
  return [...new Set(RATES.filter((r) => Object.entries(where).every(([k, v]) => (r as unknown as Record<string, string>)[k] === v))
    .map((r) => String(r[field])))].sort();
}
export const PLFS_YEARS = [...new Set(rates({}).map((r) => r.year))].sort();
export const PLFS_LATEST = PLFS_YEARS[PLFS_YEARS.length - 1];

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const QUARTER_LABEL: Record<string, string> = { Q1: "Jan–Mar", Q2: "Apr–Jun", Q3: "Jul–Sep", Q4: "Oct–Dec" };
export const periodLabel = (year: string, period: string) =>
  period.startsWith("Q") ? `${QUARTER_LABEL[period]} ${year}` : period ? `${MONTH_NAMES[Number(period) - 1]} ${year}` : year;
export const monthLabel = (ym: string) => `${MONTH_NAMES[Number(ym.slice(5, 7)) - 1]} ${ym.slice(0, 4)}`;

/** Every period of a quarterly or monthly series, in order, from first to last published (gaps kept). */
export function periods(frequency: "quarterly" | "monthly"): { year: string; period: string }[] {
  const have = RATES.filter((r) => r.frequency === frequency).map((r) => `${r.year}|${r.period}`);
  const sorted = [...new Set(have)].sort();
  if (!sorted.length) return [];
  const [y0, p0] = sorted[0].split("|"), [y1, p1] = sorted[sorted.length - 1].split("|");
  const out: { year: string; period: string }[] = [];
  const step = frequency === "quarterly" ? 4 : 12;
  const idx = (p: string) => (frequency === "quarterly" ? Number(p.slice(1)) : Number(p));
  for (let y = Number(y0), i = idx(p0); y < Number(y1) || (y === Number(y1) && i <= idx(p1)); ) {
    out.push({ year: String(y), period: frequency === "quarterly" ? `Q${i}` : String(i).padStart(2, "0") });
    i++;
    if (i > step) { i = 1; y++; }
  }
  return out;
}

export interface Worker { year: string; state: string; sector: Sector; gender: Gender; status: string; breakdown: string; category: string; value: Num }
export const WORKERS = objects<Worker>(DS.plfs.workers);
export interface Condition { year: string; state: string; sector: Sector; gender: Gender; condition: string; value: Num }
export const CONDITIONS = objects<Condition>(DS.plfs.conditions);
export interface Earning { year: string; state: string; sector: Sector; gender: Gender; kind: "regular" | "casual" | "self"; value: Num }
export const EARNINGS = objects<Earning>(DS.plfs.earnings);

/** Category label without MoSPI's numbering and codes: "4.regular wage/salary" -> "Regular wage/salary". */
export function cleanLabel(s: string): string {
  const t = s.replace(/^\d+\.\s*/, "").replace(/^[A-Z]_/, "").replace(/\s*\(Div\.[^)]*\)/, "").replace(/^NCO Division \d+:\s*/, "");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// ---- consumer prices (CPI) ----------------------------------------------------------------------

export type CpiSector = "Rural" | "Urban" | "Combined";
export interface CpiPoint { month: string; index: Num; inflation: Num }
const toPoints = (rows: [string, Num, Num][] | undefined): CpiPoint[] =>
  (rows ?? []).map(([month, index, inflation]) => ({ month, index, inflation }));
export const GENERAL = "General|General-Overall";
export const FOOD = "Consumer Food Price|Consumer Food Price-Overall";
export const cpiAllIndia = (key: string, sector: CpiSector = "Combined") => toPoints(DS.cpi.all_india[key]?.[sector]);
export const cpiState = (state: string, sector: CpiSector = "Combined") => toPoints(DS.cpi.states[state]?.[sector]);
export const CPI_KEYS = Object.keys(DS.cpi.all_india);
export const CPI_STATES = Object.keys(DS.cpi.states).filter((s) => s !== "All India");
const general = cpiAllIndia(GENERAL);
export const CPI_FIRST = general[0]?.month ?? "";
export const CPI_LAST = general[general.length - 1]?.month ?? "";

/** Months from a to b inclusive ("2014-01" .. "2025-12"). */
export function monthRange(a: string, b: string): string[] {
  const out: string[] = [];
  let y = Number(a.slice(0, 4)), m = Number(a.slice(5, 7));
  while (`${y}-${String(m).padStart(2, "0")}` <= b) {
    out.push(`${y}-${String(m).padStart(2, "0")}`);
    m++;
    if (m > 12) { m = 1; y++; }
  }
  return out;
}

/** Average of the 12 monthly indices of a calendar year ("2025") or fiscal year ("2024-25", April to March). */
export function yearAverage(points: CpiPoint[], year: string): number | undefined {
  const months = year.includes("-")
    ? monthRange(`${year.slice(0, 4)}-04`, `${Number(year.slice(0, 4)) + 1}-03`)
    : monthRange(`${year}-01`, `${year}-12`);
  const byMonth = new Map(points.map((p) => [p.month, p.index]));
  const vals = months.map((m) => byMonth.get(m));
  if (vals.some((v) => v == null)) return undefined;
  return (vals as number[]).reduce((a, b) => a + b, 0) / 12;
}
/** Change in the yearly average index on the year before (how RBI and MoSPI state average inflation). */
export function averageInflation(points: CpiPoint[], year: string): number | undefined {
  const prev = year.includes("-")
    ? `${Number(year.slice(0, 4)) - 1}-${year.slice(2, 4)}`
    : String(Number(year) - 1);
  const a = yearAverage(points, year), b = yearAverage(points, prev);
  return a !== undefined && b !== undefined ? (a / b - 1) * 100 : undefined;
}
export const cpiLabel = (key: string) => {
  const [group, sub] = key.split("|");
  return sub.endsWith("-Overall") ? group : sub;
};

// ---- consumer prices, new series (base 2024 = 100), from MoSPI's monthly press releases --------------

const C24 = DS.cpi2024;
export interface Cpi24Point { month: string; index: [number, number, number]; inflation: [Num, Num, Num]; provisional: boolean }
/** All-India general index, rural / urban / combined, January 2025 to the latest month; inflation from January 2026. */
export const CPI24: Cpi24Point[] = C24.series.map(([month, r, u, c, ir, iu, ic, provisional]) => ({ month, index: [r, u, c], inflation: [ir, iu, ic], provisional }));
export const CPI24_LATEST = C24.latest;
export const CPI24_RELEASES = C24.releases;
export const CPI24_LINKING = C24.linking;
export const CPI24_WEIGHTS = C24.weights;
/** Consumer Food Price Index inflation, [rural, urban, combined], by month (final where a later release gives it). */
export const cfpi24 = (month: string) => C24.cfpi[month];
export interface Cpi24Row { code: string; name: string; index: Num[]; inflation: Num[] }
/** Divisions, groups or states as published in that month's release (provisional). */
export function cpi24Rows(kind: "divisions" | "groups" | "states", month = C24.latest): Cpi24Row[] {
  return (C24[kind][month] ?? []).map(([code, name, ...v]) => ({ code, name, index: v.slice(0, 3), inflation: v.slice(3, 6) }));
}
/** One key for a state however a source spells it: "The Dadra And Nagar Haveli And Daman And Diu",
 * "Dadra & Nagar Haveli & Daman & Diu" and "Dadra and Nagar Haveli and Daman and Diu" all give the same key. */
export const stateKey = (s: string) =>
  s.toLowerCase().replace(/&/g, "and").replace(/^the |^nct of |\bislands?\b/g, "").replace(/[^a-z]/g, "");
/** "Andaman And Nicobar Islands" -> "Andaman & Nicobar Islands"; the releases spell names differently from MoSPI's API. */
export const tidyState = (s: string) => s.replace(/ And /g, " & ").replace(/^The /, "").replace("NCT of Delhi", "Delhi");

// ---- farm and rural labourers (CPI-AL/RL) and household spending (HCES) -------------------------------

export interface AlrlRow { month: string; base_year: string; state: string; index_al: Num; index_rl: Num; inflation_al: Num; inflation_rl: Num }
export const CPIALRL = objects<AlrlRow>(DS.cpialrl);

export interface HcesRow {
  indicator: "mpce" | "classes" | "shares" | "household_type" | "social_group" | "gini";
  year: string; state: string; sector: "Rural" | "Urban"; imputation_type: string; category: string; value: Num;
}
export const HCES = objects<HcesRow>(DS.hces);
export const HCES_YEARS = [...new Set(HCES.map((r) => r.year))].sort();
export const HCES_LATEST = HCES_YEARS[HCES_YEARS.length - 1];
/** MoSPI's headline HCES figures value items received free (public distribution, school meals) at market prices. */
export const IMPUTED = "With Imputation";
export const NOT_IMPUTED = "Without Imputation";
export function hces(q: Partial<HcesRow>): HcesRow[] {
  return HCES.filter((r) => Object.entries(q).every(([k, v]) => (r as unknown as Record<string, unknown>)[k] === v));
}
export const hcesValue = (q: Partial<HcesRow>) => hces(q)[0]?.value ?? undefined;
/** Rural + urban average, weighted by the survey's estimated persons (MoSPI's report, Table A2); worked out by the pipeline. */
export const hcesOverall = (state: string, year: string, imputation = NOT_IMPUTED) =>
  DS.hces_overall.find((r) => stateKey(r.state) === stateKey(state) && r.year === year && r.imputation_type === imputation);
/** Like hcesValue, but matching the state however it is spelt (the surveys spell some UTs differently). */
export const hcesValueFor = (state: string, q: Partial<HcesRow>) =>
  HCES.find((r) => stateKey(r.state) === stateKey(state) && Object.entries(q).every(([k, v]) => (r as unknown as Record<string, unknown>)[k] === v))?.value ?? undefined;

// ---- states ---------------------------------------------------------------------------------------

/** PLFS state names (36 states and UTs; Dadra & Nagar Haveli and Daman & Diu as one UT, Ladakh separate). */
export const PLFS_STATES = distinct("state", { frequency: "annual", year: PLFS_LATEST }).filter((s) => s !== "All India");

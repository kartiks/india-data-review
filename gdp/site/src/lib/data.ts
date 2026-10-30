// Read-only access to the verified dataset in ../data/gdp.json (built and checked by ../pipeline).
// This file only picks, adds up and labels published figures; it never changes a number.
// The only arithmetic: shares (part ÷ whole, same year, same estimate) and differences between two published figures.
import fs from "node:fs";
import path from "node:path";

export interface Pair { cur?: number; con?: number; summed?: boolean }
export interface Growth { real?: number; nominal?: number; published?: boolean }
export interface Node {
  gdp?: Pair; gva?: Pair; net_taxes?: Pair; pfce?: Pair; gfce?: Pair; gfcf?: Pair; stocks?: Pair; valuables?: Pair;
  exports?: Pair; imports?: Pair; gni?: Pair; gndi?: Pair; ndp?: Pair; cfc?: Pair; saving?: Pair;
  growth?: { gdp?: Growth };
  gva_by_industry?: Record<string, Pair>;
  gva_growth?: Record<string, Growth>;
  gva_sub?: Record<string, Record<string, Pair>>;
  gfcf_by_sector?: Record<string, Pair>;
  saving_by_sector?: Record<string, Pair>;
}
type Stages = Record<string, Node>;
interface Dataset {
  generated_at: string;
  series: Record<string, string>;
  stages: { id: string; as_printed: string; label: string; when: string }[];
  industries: Record<string, string>;
  broad_industries: string[];
  sectors: Record<string, string>;
  data: Record<string, { annual?: Record<string, Stages>; quarterly?: Record<string, Stages> }>;
  long_run: { year: string; series: string; stage: string; gdp: Pair; growth?: Growth }[];
  budget_assumptions: BudgetAssumption[];
  forecasts: { economic_survey: SurveyForecast[]; rbi: RbiForecast[] };
  source_problems: string[];
  duplicate_rows: string[];
}
export interface BudgetAssumption {
  budget: string; gdp_crore: number; growth_pct?: number; over?: string; base_gdp_crore?: number;
  text: string; url: string; note?: string;
}
export interface SurveyForecast {
  fiscal_year: string; survey: string; published_date: string; low: number; high: number; kind: string;
  band_low?: number; band_high?: number; quote: string; url: string; pdf_page?: number; notes?: string;
  nominal_low?: number | null; nominal_high?: number | null;
}
export interface RbiForecast {
  fiscal_year: string; statement: string; date: string; measure: string; value: number | null;
  low?: number | null; high?: number | null; value_text?: string; quote: string; url: string;
  is_first?: boolean; is_last?: boolean; is_first_april_policy?: boolean; notes?: string;
}

const file = path.resolve(process.cwd(), "..", "data", "gdp.json");
export const DS: Dataset = JSON.parse(fs.readFileSync(file, "utf8"));

export const OLD = "2011-12"; // series ids
export const BACK = "2011-12-back";
export const NEW = "2022-23";

export const STAGE_ORDER = Object.fromEntries(DS.stages.map((s, i) => [s.id, i]));
export const STAGE_LABEL = Object.fromEntries(DS.stages.map((s) => [s.id, s.label]));
export const STAGE_SHORT: Record<string, string> = {
  AE1: "1st advance", AE2: "2nd advance", PE: "Provisional", RE1: "1st revised", RE2: "2nd revised",
  RE3: "3rd revised", ADD: "Additional revision", FINAL: "Final", BACK: "Back series", LATEST: "Latest",
};
export const INDUSTRY = DS.industries;
export const BROAD = DS.broad_industries;
export const SECTOR = DS.sectors;

export const fyStart = (y: string) => Number(y.slice(0, 4));
export const fy = (start: number) => `${start}-${String(start + 1).slice(-2)}`;
export const prevYear = (y: string) => fy(fyStart(y) - 1);

export function annual(series: string): Record<string, Stages> {
  return DS.data[series]?.annual ?? {};
}
export function quarterly(series: string): Record<string, Stages> {
  return DS.data[series]?.quarterly ?? {};
}
export const yearsOf = (series: string) => Object.keys(annual(series)).sort();
export const range = (from: string, to: string) => {
  const out: string[] = [];
  for (let s = fyStart(from); s <= fyStart(to); s++) out.push(fy(s));
  return out;
};

/** Stages for a year, in publication order. */
export function stagesOf(series: string, year: string): string[] {
  return Object.keys(annual(series)[year] ?? {}).sort((a, b) => STAGE_ORDER[a] - STAGE_ORDER[b]);
}
export function latestStage(series: string, year: string, need?: (n: Node) => unknown): string | undefined {
  const stages = stagesOf(series, year).filter((s) => !need || need(annual(series)[year][s]));
  return stages[stages.length - 1];
}
export function firstStage(series: string, year: string, need?: (n: Node) => unknown): string | undefined {
  return stagesOf(series, year).filter((s) => !need || need(annual(series)[year][s]))[0];
}
export function node(series: string, year: string, stage?: string): Node | undefined {
  const st = stage ?? latestStage(series, year);
  return st ? annual(series)[year]?.[st] : undefined;
}

/** Published real/nominal GDP growth at a stage. */
export const growthAt = (series: string, year: string, stage: string) => annual(series)[year]?.[stage]?.growth?.gdp;

// ---- the headline series --------------------------------------------------------

/** The long-run row for a year (2011-12 base: back series to 2011-12, then the latest estimate). */
export const LONG = DS.long_run;
export const longRow = (y: string) => LONG.find((r) => r.year === y);

/** Latest annual figures in the new 2022-23 series. */
export const NEW_YEARS = yearsOf(NEW);
export const LATEST_YEAR = NEW_YEARS[NEW_YEARS.length - 1];
export const LATEST_STAGE = latestStage(NEW, LATEST_YEAR)!;

export function quarters(series: string): string[] {
  return Object.keys(quarterly(series)).sort();
}
export const quarterNode = (series: string, period: string) => quarterly(series)[period]?.LATEST;

// ---- picking a year's figure, with the stage it came from ---------------------------

export interface Pick { value: number; stage: string; series: string }

/** For each year, a value from the latest estimate that has it (or undefined). */
export function bestOf(series: string, years: string[], get: (n: Node) => number | undefined): (Pick | undefined)[] {
  return years.map((y) => {
    const st = latestStage(series, y, (n) => get(n) !== undefined);
    if (!st) return undefined;
    return { value: get(annual(series)[y][st])!, stage: st, series };
  });
}

/** 2000-01 onward on the 2011-12 base: back series up to 2010-11, then the 2011-12 series' latest estimate. */
export function oldBaseOf(years: string[], get: (n: Node) => number | undefined): (Pick | undefined)[] {
  return years.map((y) => {
    if (fyStart(y) <= 2010) {
      const n = annual(BACK)[y]?.BACK;
      const v = n ? get(n) : undefined;
      return v === undefined ? undefined : { value: v, stage: "BACK", series: BACK };
    }
    return bestOf(OLD, [y], get)[0];
  });
}

export const share = (part?: number, whole?: number) =>
  part === undefined || whole === undefined || whole === 0 ? undefined : (part / whole) * 100;

/** Sum of the eight broad industries' GVA (equals total GVA in the current series; see the report for the back series). */
export function industrySum(n: Node, price: "cur" | "con" = "cur"): number | undefined {
  const g = n.gva_by_industry ?? {};
  if (!BROAD.every((i) => g[i]?.[price] !== undefined)) return undefined;
  return BROAD.reduce((s, i) => s + g[i][price]!, 0);
}

// ---- forecasts -------------------------------------------------------------------

export const SURVEY = DS.forecasts.economic_survey;
export const RBI = DS.forecasts.rbi;
export const BUDGET = DS.budget_assumptions;

export const rbiFor = (y: string) => RBI.filter((r) => r.fiscal_year === y).sort((a, b) => a.date.localeCompare(b.date));
/** RBI's start-of-year projection: the April/May policy if it gave a number, else the first number given for the year.
 *  (A February projection for the next year can be on a different base or measure, e.g. Feb 2015 on the old 2004-05 base.) */
export const rbiFirst = (y: string) =>
  rbiFor(y).find((r) => r.is_first_april_policy && r.value !== null) ?? rbiFor(y).find((r) => r.value !== null);
export const rbiLast = (y: string) => [...rbiFor(y)].reverse().find((r) => r.value !== null);

/** MoSPI's first published growth estimate for a year in the 2011-12 series (AE1 where it exists). */
export function firstEstimate(y: string): { real: number; stage: string; series: string } | undefined {
  for (const s of [OLD, NEW]) {
    const st = firstStage(s, y, (n) => n.growth?.gdp?.real !== undefined);
    if (st && (STAGE_ORDER[st] <= STAGE_ORDER.PE || s === NEW)) return { real: growthAt(s, y, st)!.real!, stage: st, series: s };
  }
  return undefined;
}
/** Latest published growth for a year: new series if it covers the year, else the 2011-12 series. */
export function latestGrowth(y: string, prefer: string = OLD): { real: number; nominal?: number; stage: string; series: string } | undefined {
  for (const s of prefer === NEW ? [NEW, OLD] : [OLD, NEW]) {
    const st = latestStage(s, y, (n) => n.growth?.gdp?.real !== undefined);
    if (st) { const g = growthAt(s, y, st)!; return { real: g.real!, nominal: g.nominal, stage: st, series: s }; }
  }
  const r = longRow(y);
  if (r?.growth?.real !== undefined) return { real: r.growth.real, nominal: r.growth.nominal, stage: r.stage, series: r.series };
  return undefined;
}

export const SERIES_LABEL: Record<string, string> = {
  [OLD]: "2011-12 base",
  [BACK]: "2011-12 base (back series)",
  [NEW]: "2022-23 base (new series)",
};
export const GENERATED = DS.generated_at;

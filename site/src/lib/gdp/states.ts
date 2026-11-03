// Read-only access to the verified state accounts in ../data/states.json (built and checked by ../pipeline, states.py).
// This file only picks and labels published figures. The only arithmetic: shares of a state's own value added, and
// average annual growth between two published constant-price levels.
import fs from "node:fs";
import path from "node:path";
import { OLD, annual, industrySum, latestStage, STAGE_LABEL } from "./data";

export interface SPair { cur?: number; con?: number; derived?: boolean }
export interface SGrowth { real?: number; nominal?: number; published?: boolean }
export interface SNode {
  gsdp?: SPair; nsdp?: SPair; pc_gsdp?: SPair; pc_nsdp?: SPair; pc_nsdp_alt?: SPair; taxes?: SPair; subsidies?: SPair;
  growth?: { gsdp?: SGrowth; nsdp?: SGrowth; pc_nsdp?: SGrowth };
  gsva?: Record<string, SPair>;
  gsva_sub?: Record<string, Record<string, SPair>>;
}
interface StateDataset {
  generated_at: string;
  bases: string[];
  industries: Record<string, string>;
  sectors: Record<string, string[]>;
  sector_labels: Record<string, string>;
  data: Record<string, Record<string, Record<string, SNode>>>;
  left_out: string[];
}

const file = path.resolve(process.cwd(), "..", "gdp", "data", "states.json");
export const SDS: StateDataset = JSON.parse(fs.readFileSync(file, "utf8"));

// MoSPI publishes the state accounts on the 2011-12 base only. When a 2022-23 series appears, the validation report
// says so; switch this over then (and check the page's wording).
export const STATE_BASE = "2011-12";
const DATA = SDS.data[STATE_BASE] ?? {};

export const STATES = Object.keys(DATA).sort();
export const STATE_YEARS = [...new Set(STATES.flatMap((s) => Object.keys(DATA[s])))].sort();
export const FIRST_YEAR = STATE_YEARS[0];
export const SECTORS = Object.keys(SDS.sectors);
export const SECTOR_LABEL = SDS.sector_labels;

export const sNode = (state: string, year: string): SNode | undefined => DATA[state]?.[year];

/** The latest year in which at least `min` states have the figure. */
export function latestYear(get: (n: SNode) => number | undefined, min = 28): string {
  return [...STATE_YEARS].reverse().find((y) => STATES.filter((s) => { const n = sNode(s, y); return n && get(n) != null; }).length >= min)!;
}
export const countWith = (year: string, get: (n: SNode) => number | undefined) =>
  STATES.filter((s) => { const n = sNode(s, year); return n && get(n) != null; }).length;

export const gsdpCur = (n: SNode) => n.gsdp?.cur;
export const realGrowth = (n: SNode) => n.growth?.gsdp?.real;
/** Income per person: NSDP per person at current prices (MoSPI's first table, else its second). */
export const incomePerPerson = (n: SNode) => (n.pc_nsdp ?? n.pc_nsdp_alt)?.cur;
export const gsdpPerPerson = (n: SNode) => n.pc_gsdp?.cur;

/** Shares of agriculture, industry and services in the state's value added, current prices. */
export function sectorShares(n: SNode | undefined): Record<string, number> | undefined {
  const total = n?.gsva?.total?.cur;
  if (!n?.gsva || !total) return undefined;
  const out: Record<string, number> = {};
  for (const [sector, parts] of Object.entries(SDS.sectors)) {
    if (!parts.every((p) => n.gsva![p]?.cur != null)) return undefined;
    out[sector] = (parts.reduce((a, p) => a + n.gsva![p].cur!, 0) / total) * 100;
  }
  return out;
}

/** Average annual real growth between two years, from constant-price GSDP. */
export function averageGrowth(state: string, from: string, to: string): number | undefined {
  const a = sNode(state, from)?.gsdp?.con, b = sNode(state, to)?.gsdp?.con;
  const years = Number(to.slice(0, 4)) - Number(from.slice(0, 4));
  return a && b && years > 0 ? (Math.pow(b / a, 1 / years) - 1) * 100 : undefined;
}

export const isDerived = (state: string, year: string) => !!sNode(state, year)?.gsdp?.derived;

// ---- All India, from the national accounts on the same 2011-12 base -------------------------------------

const NATIONAL_SECTORS: Record<string, string[]> = {
  agriculture: ["agriculture"],
  industry: ["mining", "manufacturing", "utilities", "construction"],
  services: ["trade_transport", "finance_realestate", "public_other"],
};

export function india(year: string) {
  const stage = latestStage(OLD, year, (n) => n.gdp?.cur);
  if (!stage) return undefined;
  const n = annual(OLD)[year][stage];
  const total = industrySum(n);
  const shares = total
    ? Object.fromEntries(Object.entries(NATIONAL_SECTORS).map(([s, parts]) =>
      [s, (parts.reduce((a, p) => a + (n.gva_by_industry?.[p]?.cur ?? 0), 0) / total) * 100]))
    : undefined;
  return { gdp: n.gdp!.cur!, gdpCon: n.gdp?.con, growth: n.growth?.gdp?.real, stage, stageLabel: STAGE_LABEL[stage], shares };
}

export function indiaAverageGrowth(from: string, to: string): number | undefined {
  const a = india(from)?.gdpCon, b = india(to)?.gdpCon;
  const years = Number(to.slice(0, 4)) - Number(from.slice(0, 4));
  return a && b && years > 0 ? (Math.pow(b / a, 1 / years) - 1) * 100 : undefined;
}

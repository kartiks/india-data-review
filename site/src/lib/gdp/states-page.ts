// What /gdp/states/ shows, from the state accounts (./states.ts) and India's national accounts on the same base.
// Like the data modules, this only picks, ranks and labels published figures; the arithmetic is in ./states.ts
// (shares and average growth) and here only each state's share of all states' GSDP and the ratio of the highest
// income per person to the lowest.
import { mapMetric, type MapMetric } from "../map-metric";
import { type PickOption } from "../line-plot";
import { gpct, money, pct, rupees } from "../format";
import { stateKey } from "../states";
import { STAGE_SHORT } from "./data";
import {
  STATES, STATE_YEARS, FIRST_YEAR, SECTORS, SECTOR_LABEL, LATEST, BOUNDARY, sNode, countWith, gsdpCur,
  realGrowth, incomePerPerson, gsdpPerPerson, sectorShares, averageGrowth, isDerived, india, indiaAverageGrowth,
} from "./states";

/** One state or union territory in the year compared (null: no figure). */
export interface StateRow {
  st: string;
  key: string; // stateKey(st)
  gsdp: number | null;
  derived: boolean; // GSDP worked out as GSVA + taxes − subsidies
  growth: number | null;
  growthWorkedOut: boolean; // growth worked out from the levels, not published
  avg: number | null; // average real growth a year from FIRST_YEAR
  boundary: boolean; // the state's area changed between FIRST_YEAR and the year compared
  income: number | null;
  gsdpPP: number | null;
  shares: Record<string, number> | undefined;
}

// One year for every measure, so states are compared like with like: the latest year in which the states that have
// published made up at least 97% of the states' economy the year before.
const Y = LATEST;

/** The table's rows: every state, in the year compared. */
export function stateRows(year = Y): StateRow[] {
  return STATES.map((st) => {
    const n = sNode(st, year);
    return {
      st,
      key: stateKey(st),
      gsdp: n ? gsdpCur(n) ?? null : null,
      derived: isDerived(st, year),
      growth: n ? realGrowth(n) ?? null : null,
      growthWorkedOut: n?.growth?.gsdp?.published === false,
      avg: averageGrowth(st, FIRST_YEAR, year) ?? null,
      boundary: !!BOUNDARY[st] && BOUNDARY[st].until >= FIRST_YEAR && BOUNDARY[st].until < year,
      income: n ? incomePerPerson(n) ?? null : null,
      gsdpPP: n ? gsdpPerPerson(n) ?? null : null,
      shares: sectorShares(n),
    };
  });
}

/** The map's measures, each with India's figure in its note where there is one. */
export function stateMetrics(rows: StateRow[], year = Y): MapMetric[] {
  const IN = india(year);
  const inAvg = indiaAverageGrowth(FIRST_YEAR, year);
  return [
    mapMetric(rows, {
      id: "size", label: "Size", title: `Size of the state economy (GSDP), ${year}`, format: (v) => money(v),
      note: `Gross state domestic product at current prices.${IN ? ` India's GDP: ${money(IN.gdp)}.` : ""}`,
    }, (r) => r.gsdp),
    mapMetric(rows, {
      id: "growth", label: "Growth", title: `Real growth, ${year}`, format: (v) => gpct(v),
      note: `GSDP at constant 2011-12 prices, on the year before.${IN?.growth != null ? ` India: ${gpct(IN.growth)}.` : ""}`,
    }, (r) => r.growth),
    mapMetric(rows, {
      id: "avg", label: `Growth since ${FIRST_YEAR}`, title: `Average real growth a year, ${FIRST_YEAR} to ${year}`, format: (v) => gpct(v),
      note: `Worked out from constant-price GSDP in the two years.${inAvg != null ? ` India: ${gpct(inAvg)}.` : ""}`,
    }, (r) => r.avg),
    mapMetric(rows, {
      id: "income", label: "Income per person", title: `Income per person, ${year}`, format: rupees,
      note: "Net state domestic product per person, current prices.",
    }, (r) => r.income),
    ...SECTORS.map((s) => mapMetric(rows, {
      id: s, label: SECTOR_LABEL[s], title: `${SECTOR_LABEL[s]}, share of the state's value added, ${year}`, format: (v) => pct(v),
      note: `Current prices.${IN?.shares ? ` India: ${pct(IN.shares[s])}.` : ""}`,
    }, (r) => r.shares?.[s])),
  ];
}

/** Ranked lists for the two bar charts: the 12 largest economies, and the 6 highest and 6 lowest incomes per person. */
export function stateRankings(rows: StateRow[]) {
  const all = rows.filter((r) => r.gsdp != null);
  const total = all.reduce((a, r) => a + r.gsdp!, 0);
  const biggest = [...all].sort((a, b) => b.gsdp! - a.gsdp!);
  const richest = rows.filter((r) => r.income != null).sort((a, b) => b.income! - a.income!);
  const sizeRows = biggest.slice(0, 12).map((r) => ({
    label: r.st, value: r.gsdp!, display: money(r.gsdp!), sub: `${pct((Number(r.gsdp) / total) * 100)} of all states`,
  }));
  const incomeRows = richest.map((r, i) => ({ label: `${i + 1}. ${r.st}`, value: r.income!, display: rupees(r.income!) }))
    .filter((_, i) => i < 6 || i >= richest.length - 6);
  return { all, total, biggest, richest, sizeRows, incomeRows };
}

// Years still at an early estimate are marked; on the 2011-12 base they will not be revised further.
const EARLY = new Set(["AE1", "AE2", "PE"]);

/** Real growth year by year: every state with constant-price figures (to compare any set), and All India for
 *  reference. Years run to the latest any state has published. */
export function growthLines() {
  const years = STATE_YEARS.filter((y) => y > FIRST_YEAR);
  const nextYear = (y: string) => STATE_YEARS[STATE_YEARS.indexOf(y) + 1];
  const options: PickOption[] = STATES.map((st) => {
    const kinds = years.map((y) => sNode(st, y)?.growth?.gsdp?.published === false ? "worked out"
      : BOUNDARY[st] && y === nextYear(BOUNDARY[st].until) ? "area changed" : "");
    const values = years.map((y) => { const n = sNode(st, y); return n ? realGrowth(n) ?? null : null; });
    const worked = years.filter((_, i) => values[i] != null && kinds[i] === "worked out").length;
    const notes = [
      worked ? `${st}: growth worked out here from GSDP levels${worked < values.filter((v) => v != null).length ? " in some years" : ""}, because MoSPI's GSDP table leaves ${st} out (see the notes under the table of all states, below).` : "",
      BOUNDARY[st] ? BOUNDARY[st].note : "",
    ].filter(Boolean);
    return { key: stateKey(st), name: st, values, kinds, note: notes.join(" ") };
  }).filter((o) => o.values.some((v) => v != null));
  const reference: PickOption = {
    key: "india", name: "All India",
    values: years.map((y) => india(y)?.growth ?? null),
    kinds: years.map((y) => { const st = india(y)?.stage; return st && EARLY.has(st) ? `${STAGE_SHORT[st].toLowerCase()} estimate` : ""; }),
    note: "All India (dashed): GDP growth from the national accounts on the same 2011-12 base, the latest estimate for each year. MoSPI moved national GDP to a 2022-23 base in February 2026, so the last years on this base stay at their advance or provisional estimates.",
  };
  const noGrowth = STATES.filter((st) => !options.some((o) => o.name === st));
  const last = years[years.length - 1];
  return { years, options, reference, noGrowth, last, lastCount: countWith(last, realGrowth) };
}

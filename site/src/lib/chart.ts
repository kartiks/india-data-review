// Geometry helpers for the build-time SVG charts.

export interface Size {
  name: "sm" | "md" | "lg" | "xl";
  width: number; // viewBox width
  height: number;
  font: number; // in viewBox units
  left: number;
  right: number; // a line chart with one series: room for its end label (shown when this is over 40)
  rightMulti: number; // a line chart with two or more series (legend and hover instead of end labels)
  top: number;
  bottom: number;
  xLabels: number; // most labels on the x axis
  from: number; // shown when the chart is at least this many CSS px wide (styles/charts.css)
  max: number; // drawn at most this many CSS px wide (styles/charts.css)
}
// Four renderings of every chart; styles/charts.css shows the one that fits the chart's own width (a container
// query, so a chart in a half-width column gets a narrower one than a full-width chart on the same screen). Each
// is shown from `from` px wide and drawn at most `max` px wide, which keeps tick labels at about 11-14px:
// sm 320: 10.6px on a 375px phone, 14px at 410; md 480: 11px at 440, 14px at 560; lg 660: 11px at 600, 14px at
// 770; xl 880: 11px at 800, 13px on the widest card (958).
export const SIZES: Size[] = [
  { name: "sm", width: 320, height: 220, font: 11, left: 44, right: 12, rightMulti: 12, top: 14, bottom: 26, xLabels: 4, from: 0, max: 410 },
  { name: "md", width: 480, height: 250, font: 12, left: 52, right: 24, rightMulti: 24, top: 16, bottom: 28, xLabels: 6, from: 440, max: 560 },
  { name: "lg", width: 660, height: 280, font: 12, left: 56, right: 96, rightMulti: 36, top: 16, bottom: 28, xLabels: 8, from: 600, max: 770 },
  { name: "xl", width: 880, height: 320, font: 12, left: 56, right: 96, rightMulti: 36, top: 16, bottom: 28, xLabels: 10, from: 800, max: 1027 },
];

/** Round tick steps (1, 2, 2.5, 5 × 10^n) covering [min, max]. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) max = min + 1;
  const raw = (max - min) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 1e6) / 1e6);
  // No finite range (a chart with no values and zero=false gets min=Infinity, max=-Infinity): use 0 to 1.
  return ticks.length ? ticks : niceTicks(0, 1, count);
}

export const scale = (d0: number, d1: number, r0: number, r1: number) => (v: number) =>
  d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);

/** SVG path for a column/bar with a 4px rounded data-end and a square baseline. */
export function columnPath(x: number, y0: number, w: number, y1: number, r = 4): string {
  const h = y0 - y1;
  if (Math.abs(h) < 0.5) return "";
  const up = h > 0;
  const rr = Math.min(r, Math.abs(h), w / 2);
  const top = y1;
  if (up) {
    return `M${x},${y0}V${top + rr}Q${x},${top} ${x + rr},${top}H${x + w - rr}Q${x + w},${top} ${x + w},${top + rr}V${y0}Z`;
  }
  return `M${x},${y0}V${top - rr}Q${x},${top} ${x + rr},${top}H${x + w - rr}Q${x + w},${top} ${x + w},${top - rr}V${y0}Z`;
}

export interface Estimate { short: string; full: string }
/** How final a figure is, as pages pass it ("Actual", "RE", "Third Revised Estimate", "Provisional", "1st advance
 *  estimate"), turned into one short lower-case form for tables and readouts ("RE", "3rd revised", "provisional",
 *  "1st advance") and a full name for a tooltip. Actuals get "", since they need no label. Presentation only. */
export function estimate(kind: string | undefined): Estimate {
  const k = (kind ?? "").trim();
  if (!k || /^actuals?$/i.test(k)) return { short: "", full: "" };
  if (k === "RE") return { short: "RE", full: "Revised Estimate" };
  if (k === "BE") return { short: "BE", full: "Budget Estimate" };
  const short = k.toLowerCase().replace(/\s+estimates?$/, "").replace(/^first\b/, "1st").replace(/^second\b/, "2nd").replace(/^third\b/, "3rd");
  return { short, full: k[0].toUpperCase() + k.slice(1) };
}

/** Where a table shows estimate labels, given each cell's short label (null = no value):
 *  "none" when every value has the same one (`all`, "" for actuals: say it once under the table);
 *  "column" when each row's values share one (a column after the year); "inline" otherwise (before each value). */
export function estimateLayout(cells: (string | null)[][]): { mode: "none" | "column" | "inline"; all: string } {
  const present = cells.flat().filter((k): k is string => k != null);
  if (new Set(present).size <= 1) return { mode: "none", all: present[0] ?? "" };
  const rowShares = cells.every((row) => new Set(row.filter((k) => k != null)).size <= 1);
  return { mode: rowShares ? "column" : "inline", all: "" };
}

/** Rough width of a text label in viewBox units at a size (0.6 em a character, generous for digits). */
export const labelWidth = (s: string, sz: Size) => s.length * sz.font * 0.6;

/** Indices to label on the x axis: the latest, then evenly back, at most the size's xLabels and no closer than the
 *  widest label allows. `spacing`: viewBox units between neighbouring positions. `endAnchored`: the latest label
 *  ends at its position (text-anchor end), so it reaches further left; the label before it is dropped when the
 *  two would touch. */
export function xTickIndices(labels: string[], sz: Size, spacing: number, endAnchored: boolean): number[] {
  const n = labels.length;
  if (n <= 1) return n ? [0] : [];
  const w = Math.max(...labels.map((l) => labelWidth(l, sz)));
  const gap = sz.font * 0.5;
  const step = Math.max(1, Math.ceil(n / sz.xLabels), Math.ceil((w + gap) / Math.max(spacing, 1e-6)));
  const out: number[] = [];
  for (let i = n - 1; i >= 0; i -= step) out.push(i);
  if (endAnchored && out.length > 1 && step * spacing < 1.5 * w + gap) out.splice(1, 1);
  return out.reverse();
}

// Geometry helpers for the build-time SVG charts.

export interface Size {
  name: "sm" | "lg";
  width: number;
  height: number;
  font: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
}
// Two renderings of every chart: one sized for phones, one for wider screens.
export const SIZES: Size[] = [
  { name: "sm", width: 360, height: 220, font: 11, left: 44, right: 12, top: 14, bottom: 26 },
  { name: "lg", width: 720, height: 300, font: 12, left: 56, right: 96, top: 16, bottom: 28 },
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
  return ticks;
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

/** Horizontal bar with a rounded end at x1 (square at x0). */
export function barPath(x0: number, y: number, x1: number, h: number, r = 4): string {
  const w = x1 - x0;
  if (Math.abs(w) < 0.5) return "";
  const rr = Math.min(r, Math.abs(w), h / 2);
  if (w > 0) return `M${x0},${y}H${x1 - rr}Q${x1},${y} ${x1},${y + rr}V${y + h - rr}Q${x1},${y + h} ${x1 - rr},${y + h}H${x0}Z`;
  return `M${x0},${y}H${x1 + rr}Q${x1},${y} ${x1},${y + rr}V${y + h - rr}Q${x1},${y + h} ${x1 + rr},${y + h}H${x0}Z`;
}

export const shortYear = (y: string) => y; // "2005-06"

/** Indices to label on the x axis: the latest year, then evenly back, as many as fit at this size. */
export function xTickIndices(n: number, size: "sm" | "lg"): number[] {
  const maxLabels = size === "sm" ? 4 : 9;
  const step = Math.max(1, Math.ceil(n / maxLabels));
  const out: number[] = [];
  for (let i = n - 1; i >= 0; i -= step) out.push(i);
  return out.reverse();
}

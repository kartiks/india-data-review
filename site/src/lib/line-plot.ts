// SVG markup for line charts over years, as a string, so the same drawing runs at build time (LineChart.astro, and
// PickLines' starting set) and in the browser (PickLines redrawing the lines the reader chose).
import { SIZES, niceTicks, scale, xTickIndices, type Size } from "./chart";
import { axisPct } from "./format";

/** Axis tick formats by name, so a chart drawn again in the browser formats its ticks the same way. */
export const AXIS_FORMATS = { pct: axisPct };
export type AxisFormat = keyof typeof AXIS_FORMATS;

export interface PlotLine {
  name: string;
  color: string; // CSS colour, e.g. "var(--s1)"
  dashed?: boolean;
  values: (number | null)[]; // aligned with `years`
  estimates?: boolean[]; // per year: an estimate, drawn as a hollow marker
}
export interface PlotOptions {
  zero?: boolean; // include zero in the y range (default true)
  endLabel?: boolean; // a chart with one line labels its last value in the right margin, where a size leaves room
  annotations?: { year: string; label: string }[]; // a dashed rule at a year, with a label
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const n1 = (v: number) => v.toFixed(1);

/** Ticks for the y axis, including zero unless `zero` is false. */
export function plotTicks(lines: PlotLine[], zero = true): number[] {
  const values = lines.flatMap((l) => l.values).filter((v): v is number => v != null);
  const lo = Math.min(...values), hi = Math.max(...values);
  return zero ? niceTicks(Math.min(0, lo), Math.max(0, hi), 4) : niceTicks(lo, hi, 4);
}

/** Where everything goes at one size: the right margin (room for an end label only with one line), the x of each
 *  year, the y scale, the years labelled on the x axis, and annotation labels (moved to a lower row when they would
 *  overlap). */
export function lineGeometry(sz: Size, years: string[], lines: PlotLine[], ticks: number[], opts: PlotOptions = {}) {
  const right = opts.endLabel && lines.length === 1 ? sz.right : sz.rightMulti;
  const x = scale(0, years.length - 1, sz.left, sz.width - right);
  const y = scale(ticks[0], ticks[ticks.length - 1], sz.height - sz.bottom, sz.top);
  const xs = years.map((_, i) => x(i));
  const xTicks = xTickIndices(years, sz, xs.length > 1 ? xs[1] - xs[0] : 0, right < 30);
  const charW = sz.font * 0.58;
  const placed: { x0: number; x1: number; row: number }[] = [];
  const notes = (opts.annotations ?? []).flatMap((a) => {
    const i = years.indexOf(a.year);
    if (i < 0) return [];
    const w = a.label.length * charW;
    const left = xs[i] > sz.left + (sz.width - sz.left) * 0.55;
    const x0 = left ? xs[i] - 4 - w : xs[i] + 4;
    const x1 = x0 + w;
    let row = 0;
    while (placed.some((p) => p.row === row && x0 < p.x1 + 6 && x1 > p.x0 - 6)) row++;
    placed.push({ x0, x1, row });
    return [{ i, label: a.label, left, ty: sz.top + 2 + row * sz.font * 1.3 }];
  });
  return { right, xs, y, xTicks, notes };
}

/** One line's path, lifting the pen over missing years. */
export function linePath(xs: number[], y: (v: number) => number, values: (number | null)[]): string {
  let d = "";
  let pen = false;
  values.forEach((v, i) => {
    if (v == null) { pen = false; return; }
    d += `${pen ? "L" : "M"}${n1(xs[i])},${n1(y(v))}`;
    pen = true;
  });
  return d;
}

export function linePlotSvg(sz: Size, years: string[], lines: PlotLine[], format: (v: number) => string, label: string, opts: PlotOptions = {}): string {
  const ticks = plotTicks(lines, opts.zero ?? true);
  const { right, xs, y, xTicks, notes } = lineGeometry(sz, years, lines, ticks, opts);
  const bottom = sz.height - sz.bottom;
  const out: string[] = [];
  for (const t of ticks) {
    out.push(`<line x1="${sz.left}" x2="${sz.width - right}" y1="${n1(y(t))}" y2="${n1(y(t))}" class="${t === 0 ? "baseline" : "gridline"}"/>`);
    out.push(`<text x="${sz.left - 6}" y="${n1(y(t))}" dy="0.32em" text-anchor="end" class="tick">${esc(format(t))}</text>`);
  }
  for (const i of xTicks) {
    const anchor = i === years.length - 1 && right < 30 ? "end" : "middle";
    out.push(`<text x="${n1(xs[i])}" y="${sz.height - 8}" text-anchor="${anchor}" class="tick">${esc(years[i])}</text>`);
  }
  for (const n of notes) {
    out.push(`<g class="annotation"><line x1="${n1(xs[n.i])}" x2="${n1(xs[n.i])}" y1="${sz.top}" y2="${bottom}"/>`
      + `<text x="${n1(n.left ? xs[n.i] - 4 : xs[n.i] + 4)}" y="${n1(n.ty)}" dy="0.8em" text-anchor="${n.left ? "end" : "start"}" class="tick">${esc(n.label)}</text></g>`);
  }
  for (const l of lines) {
    const dash = l.dashed ? ` stroke-dasharray="5 4"` : "";
    out.push(`<path d="${linePath(xs, y, l.values)}" fill="none" stroke="${l.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${dash}/>`);
  }
  // Markers: hollow for estimates, filled for the latest value that isn't one.
  const lastOf = (l: PlotLine) => [...l.values.keys()].reverse().find((i) => l.values[i] != null);
  for (const l of lines) {
    const last = lastOf(l);
    l.values.forEach((v, i) => {
      if (v == null) return;
      if (l.estimates?.[i]) out.push(`<circle cx="${n1(xs[i])}" cy="${n1(y(v))}" r="4" fill="var(--surface)" stroke="${l.color}" stroke-width="2"/>`);
      else if (i === last) out.push(`<circle cx="${n1(xs[i])}" cy="${n1(y(v))}" r="4" fill="${l.color}" stroke="var(--surface)" stroke-width="2"/>`);
    });
  }
  const endAt = right > 40 && lines.length === 1 ? lastOf(lines[0]) : undefined;
  if (endAt != null) {
    const v = lines[0].values[endAt]!;
    out.push(`<text x="${n1(xs[endAt] + 9)}" y="${n1(y(v))}" dy="0.32em" class="end-label">${esc(format(v))}</text>`);
  }
  out.push(`<line class="crosshair" x1="0" x2="0" y1="${sz.top}" y2="${bottom}" visibility="hidden"/>`);
  out.push(`<rect class="hit" x="${sz.left - 6}" y="0" width="${sz.width - right - sz.left + 12}" height="${sz.height}" fill="transparent"/>`);
  return `<svg class="plot plot-${sz.name}" viewBox="0 0 ${sz.width} ${sz.height}" role="img" aria-label="${esc(label)}" data-xs="${xs.map(n1).join(",")}" style="font-size:${sz.font}px">${out.join("")}</svg>`;
}

/** Every size; styles/charts.css shows the one that fits. */
export const linePlots = (years: string[], lines: PlotLine[], format: (v: number) => string, label: string, opts: PlotOptions = {}) =>
  SIZES.map((sz) => linePlotSvg(sz, years, lines, format, label, opts)).join("");

/** Colour slots for a chosen set of lines: each known key in order takes the lowest free slot (1..max lines); the
 *  reference line takes slot 0 and does not count. Unknown and repeated keys are skipped. */
export function assignSlots(keys: string[], known: (key: string) => boolean, refKey: string | undefined, max: number, current: { key: string; slot: number }[] = []) {
  const out = [...current];
  for (const key of keys) {
    if (!known(key) || out.some((c) => c.key === key)) continue;
    if (key === refKey) { out.push({ key, slot: 0 }); continue; }
    if (out.filter((c) => c.key !== refKey).length >= max) continue;
    let slot = 1;
    while (out.some((c) => c.slot === slot)) slot++;
    out.push({ key, slot });
  }
  return out;
}

export const slotColor = (slot: number) => (slot === 0 ? "var(--ink-2)" : `var(--s${slot})`);

/** Years up to the last one in which any of the lines has a value (all years if none has). */
export function yearsWithData(years: string[], lines: { values: (number | null)[] }[]) {
  const last = Math.max(-1, ...lines.flatMap((l) => l.values.map((v, i) => (v == null ? -1 : i))));
  return last >= 0 ? years.slice(0, last + 1) : years;
}

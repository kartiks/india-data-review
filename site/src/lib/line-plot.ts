// SVG markup for a plain multi-line chart, as a string, so the same drawing runs at build time and in the browser
// (charts whose lines the reader chooses). Same geometry and classes as LineChart.astro; no estimates or annotations.
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
}

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const n1 = (v: number) => v.toFixed(1);

/** Ticks for the y axis, always including zero. */
export function plotTicks(lines: PlotLine[]): number[] {
  const values = lines.flatMap((l) => l.values).filter((v): v is number => v != null);
  return niceTicks(Math.min(0, ...values), Math.max(0, ...values), 4);
}

export function linePlotSvg(sz: Size, years: string[], lines: PlotLine[], format: (v: number) => string, label: string): string {
  const ticks = plotTicks(lines);
  const right = sz.rightMulti;
  const x = scale(0, years.length - 1, sz.left, sz.width - right);
  const y = scale(ticks[0], ticks[ticks.length - 1], sz.height - sz.bottom, sz.top);
  const xs = years.map((_, i) => x(i));
  const out: string[] = [];
  for (const t of ticks) {
    out.push(`<line x1="${sz.left}" x2="${sz.width - right}" y1="${n1(y(t))}" y2="${n1(y(t))}" class="${t === 0 ? "baseline" : "gridline"}"/>`);
    out.push(`<text x="${sz.left - 6}" y="${n1(y(t))}" dy="0.32em" text-anchor="end" class="tick">${esc(format(t))}</text>`);
  }
  for (const i of xTickIndices(years.length, sz.xLabels)) {
    const anchor = i === years.length - 1 && right < 30 ? "end" : "middle";
    out.push(`<text x="${n1(xs[i])}" y="${sz.height - 8}" text-anchor="${anchor}" class="tick">${esc(years[i])}</text>`);
  }
  for (const l of lines) {
    let d = "";
    let pen = false;
    l.values.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${n1(xs[i])},${n1(y(v))}`;
      pen = true;
    });
    const dash = l.dashed ? ` stroke-dasharray="5 4"` : "";
    out.push(`<path d="${d}" fill="none" stroke="${l.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"${dash}/>`);
  }
  for (const l of lines) {
    const last = [...l.values.keys()].reverse().find((i) => l.values[i] != null);
    if (last != null) out.push(`<circle cx="${n1(xs[last])}" cy="${n1(y(l.values[last]!))}" r="4" fill="${l.color}" stroke="var(--surface)" stroke-width="2"/>`);
  }
  out.push(`<line class="crosshair" x1="0" x2="0" y1="${sz.top}" y2="${sz.height - sz.bottom}" visibility="hidden"/>`);
  out.push(`<rect class="hit" x="${sz.left - 6}" y="0" width="${sz.width - right - sz.left + 12}" height="${sz.height}" fill="transparent"/>`);
  return `<svg class="plot plot-${sz.name}" viewBox="0 0 ${sz.width} ${sz.height}" role="img" aria-label="${esc(label)}" data-xs="${xs.map(n1).join(",")}" style="font-size:${sz.font}px">${out.join("")}</svg>`;
}

/** Both sizes (phone and wider screens); CSS shows one. */
export const linePlots = (years: string[], lines: PlotLine[], format: (v: number) => string, label: string) =>
  SIZES.map((sz) => linePlotSvg(sz, years, lines, format, label)).join("");

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

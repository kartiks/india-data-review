// Number formatting in Indian units. All amounts in the data are Rs crore.
// 1 lakh crore = 100,000 crore (about Rs 1 trillion).
// Negative values get a true minus sign (−), chosen after rounding: a value that rounds to zero has none.

const inr = (digits: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

/** `v` rounded to `digits` decimals, as it will be shown (half away from zero, like Intl and toFixed for display). */
const shown = (v: number, digits: number) => Number(Math.abs(v).toFixed(digits));
/** "−" if `v` is negative and doesn't round to zero at `digits` decimals. */
const minus = (v: number, digits: number) => (v < 0 && shown(v, digits) !== 0 ? "−" : "");
/** "−" for any negative value (for amounts too large to round to zero). */
const neg = (v: number) => (v < 0 ? "−" : "");

/** "₹53.47 lakh crore" or "₹42,100 crore". The unit is picked after rounding: 99,999.6 is "₹1.00 lakh crore". */
export function money(crore: number, opts: { digits?: number } = {}): string {
  const a = Math.abs(crore);
  if (shown(a, 0) >= 100000) {
    const d = opts.digits ?? 2;
    return `${neg(crore)}₹${inr(d).format(a / 100000)} lakh crore`;
  }
  if (shown(a, 1) >= 100) return `${minus(crore, 0)}₹${inr(0).format(a)} crore`;
  const d = shown(a, 2) >= 10 ? 1 : 2;
  return `${minus(crore, d)}₹${inr(d).format(a)} crore`;
}

/** Compact for axes and tight labels: "53L Cr", "5.3L Cr", "42K Cr", "850 Cr". The unit is picked after rounding. */
export function moneyShort(crore: number): string {
  const a = Math.abs(crore);
  if (shown(a / 1000, 0) >= 100) {
    const d = shown(a / 100000, 1) >= 10 ? 0 : 1;
    return `${neg(crore)}${inr(d).format(a / 100000)}L Cr`;
  }
  if (shown(a, 0) >= 1000) return `${neg(crore)}${inr(0).format(a / 1000)}K Cr`;
  return `${minus(crore, 0)}${inr(0).format(a)} Cr`;
}

/** Exact, as printed: "₹53,47,315 crore". */
export function exact(crore: number): string {
  const digits = Number.isInteger(crore) ? 0 : 2;
  return `${minus(crore, digits)}₹${inr(digits).format(Math.abs(crore))} crore`;
}

/** Share or rate: "12.3%", "−1.3%". */
export const pct = (v: number, digits = 1) => `${minus(v, digits)}${Math.abs(v).toFixed(digits)}%`;
/** Change with its sign: "+3.2%", "−3.2%", "0.0%". */
export const signedPct = (v: number, digits = 1) =>
  `${shown(v, digits) === 0 ? "" : v > 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}%`;

/** "2026-27" -> "FY 2026-27" (for fiscal-year arithmetic, see fy.ts). */

/** Split for display: { num: "₹53.47", unit: "lakh crore" }. */
export function moneyParts(crore: number): { num: string; unit: string } {
  const s = money(crore);
  const m = s.match(/^(.*?)\s(lakh crore|crore)$/);
  return m ? { num: m[1], unit: m[2] } : { num: s, unit: "" };
}

/** Growth rate with a true minus sign: "7.8%", "−5.7%". */
export const gpct = (v: number, digits = 1) => `${minus(v, digits)}${Math.abs(v).toFixed(digits)}%`;
/** Change in percentage points: "+1.8 pts", "−0.4 pts", "±0.0 pts". */
export const pts = (v: number) => `${shown(v, 1) === 0 ? "±" : v > 0 ? "+" : "−"}${Math.abs(v).toFixed(1)} pts`;
/** Axis label for growth: "8%", "−4%". */
export const axisPct = (v: number) => `${v < 0 ? "−" : ""}${Math.abs(v)}%`;

/** A plain number with Indian grouping and a fixed number of decimals: "1,438.1". */
export const decimal = (v: number, digits = 1) => `${minus(v, digits)}${inr(digits).format(Math.abs(v))}`;
/** A figure, or an en dash where there is none: orDash(r.growth, gpct). */
export const orDash = (v: number | null | undefined, fmt: (v: number) => string) => (v == null ? "–" : fmt(v));

/** Rupees (not crore), Indian grouping: "₹2,43,107". */
export const rupees = (v: number) => `${minus(v, 0)}₹${inr(0).format(Math.abs(v))}`;
/** Rupees for axes: "₹50,000", "₹1.5 lakh". */
export const rupeesAxis = (v: number) =>
  shown(v, 0) >= 100000
    ? `${neg(v)}₹${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(Math.abs(v) / 100000)} lakh`
    : rupees(v);

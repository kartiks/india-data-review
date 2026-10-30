// Number formatting in Indian units. All amounts in the data are Rs crore.
// 1 lakh crore = 100,000 crore (about Rs 1 trillion).

const inr = (digits: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

/** "₹53.47 lakh crore" or "₹42,100 crore". */
export function money(crore: number, opts: { digits?: number } = {}): string {
  const sign = crore < 0 ? "−" : "";
  const a = Math.abs(crore);
  if (a >= 100000) return `${sign}₹${inr(opts.digits ?? 2).format(a / 100000)} lakh crore`;
  if (a >= 100) return `${sign}₹${inr(0).format(a)} crore`;
  return `${sign}₹${inr(a >= 10 ? 1 : 2).format(a)} crore`;
}

/** Compact for axes and tight labels: "53.5L Cr", "42,100 Cr". */
export function moneyShort(crore: number): string {
  const sign = crore < 0 ? "−" : "";
  const a = Math.abs(crore);
  if (a >= 100000) return `${sign}${inr(a >= 1000000 ? 0 : 1).format(a / 100000)}L Cr`;
  if (a >= 1000) return `${sign}${inr(0).format(a / 1000)}K Cr`;
  return `${sign}${inr(0).format(a)} Cr`;
}

/** Exact, as printed: "₹53,47,315 crore". */
export function exact(crore: number): string {
  const digits = Number.isInteger(crore) ? 0 : 2;
  return `${crore < 0 ? "−" : ""}₹${inr(digits).format(Math.abs(crore))} crore`;
}

export const pct = (v: number, digits = 1) => `${v.toFixed(digits)}%`;
export const signedPct = (v: number, digits = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;

/** "2026-27" -> "FY 2026-27". */
export const fy = (y: string) => `FY ${y}`;

/** Split for display: { num: "₹53.47", unit: "lakh crore" }. */
export function moneyParts(crore: number): { num: string; unit: string } {
  const s = money(crore);
  const m = s.match(/^(.*?)\s(lakh crore|crore)$/);
  return m ? { num: m[1], unit: m[2] } : { num: s, unit: "" };
}

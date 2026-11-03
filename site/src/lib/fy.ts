// Indian fiscal years run from April to March and are written "2024-25". The one that ends in 2000 is
// "1999-00"; some sources write it "1999-2000", which these helpers read too (fyNormal turns it into
// the usual form). Every fiscal-year calculation on the site goes through here.

const FY = /^(\d{4})-(\d{2}|\d{4})$/;

/** Is this a fiscal year ("2024-25" or "1999-2000"), rather than a calendar year ("2025")? */
export const isFy = (y: string) => FY.test(y);

/** First calendar year of a fiscal year: "2024-25" -> 2024, "1999-2000" -> 1999. */
export function fyStart(y: string): number {
  const m = FY.exec(y);
  if (!m) throw new Error(`Not a fiscal year: "${y}"`);
  return Number(m[1]);
}

/** The fiscal year that starts in a calendar year: 2024 -> "2024-25", 1999 -> "1999-00". */
export const fyLabel = (start: number) => `${start}-${String(start + 1).slice(-2)}`;

/** "1999-2000" -> "1999-00"; "2024-25" unchanged. */
export const fyNormal = (y: string) => fyLabel(fyStart(y));

/** The year before: "2024-25" -> "2023-24", "2000-01" -> "1999-00". */
export const prevFy = (y: string) => fyLabel(fyStart(y) - 1);

/** The year after: "2024-25" -> "2025-26", "1998-99" -> "1999-00". */
export const nextFy = (y: string) => fyLabel(fyStart(y) + 1);

/** Every fiscal year from `from` to `to`, both included: ("2022-23", "2024-25") -> 3 years. Empty if to < from. */
export function fyRange(from: string, to: string): string[] {
  const out: string[] = [];
  for (let s = fyStart(from); s <= fyStart(to); s++) out.push(fyLabel(s));
  return out;
}

/** Number of years from one fiscal year to another: ("2011-12", "2024-25") -> 13. */
export const fyGap = (from: string, to: string) => fyStart(to) - fyStart(from);

/** First and last month of a fiscal year: "2024-25" -> ["2024-04", "2025-03"]. */
export function fyMonths(y: string): [string, string] {
  const s = fyStart(y);
  return [`${s}-04`, `${s + 1}-03`];
}

/** Fiscal years starting in `firstStart` or later whose last month (March) is no later than `lastMonth` ("2026-09"). */
export function completeFys(firstStart: number, lastMonth: string): string[] {
  const out: string[] = [];
  for (let s = firstStart; fyMonths(fyLabel(s))[1] <= lastMonth; s++) out.push(fyLabel(s));
  return out;
}

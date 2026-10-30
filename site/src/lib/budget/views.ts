// Per-year views built from the verified data. Every row keeps the value's estimate type and source.
import {
  type Kind, type Value, YEARS, MINISTRIES, SCHEMES, KIND_LABEL,
  headline, taxMix, statesShare, ministryTotal, schemeValue, best,
} from "./data";

export interface Part { id: string; label: string; value: number; href?: string; note?: string }

/** Where each rupee comes from: gross taxes by type, non-tax revenue, other receipts, borrowing. */
export function comesFrom(year: string, kind: Kind): Part[] | undefined {
  const mix = taxMix(year, kind);
  const nonTax = headline(year, "non_tax_revenue", kind);
  const rec = headline(year, "recoveries_of_loans", kind);
  const other = headline(year, "other_receipts", kind);
  const borrow = headline(year, "borrowings", kind);
  if (!mix || !nonTax || !borrow) return undefined;
  const parts: Part[] = [
    ...mix.parts.filter((p) => p.value > 0).map((p) => ({ id: p.id, label: p.label, value: p.value, href: "/budget/taxes/" })),
    { id: "non_tax", label: "Non-tax revenue (dividends, interest, fees)", value: nonTax.value },
    { id: "non_debt", label: "Loan recoveries and disinvestment", value: (rec?.value ?? 0) + (other?.value ?? 0) },
    { id: "borrowing", label: "Borrowing (fiscal deficit)", value: borrow.value },
  ];
  return parts.sort((a, b) => b.value - a.value);
}

/** Where each rupee goes: states' share of taxes, interest, then ministries (Finance shown without interest). */
export function goesTo(year: string, kind: Kind, top = 9): Part[] | undefined {
  const states = statesShare(year, kind);
  const interest = headline(year, "interest_payments", kind);
  if (!states || !interest) return undefined;
  const mins = MINISTRIES.map((m) => {
    const t = ministryTotal(year, m, kind);
    if (!t) return null;
    const value = m.id === "finance" ? t.value - interest.value : t.value;
    const label = m.id === "finance" ? `${m.name} (excluding interest)` : m.name;
    return { id: m.id, label, value, href: `/budget/ministries/${m.id}/` };
  }).filter((x): x is Part & { href: string } => !!x && x.value > 0);
  mins.sort((a, b) => b.value - a.value);
  const rest = mins.slice(top).reduce((s, m) => s + m.value, 0);
  const named: Part[] = [
    { id: "states", label: "States' share of central taxes", value: states.value, href: "/budget/taxes/" },
    { id: "interest", label: "Interest on government debt", value: interest.value, href: "/budget/trends/#interest" },
    ...mins.slice(0, top),
  ].sort((a, b) => b.value - a.value);
  return [...named, { id: "rest", label: `All other ministries (${mins.length - top})`, value: rest, href: "/budget/ministries/" }];
}

export interface Tile { label: string; value: Value | undefined; extra?: string }

/** The previous year's figure to compare against: same type if available, else the best available. */
export function previous(year: string, get: (y: string, k: Kind) => Value | undefined, kind: Kind) {
  const i = YEARS.indexOf(year);
  if (i <= 0) return undefined;
  const prev = YEARS[i - 1];
  const v = kind === "be" ? get(prev, "re") ?? get(prev, "be") : get(prev, kind) ?? best((k) => get(prev, k));
  return v ? { year: prev, v } : undefined;
}

export interface Gap { label: string; be: number; outcome: number; outcomeKind: string; href?: string; note?: string }

/** Budget Estimate vs the latest figure (Actual, else Revised) for headline items and the biggest ministries. */
export function promiseGaps(year: string): { kind: Kind; rows: Gap[] } | undefined {
  const outcomeKind: Kind | undefined = headline(year, "total_expenditure", "actual")
    ? "actual"
    : headline(year, "total_expenditure", "re") ? "re" : undefined;
  if (!outcomeKind) return undefined;
  const rows: Gap[] = [];
  const add = (label: string, be?: Value, out?: Value, href?: string) => {
    if (be && out) rows.push({ label, be: be.value, outcome: out.value, outcomeKind: KIND_LABEL[outcomeKind], href, note: out.source.note ?? be.source.note });
  };
  for (const [field, label] of [
    ["total_expenditure", "Total spending"],
    ["capital_expenditure", "Capital spending (infrastructure, assets)"],
    ["tax_revenue_net", "Tax revenue (Centre's share)"],
    ["non_tax_revenue", "Non-tax revenue"],
    ["fiscal_deficit", "Borrowing (fiscal deficit)"],
  ] as const) {
    add(label, headline(year, field, "be"), headline(year, field, outcomeKind), "/budget/trends/");
  }
  const big = MINISTRIES.map((m) => ({ m, be: ministryTotal(year, m, "be"), out: ministryTotal(year, m, outcomeKind) }))
    .filter((x) => x.be && x.out && x.m.id !== "finance")
    .sort((a, b) => b.be!.value - a.be!.value)
    .slice(0, 6);
  for (const x of big) add(x.m.name, x.be, x.out, `/budget/ministries/${x.m.id}/`);
  return { kind: outcomeKind, rows };
}

export function topSchemes(year: string, kind: Kind, n = 10) {
  return SCHEMES.map((s) => ({ s, v: schemeValue(year, s.key, kind) }))
    .filter((x): x is { s: (typeof SCHEMES)[number]; v: Value } => !!x.v && x.v.value > 0)
    .sort((a, b) => b.v.value - a.v.value)
    .slice(0, n);
}

/** Context a reader needs for particular years (one-off events that distort the figures). */
export const YEAR_NOTES: Record<string, string> = Object.fromEntries(
  ["2002-03", "2003-04", "2004-05"].map((y) => [
    y,
    "This year includes large one-off debt transactions: states prepaying central loans under the Debt Swap Scheme " +
      "(which inflates loan recoveries) and repayments to the National Small Savings Fund counted as capital spending. " +
      "Capital and total spending look higher than the real spending on assets and services.",
  ]),
);
YEAR_NOTES["2007-08"] =
  "2007-08 spending and receipts include about ₹35,500 crore for the transfer of RBI's stake in State Bank of India to the government.";

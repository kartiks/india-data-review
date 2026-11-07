// One measure for components/StateMap.astro to colour the map by.

export interface MapMetric {
  id: string;
  label: string; // button text
  title: string; // shown above the map when selected
  note?: string;
  values: Record<string, number | null>; // keyed by stateKey() from lib/states
  format: (v: number) => string;
}

/** A map metric with one value per row, keyed by the row's `key` (a stateKey()); a missing value is null. */
export function mapMetric<R extends { key: string }>(
  rows: readonly R[],
  m: Omit<MapMetric, "values">,
  get: (r: R) => number | null | undefined,
): MapMetric {
  return { ...m, values: Object.fromEntries(rows.map((r) => [r.key, get(r) ?? null])) };
}

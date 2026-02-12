export function formatCrore(value: number): string {
  if (value === 0) return "N/A";
  if (Math.abs(value) >= 100000) {
    return `${(value / 100000).toFixed(1)}L Cr`;
  }
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(1)}K Cr`;
  }
  return `${value.toFixed(0)} Cr`;
}

export function formatCroreShort(value: number): string {
  if (value === 0) return "N/A";
  if (Math.abs(value) >= 100000) {
    return `${(value / 100000).toFixed(1)}L`;
  }
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(0)}K`;
  }
  return `${value.toFixed(0)}`;
}

export function formatPercent(value: number): string {
  if (value === 0) return "N/A";
  return `${value.toFixed(1)}%`;
}

export function shortYear(year: string): string {
  const parts = year.split("-");
  if (parts.length === 2) {
    return `'${parts[0].slice(2)}`;
  }
  return year;
}

export function getGrowthPercent(current: number, previous: number): number {
  if (previous === 0) return 0;
  return ((current - previous) / previous) * 100;
}

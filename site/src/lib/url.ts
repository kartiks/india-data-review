// Internal links must respect the site's base path (e.g. "/india-budget-site/" on GitHub Pages).
// Write paths from the site root ("/taxes/") and pass them through link().
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export function link(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path; // external or relative: leave alone
  return `${BASE}${path}`;
}

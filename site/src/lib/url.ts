// Internal links must respect the site's base path (astro.config's `base`, from SITE_BASE: "/" on
// the live site, a subpath such as "/india-data-review/" in other builds). Write paths from the site
// root ("/budget/taxes/") and pass them through link(), in pages and in client <script> modules alike.
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

export function link(path: string): string {
  if (!path.startsWith("/") || path.startsWith("//")) return path; // external or relative: leave alone
  return `${BASE}${path}`;
}

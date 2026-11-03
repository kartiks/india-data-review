import { defineConfig } from "astro/config";

// Fully static site: every page is pre-rendered from the verified datasets in each area's data/ folder
// (../budget/data, ../gdp/data, ../jobs-prices/data).
// Optional overrides, set by nothing in this repository (Vercel serves the site at the root of its domain):
// SITE_URL is the address used in canonical and og:url links (default: the live domain), and SITE_BASE a path to
// serve the site under, e.g. "/preview/" (internal links go through link() in src/lib/url.ts so they follow it).
export default defineConfig({
  output: "static",
  site: process.env.SITE_URL || "https://india-data-review.k4tech.in",
  base: process.env.SITE_BASE || "/",
  trailingSlash: "always",
  build: { format: "directory" },
});

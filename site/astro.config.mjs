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
  // Content-Security-Policy, as a <meta> tag on every page: Astro adds the hash of each script and stylesheet it
  // emits (components/InlineScript.astro adds the few inline scripts it does not bundle). Everything the site loads
  // is its own: pages, scripts, styles, /data/ downloads, the scheme search index and, on Vercel, the analytics
  // script and its beacon (/_vercel/insights/). frame-ancestors cannot be set by a <meta> tag: it is sent as a header
  // (vercel.json), with the other security headers.
  security: {
    csp: {
      directives: ["default-src 'self'", "base-uri 'self'", "form-action 'self'", "object-src 'none'"],
      styleDirective: {
        // Charts and bars are sized and coloured with style attributes, some drawn by scripts in the browser. Inline
        // style attributes cannot run code; <style> elements and stylesheets still need a hash or 'self'.
        // (Astro warns that style-src's 'self' does not carry over to style-src-attr: that is intended.)
        resources: ["'self'", { resource: "'unsafe-inline'", kind: "attribute" }],
      },
    },
  },
  // No Markdown pages; Shiki's code highlighting would need inline styles, so turn it off (Astro warns otherwise).
  markdown: { syntaxHighlight: false },
});

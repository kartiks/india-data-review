import { defineConfig } from "astro/config";

// Fully static site: every page is pre-rendered from the verified datasets in ../data.
// SITE_URL / SITE_BASE are set by the deploy workflow (e.g. GitHub Pages serves under /<repo>/).
export default defineConfig({
  output: "static",
  site: process.env.SITE_URL || undefined,
  base: process.env.SITE_BASE || "/",
  trailingSlash: "always",
  build: { format: "directory" },
});

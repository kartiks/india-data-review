import { defineConfig } from "astro/config";

// Fully static site: every page is pre-rendered from the verified datasets in ../data.
export default defineConfig({
  output: "static",
  trailingSlash: "always",
  build: { format: "directory" },
});

import { defineConfig } from "vitest/config";

// Unit tests for the site's TypeScript (npm test). The data modules read ../<area>/data/*.json relative to the
// working directory, as in an Astro build, so run from site/. DOM tests opt in with `// @vitest-environment happy-dom`.
export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
  },
});

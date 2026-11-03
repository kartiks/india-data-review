import { afterEach, describe, expect, it, vi } from "vitest";

// link() reads the base path when the module loads, so each case stubs it and imports a fresh copy.
async function linkWithBase(base: string) {
  vi.stubEnv("BASE_URL", base);
  vi.resetModules();
  return (await import("../src/lib/url")).link;
}
afterEach(() => vi.unstubAllEnvs());

describe("link", () => {
  it("leaves root paths alone when the site is at the root", async () => {
    const link = await linkWithBase("/");
    expect(link("/budget/taxes/")).toBe("/budget/taxes/");
    expect(link("/")).toBe("/");
  });
  it("prefixes root paths with a sub-path base, with or without its trailing slash", async () => {
    for (const base of ["/india-data-review/", "/india-data-review"]) {
      const link = await linkWithBase(base);
      expect(link("/budget/taxes/")).toBe("/india-data-review/budget/taxes/");
      expect(link("/")).toBe("/india-data-review/");
    }
  });
  it("leaves external, protocol-relative and relative links alone", async () => {
    const link = await linkWithBase("/india-data-review/");
    expect(link("https://indiabudget.gov.in/")).toBe("https://indiabudget.gov.in/");
    expect(link("//example.org/x")).toBe("//example.org/x");
    expect(link("taxes/")).toBe("taxes/");
    expect(link("#interest")).toBe("#interest");
  });
});

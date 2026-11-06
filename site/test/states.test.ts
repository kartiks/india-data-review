import fs from "node:fs";
import { describe, expect, it } from "vitest";
import { stateKey } from "../src/lib/states";

// Shared with the jobs and prices pipeline's test of its own state_key, so the two rules cannot drift apart.
const fixture = JSON.parse(fs.readFileSync(new URL("../../shared/fixtures/state-names.json", import.meta.url), "utf8")) as {
  names: Record<string, string>;
};

describe("stateKey", () => {
  it("gives every spelling in shared/fixtures/state-names.json its key", () => {
    expect(Object.keys(fixture.names).length).toBeGreaterThan(10);
    for (const [name, key] of Object.entries(fixture.names)) expect(stateKey(name), name).toBe(key);
  });
  it("keeps different states apart", () => {
    expect(stateKey("Tamil Nadu")).not.toBe(stateKey("Telangana"));
    expect(stateKey("Dadra & Nagar Haveli")).not.toBe(stateKey("Dadra & Nagar Haveli and Daman & Diu"));
  });
});

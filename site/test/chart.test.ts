import { describe, expect, it } from "vitest";
import { niceTicks } from "../src/lib/chart";

describe("niceTicks", () => {
  it("covers the range with round steps", () => {
    expect(niceTicks(0, 100, 4)).toEqual([0, 25, 50, 75, 100]);
    expect(niceTicks(0, 9.3, 4)).toEqual([0, 2.5, 5, 7.5, 10]);
    expect(niceTicks(-5.8, 9.1, 4)).toEqual([-10, -5, 0, 5, 10]);
    expect(niceTicks(0, 5347315, 4)).toEqual([0, 2000000, 4000000, 6000000]);
  });
  it("keeps decimal steps exact", () => {
    expect(niceTicks(0, 0.3, 3)).toEqual([0, 0.1, 0.2, 0.3]);
  });
  it("widens a single value into a range", () => {
    const t = niceTicks(5, 5, 4);
    expect(t[0]).toBeLessThanOrEqual(5);
    expect(t[t.length - 1]).toBeGreaterThan(5);
  });
  it("gives finite ticks when there are no values (min = Infinity, max = -Infinity, as Math.min/max of [] give)", () => {
    const t = niceTicks(Math.min(), Math.max(), 4);
    expect(t.length).toBeGreaterThan(1);
    expect(t.every(Number.isFinite)).toBe(true);
  });
});

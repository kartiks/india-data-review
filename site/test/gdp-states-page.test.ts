// What /gdp/states/ shows (src/lib/gdp/states-page.ts), on the committed state accounts.
import { describe, expect, it } from "vitest";
import { growthLines, stateMetrics, stateRankings, stateRows } from "../src/lib/gdp/states-page";
import { BOUNDARY, FIRST_YEAR, LATEST, SECTORS, STATES, STATE_YEARS, sNode } from "../src/lib/gdp/states";
import { stateKey } from "../src/lib/states";

const rows = stateRows();

describe("stateRows", () => {
  it("has one row per state, keyed by stateKey, for the year compared", () => {
    expect(rows.map((r) => r.st)).toEqual(STATES);
    for (const r of rows) {
      expect(r.key).toBe(stateKey(r.st));
      expect(r.gsdp).toBe(sNode(r.st, LATEST)?.gsdp?.cur ?? null);
    }
  });
  it("marks a boundary change only inside the period compared", () => {
    for (const r of rows) {
      const b = BOUNDARY[r.st];
      expect(r.boundary).toBe(!!b && b.until >= FIRST_YEAR && b.until < LATEST);
    }
    expect(stateRows(FIRST_YEAR).some((r) => r.boundary)).toBe(false);
  });
  it("has sector shares that add up to 100% (to rounding) where there are any", () => {
    for (const r of rows.filter((r) => r.shares)) {
      expect(SECTORS.reduce((a, s) => a + r.shares![s], 0)).toBeCloseTo(100, 1);
    }
  });
});

describe("stateMetrics", () => {
  const metrics = stateMetrics(rows);
  it("has the four measures and one per sector, with unique ids", () => {
    expect(metrics.map((m) => m.id)).toEqual(["size", "growth", "avg", "income", ...SECTORS]);
  });
  it("gives every state a value or null", () => {
    for (const m of metrics) expect(Object.keys(m.values).sort()).toEqual(rows.map((r) => r.key).sort());
    const size = metrics[0];
    for (const r of rows) expect(size.values[r.key]).toBe(r.gsdp);
  });
});

describe("stateRankings", () => {
  const { all, total, sizeRows, incomeRows, richest } = stateRankings(rows);
  it("lists the 12 largest economies, largest first, with their share of all states", () => {
    expect(sizeRows).toHaveLength(Math.min(12, all.length));
    for (let i = 1; i < sizeRows.length; i++) expect(sizeRows[i].value).toBeLessThanOrEqual(sizeRows[i - 1].value);
    expect(total).toBeCloseTo(all.reduce((a, r) => a + r.gsdp!, 0));
    expect(sizeRows[0].sub).toMatch(/% of all states$/);
  });
  it("lists the six highest and six lowest incomes per person, by rank", () => {
    expect(incomeRows).toHaveLength(Math.min(12, richest.length));
    expect(incomeRows[0].label).toBe(`1. ${richest[0].st}`);
    expect(incomeRows[incomeRows.length - 1].label).toBe(`${richest.length}. ${richest[richest.length - 1].st}`);
  });
});

describe("growthLines", () => {
  const g = growthLines();
  it("runs from the year after the first to the latest any state has published", () => {
    expect(g.years[0] > FIRST_YEAR).toBe(true);
    expect(g.last).toBe(STATE_YEARS[STATE_YEARS.length - 1]);
    expect(g.lastCount).toBeGreaterThan(0);
  });
  it("has a line, aligned with the years, for every state with a figure, and lists the rest", () => {
    for (const o of [...g.options, g.reference]) {
      expect(o.values).toHaveLength(g.years.length);
      expect(o.kinds).toHaveLength(g.years.length);
    }
    for (const o of g.options) expect(o.values.some((v) => v != null)).toBe(true);
    expect([...g.options.map((o) => o.name), ...g.noGrowth].sort()).toEqual([...STATES].sort());
  });
  it("labels growth worked out from the levels, and the year after a boundary change", () => {
    for (const o of g.options) {
      g.years.forEach((y, i) => {
        if (sNode(o.name, y)?.growth?.gsdp?.published === false) expect(o.kinds![i]).toBe("worked out");
      });
      const b = BOUNDARY[o.name];
      if (b) expect(o.kinds).toContain("area changed");
      if (o.kinds!.includes("worked out")) expect(o.note).toMatch(/growth worked out here from GSDP levels/);
    }
  });
  it("has All India as the reference line", () => {
    expect(g.reference).toMatchObject({ key: "india", name: "All India" });
    expect(g.reference.values.some((v) => v != null)).toBe(true);
  });
});

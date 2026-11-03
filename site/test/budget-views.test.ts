import { describe, expect, it } from "vitest";
import { comesFrom, goesTo, previous, promiseGaps, topSchemes, YEAR_NOTES } from "../src/lib/budget/views";
import { type Kind, YEARS, LATEST_YEAR, SCHEME_YEARS, KINDS, headline, statesShare, yearKind } from "../src/lib/budget/data";

const total = (y: string, k: Kind) => headline(y, "total_expenditure", k);
const sample = [YEARS[0], "2010-11", "2020-21", LATEST_YEAR];
const sortedDown = (xs: number[]) => xs.every((v, i) => i === 0 || xs[i - 1] >= v);

describe("goesTo", () => {
  it("adds up to total spending plus the states' share of taxes, for every year and estimate", () => {
    for (const y of YEARS) for (const k of KINDS) {
      const parts = goesTo(y, k);
      if (!parts) continue;
      const sum = parts.reduce((s, p) => s + p.value, 0);
      expect(Math.abs(sum - statesShare(y, k)!.value - total(y, k)!.value), `${y} ${k}`).toBeLessThan(2);
    }
  });
  it("lists the named parts largest first and the rest last", () => {
    const parts = goesTo(LATEST_YEAR, "be", 9)!;
    expect(parts).toHaveLength(12); // states, interest, 9 ministries, the rest
    expect(parts.at(-1)!.id).toBe("rest");
    expect(sortedDown(parts.slice(0, -1).map((p) => p.value))).toBe(true);
    expect(parts.every((p) => p.value > 0)).toBe(true);
    expect(parts.find((p) => p.id === "finance")?.label).toMatch(/excluding interest/);
  });
});

describe("comesFrom", () => {
  it("is positive, largest first, and includes borrowing", () => {
    for (const y of sample) {
      const parts = comesFrom(y, "be")!;
      expect(sortedDown(parts.map((p) => p.value))).toBe(true);
      expect(parts.every((p) => p.value >= 0)).toBe(true);
      expect(parts.some((p) => p.id === "borrowing")).toBe(true);
    }
  });
  it("is missing when the year has no figures of that kind", () => {
    expect(yearKind(LATEST_YEAR)).toBe("be");
    expect(comesFrom(LATEST_YEAR, "actual")).toBeUndefined();
  });
});

describe("previous", () => {
  const get = (y: string, k: Kind) => total(y, k);
  it("has nothing before the first year", () => {
    expect(previous(YEARS[0], get, "be")).toBeUndefined();
  });
  it("compares a Budget Estimate with the year before's Revised Estimate", () => {
    const p = previous(LATEST_YEAR, get, "be")!;
    expect(p.year).toBe(YEARS[YEARS.length - 2]);
    expect(p.v).toEqual(total(p.year, "re"));
  });
  it("compares actuals with actuals", () => {
    const p = previous("2020-21", get, "actual")!;
    expect(p.year).toBe("2019-20");
    expect(p.v).toEqual(total("2019-20", "actual"));
  });
});

describe("promiseGaps", () => {
  it("has nothing for a year with only a Budget Estimate", () => {
    expect(promiseGaps(LATEST_YEAR)).toBeUndefined();
  });
  it("compares the Budget Estimate with the actual where there is one", () => {
    const g = promiseGaps("2020-21")!;
    expect(g.kind).toBe("actual");
    expect(g.rows[0].label).toBe("Total spending");
    expect(g.rows[0].be).toBe(total("2020-21", "be")!.value);
    expect(g.rows[0].outcome).toBe(total("2020-21", "actual")!.value);
    expect(g.rows.some((r) => r.href?.startsWith("/budget/ministries/"))).toBe(true);
  });
});

describe("topSchemes", () => {
  it("returns at most n positive schemes, largest first", () => {
    const y = SCHEME_YEARS[SCHEME_YEARS.length - 1];
    const top = topSchemes(y, "be", 5);
    expect(top).toHaveLength(5);
    expect(sortedDown(top.map((x) => x.v.value))).toBe(true);
    expect(top.every((x) => x.v.value > 0)).toBe(true);
  });
  it("is empty before schemes were shown", () => {
    expect(topSchemes(YEARS[0], "be")).toEqual([]);
  });
});

describe("YEAR_NOTES", () => {
  it("covers the debt-swap years and 2007-08", () => {
    expect(Object.keys(YEAR_NOTES).sort()).toEqual(["2002-03", "2003-04", "2004-05", "2007-08"]);
  });
});

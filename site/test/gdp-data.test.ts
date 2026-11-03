import { describe, expect, it } from "vitest";
import {
  type Node, BROAD, NEW, OLD, STAGE_ORDER, LATEST_YEAR, annual, bestOf, industrySum, latestStage, firstStage, oldBaseOf,
  perPersonGrowth, share, stagesOf, yearsOf,
} from "../src/lib/gdp/data";
import { averageGrowth, coverage, LATEST as STATES_LATEST } from "../src/lib/gdp/states";
import { fyRange, isFy } from "../src/lib/fy";

describe("share", () => {
  it("is part over whole, in percent", () => {
    expect(share(25, 200)).toBe(12.5);
    expect(share(-5, 50)).toBe(-10);
  });
  it("is undefined when either side is missing or the whole is zero", () => {
    expect(share(undefined, 10)).toBeUndefined();
    expect(share(1, undefined)).toBeUndefined();
    expect(share(1, 0)).toBeUndefined();
  });
});

describe("industrySum", () => {
  const full = (v: number): Node => ({ gva_by_industry: Object.fromEntries(BROAD.map((i: string) => [i, { cur: v, con: v / 2 }])) } as Node);
  it("adds the broad industries at current or constant prices", () => {
    expect(industrySum(full(10))).toBe(10 * BROAD.length);
    expect(industrySum(full(10), "con")).toBe(5 * BROAD.length);
  });
  it("is undefined if any broad industry is missing", () => {
    const n = full(10);
    delete (n.gva_by_industry as Record<string, unknown>)[BROAD[0]];
    expect(industrySum(n)).toBeUndefined();
    expect(industrySum({} as Node)).toBeUndefined();
  });
  it("equals published GVA in the latest year of the new series", () => {
    const n = annual(NEW)[LATEST_YEAR][latestStage(NEW, LATEST_YEAR)!];
    const sum = industrySum(n);
    if (sum !== undefined && n.gva?.cur !== undefined) expect(Math.abs(sum - n.gva.cur) / n.gva.cur).toBeLessThan(0.001);
  });
});

describe("stages and picks", () => {
  it("lists a year's stages in publication order", () => {
    for (const y of yearsOf(OLD)) {
      const order = stagesOf(OLD, y).map((s) => STAGE_ORDER[s]);
      expect(order, y).toEqual([...order].sort((a, b) => a - b));
    }
  });
  it("latestStage and firstStage are the ends of that list", () => {
    const s = stagesOf(OLD, "2015-16");
    expect(latestStage(OLD, "2015-16")).toBe(s.at(-1));
    expect(firstStage(OLD, "2015-16")).toBe(s[0]);
    expect(latestStage(OLD, "1900-01")).toBeUndefined();
  });
  it("bestOf picks the latest estimate that has the figure", () => {
    const get = (n: Node) => n.gdp?.cur;
    const [p, none] = bestOf(OLD, ["2015-16", "1900-01"], get);
    expect(p!.stage).toBe(latestStage(OLD, "2015-16", (n) => get(n) !== undefined));
    expect(p!.value).toBe(get(annual(OLD)["2015-16"][p!.stage]));
    expect(none).toBeUndefined();
  });
  it("oldBaseOf uses the back series to 2010-11 and the 2011-12 series after", () => {
    const [a, b] = oldBaseOf(["2010-11", "2011-12"], (n) => n.gdp?.con);
    expect(a?.stage).toBe("BACK");
    expect(b?.series).toBe(OLD);
  });
  it("every year key is a fiscal year", () => {
    for (const s of [OLD, NEW]) for (const y of yearsOf(s)) expect(isFy(y), y).toBe(true);
  });
});

describe("per person and states", () => {
  it("perPersonGrowth needs the year before", () => {
    const ys = yearsOf(NEW).filter((y) => perPersonGrowth(NEW, y) !== undefined);
    expect(ys.length).toBeGreaterThan(0);
    expect(perPersonGrowth(NEW, yearsOf(NEW)[0])).toBeUndefined();
  });
  it("averageGrowth compounds over the number of years", () => {
    const g = averageGrowth("Kerala", "2011-12", STATES_LATEST);
    expect(g).toBeTypeOf("number");
    expect(averageGrowth("Kerala", STATES_LATEST, STATES_LATEST)).toBeUndefined();
  });
  it("coverage is a share between 0 and 1", () => {
    for (const y of fyRange("2012-13", STATES_LATEST)) {
      const c = coverage(y);
      expect(c, y).toBeGreaterThanOrEqual(0);
      expect(c, y).toBeLessThanOrEqual(1);
    }
  });
});

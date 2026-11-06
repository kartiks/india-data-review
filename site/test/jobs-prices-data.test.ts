import { describe, expect, it } from "vitest";
import { completeFys } from "../src/lib/fy";
import {
  type CpiPoint, averageInflation, monthRange, rbiLatestYear, rbiValue, rbiYears, tidyState, yearAverage, RBI,
  CPI_LAST, GENERAL, cpiAllIndia,
} from "../src/lib/jobs-prices/data";

/** Monthly points from `from` to `to` with index = f(month number since start). */
function series(from: string, to: string, f: (i: number) => number | null): CpiPoint[] {
  return monthRange(from, to).map((month, i) => ({ month, index: f(i), inflation: null }));
}

describe("monthRange", () => {
  it("crosses year ends and includes both ends", () => {
    expect(monthRange("2024-11", "2025-02")).toEqual(["2024-11", "2024-12", "2025-01", "2025-02"]);
    expect(monthRange("2025-03", "2025-03")).toEqual(["2025-03"]);
    expect(monthRange("2025-04", "2025-03")).toEqual([]);
  });
});

describe("yearAverage", () => {
  const pts = series("2023-01", "2025-12", (i) => 100 + i); // Jan 2023 = 100, Dec 2025 = 135
  it("averages a calendar year", () => {
    expect(yearAverage(pts, "2024")).toBeCloseTo(117.5); // months 12..23
  });
  it("averages a fiscal year, April to March", () => {
    expect(yearAverage(pts, "2024-25")).toBeCloseTo(120.5); // Apr 2024 (115) .. Mar 2025 (126)
  });
  it("gives nothing when a month is missing", () => {
    expect(yearAverage(pts, "2025-26")).toBeUndefined(); // runs to Mar 2026
    const gap = pts.map((p) => (p.month === "2024-07" ? { ...p, index: null } : p));
    expect(yearAverage(gap, "2024")).toBeUndefined();
    expect(yearAverage(gap, "2024-25")).toBeUndefined();
  });
});

describe("averageInflation", () => {
  const flat = series("2022-04", "2025-03", (i) => (i < 12 ? 100 : i < 24 ? 105 : 110.25));
  it("compares fiscal-year averages", () => {
    expect(averageInflation(flat, "2023-24")).toBeCloseTo(5);
    expect(averageInflation(flat, "2024-25")).toBeCloseTo(5);
  });
  it("compares calendar-year averages", () => {
    const cal = series("2023-01", "2024-12", (i) => (i < 12 ? 200 : 190));
    expect(averageInflation(cal, "2024")).toBeCloseTo(-5);
  });
  it("needs the year before", () => {
    expect(averageInflation(flat, "2022-23")).toBeUndefined();
  });
  it("matches the published series around the turn of the century", () => {
    // fiscal 2000-01 compares with "1999-00", not "1999-2000"
    const old = series("1999-04", "2001-03", (i) => (i < 12 ? 50 : 52));
    expect(averageInflation(old, "2000-01")).toBeCloseTo(4);
  });
  it("gives a figure for each complete fiscal year of the real CPI series", () => {
    const real = cpiAllIndia(GENERAL);
    const years = completeFys(Number(real[0].month.slice(0, 4)) + 1, CPI_LAST);
    expect(years.length).toBeGreaterThan(5);
    for (const y of years) {
      const v = averageInflation(real, y);
      expect(v, y).toBeTypeOf("number");
      expect(Math.abs(v!), y).toBeLessThan(15);
    }
  });
});

describe("state names", () => {
  it("tidyState", () => {
    expect(tidyState("Andaman And Nicobar Islands")).toBe("Andaman & Nicobar Islands");
    expect(tidyState("NCT of Delhi")).toBe("Delhi");
    expect(tidyState("The Dadra And Nagar Haveli")).toBe("Dadra & Nagar Haveli");
  });
});

describe("RBI handbook", () => {
  it("rbiLatestYear picks a year that most states have", () => {
    const y = rbiLatestYear("wage_agriculture");
    expect(rbiYears("wage_agriculture")).toContain(y);
    expect(rbiValue("wage_agriculture", "Kerala", y)).toBeTypeOf("number");
  });
  it("rbiLatestYear refuses a table or variant with no state figures instead of returning undefined", () => {
    expect(() => rbiLatestYear("no_such_table")).toThrow(/no_such_table/);
    expect(() => rbiLatestYear("wage_agriculture", "no such variant")).toThrow(/variant/);
  });
  it("rbiValue matches state names loosely and returns null when missing", () => {
    const y = rbiLatestYear("wage_agriculture");
    const row = RBI.find((r) => r.table_id === "wage_agriculture" && r.year === y && r.state.includes("&"));
    if (row) expect(rbiValue("wage_agriculture", row.state.replace("&", "and"), y)).toBe(row.value);
    expect(rbiValue("wage_agriculture", "Atlantis", y)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { completeFys, fyGap, fyLabel, fyMonths, fyNormal, fyRange, fyStart, isFy, nextFy, prevFy } from "../src/lib/fy";

describe("fiscal years", () => {
  it("reads the first calendar year", () => {
    expect(fyStart("2024-25")).toBe(2024);
    expect(fyStart("1999-00")).toBe(1999);
    expect(fyStart("1999-2000")).toBe(1999);
  });
  it("refuses anything that isn't a fiscal year", () => {
    expect(() => fyStart("2025")).toThrow(/Not a fiscal year/);
    expect(() => fyStart("2024-25-Q1")).toThrow();
    expect(() => fyStart("")).toThrow();
    expect(isFy("2025")).toBe(false);
    expect(isFy("2024-25")).toBe(true);
    expect(isFy("1999-2000")).toBe(true);
  });
  it("labels across the century", () => {
    expect(fyLabel(2024)).toBe("2024-25");
    expect(fyLabel(1999)).toBe("1999-00");
    expect(fyLabel(2000)).toBe("2000-01");
    expect(fyLabel(2009)).toBe("2009-10");
    expect(fyNormal("1999-2000")).toBe("1999-00");
    expect(fyNormal("2024-25")).toBe("2024-25");
  });
  it("steps back and forward", () => {
    expect(prevFy("2024-25")).toBe("2023-24");
    expect(prevFy("2000-01")).toBe("1999-00");
    expect(prevFy("1999-2000")).toBe("1998-99");
    expect(nextFy("1998-99")).toBe("1999-00");
    expect(nextFy("1999-00")).toBe("2000-01");
    expect(nextFy("2009-10")).toBe("2010-11");
  });
  it("lists ranges", () => {
    expect(fyRange("1998-99", "2001-02")).toEqual(["1998-99", "1999-00", "2000-01", "2001-02"]);
    expect(fyRange("2024-25", "2024-25")).toEqual(["2024-25"]);
    expect(fyRange("2024-25", "2023-24")).toEqual([]);
    expect(fyGap("2011-12", "2024-25")).toBe(13);
  });
  it("gives months and complete years", () => {
    expect(fyMonths("2024-25")).toEqual(["2024-04", "2025-03"]);
    expect(fyMonths("1999-00")).toEqual(["1999-04", "2000-03"]);
    expect(completeFys(2022, "2025-03")).toEqual(["2022-23", "2023-24", "2024-25"]);
    expect(completeFys(2022, "2025-02")).toEqual(["2022-23", "2023-24"]);
    expect(completeFys(2022, "2022-12")).toEqual([]);
  });
});

import { describe, expect, it } from "vitest";
import { linePlotSvg } from "../src/lib/line-plot";
import { SIZES } from "../src/lib/chart";
import { axisPct, pct } from "../src/lib/format";

const xl = SIZES.find((s) => s.name === "xl")!;
const sm = SIZES.find((s) => s.name === "sm")!;
const endLabels = (svg: string) => [...svg.matchAll(/class="end-label">([^<]*)</g)].map((m) => m[1]);
const line = (values: (number | null)[]) => ({ name: "Gross saving", color: "var(--s1)", values });

describe("linePlotSvg end label", () => {
  it("formats the last value as the chart's values, not with the axis format", () => {
    const svg = linePlotSvg(xl, ["2023-24", "2024-25"], [line([29.5, 30.7379704282000022])], axisPct, "Saving", { endLabel: true, valueFormat: (v) => pct(v) });
    expect(endLabels(svg)).toEqual([pct(30.7379704282000022)]);
    expect(svg).not.toContain("30.7379704282");
  });
  it("labels the last year with a value, skipping trailing gaps", () => {
    const svg = linePlotSvg(xl, ["a", "b", "c"], [line([1, 2.25, null])], axisPct, "x", { endLabel: true, valueFormat: (v) => v.toFixed(1) });
    expect(endLabels(svg)).toEqual(["2.3"]);
  });
  it("falls back to the axis format, and draws no end label with two lines or where a size has no room", () => {
    expect(endLabels(linePlotSvg(xl, ["a", "b"], [line([1, 2])], axisPct, "x", { endLabel: true }))).toEqual(["2%"]);
    expect(endLabels(linePlotSvg(xl, ["a", "b"], [line([1, 2]), line([3, 4])], axisPct, "x", { endLabel: true }))).toEqual([]);
    expect(endLabels(linePlotSvg(sm, ["a", "b"], [line([1, 2])], axisPct, "x", { endLabel: true }))).toEqual([]);
  });
});

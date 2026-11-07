import { describe, expect, it } from "vitest";
import { mapMetric } from "../src/lib/map-metric";

describe("mapMetric", () => {
  const rows = [{ key: "goa", v: 2 }, { key: "kerala", v: undefined }, { key: "sikkim", v: null }, { key: "bihar", v: 0 }];
  const fmt = (v: number) => `${v}%`;
  it("keys one value per row by the row's key, missing values as null", () => {
    const m = mapMetric(rows, { id: "x", label: "X", title: "X, 2024", note: "n", format: fmt }, (r) => r.v);
    expect(m.values).toEqual({ goa: 2, kerala: null, sikkim: null, bihar: 0 });
    expect(m).toMatchObject({ id: "x", label: "X", title: "X, 2024", note: "n", format: fmt });
  });
});

import { describe, expect, it } from "vitest";
import {
  axisPct, decimal, exact, gpct, money, moneyParts, moneyShort, orDash, pct, pts, rupees, rupeesAxis, signedPct,
} from "../src/lib/format";

describe("money", () => {
  it("uses lakh crore from ₹1 lakh crore up", () => {
    expect(money(5347315)).toBe("₹53.47 lakh crore");
    expect(money(100000)).toBe("₹1.00 lakh crore");
    expect(money(5347315, { digits: 1 })).toBe("₹53.5 lakh crore");
  });
  it("uses whole crore with Indian grouping from ₹100 crore", () => {
    expect(money(42100)).toBe("₹42,100 crore");
    expect(money(99999)).toBe("₹99,999 crore");
    expect(money(100)).toBe("₹100 crore");
  });
  it("keeps one or two decimals for small amounts", () => {
    expect(money(42.25)).toBe("₹42.3 crore");
    expect(money(4.256)).toBe("₹4.26 crore");
    expect(money(0)).toBe("₹0.00 crore");
  });
  it("picks the unit after rounding, so a value never shows as the next unit's boundary", () => {
    expect(money(99999.6)).toBe("₹1.00 lakh crore");
    expect(money(99999.4)).toBe("₹99,999 crore");
    expect(money(99.96)).toBe("₹100 crore");
    expect(money(99.94)).toBe("₹99.9 crore");
    expect(money(9.996)).toBe("₹10.0 crore");
  });
  it("puts a true minus sign before the rupee sign", () => {
    expect(money(-42100)).toBe("−₹42,100 crore");
    expect(money(-250000)).toBe("−₹2.50 lakh crore");
    expect(money(-99999.6)).toBe("−₹1.00 lakh crore");
  });
  it("drops the sign of a value that rounds to zero", () => {
    expect(money(-0.001)).toBe("₹0.00 crore");
  });
});

describe("moneyShort", () => {
  it("matches its documented examples", () => {
    expect(moneyShort(5347315)).toBe("53L Cr");
    expect(moneyShort(534731)).toBe("5.3L Cr");
    expect(moneyShort(42100)).toBe("42K Cr");
    expect(moneyShort(850)).toBe("850 Cr");
  });
  it("picks the unit after rounding", () => {
    expect(moneyShort(99950)).toBe("1.0L Cr");
    expect(moneyShort(999.6)).toBe("1K Cr");
    expect(moneyShort(999999)).toBe("10L Cr");
  });
  it("handles negatives and zero", () => {
    expect(moneyShort(-42100)).toBe("−42K Cr");
    expect(moneyShort(0)).toBe("0 Cr");
    expect(moneyShort(-0.2)).toBe("0 Cr");
  });
});

describe("exact", () => {
  it("prints whole and fractional crore as given", () => {
    expect(exact(5347315)).toBe("₹53,47,315 crore");
    expect(exact(12.5)).toBe("₹12.50 crore");
    expect(exact(-1200)).toBe("−₹1,200 crore");
  });
});

describe("moneyParts", () => {
  it("splits number and unit", () => {
    expect(moneyParts(5347315)).toEqual({ num: "₹53.47", unit: "lakh crore" });
    expect(moneyParts(42100)).toEqual({ num: "₹42,100", unit: "crore" });
    expect(moneyParts(-42100)).toEqual({ num: "−₹42,100", unit: "crore" });
  });
});

describe("percentages", () => {
  it("pct", () => {
    expect(pct(12.345)).toBe("12.3%");
    expect(pct(12.345, 2)).toBe("12.35%");
    expect(pct(-1.25)).toBe("−1.3%");
    expect(pct(-0.04)).toBe("0.0%");
  });
  it("signedPct", () => {
    expect(signedPct(3.21)).toBe("+3.2%");
    expect(signedPct(-3.21)).toBe("−3.2%");
    expect(signedPct(0)).toBe("0.0%");
  });
  it("gpct", () => {
    expect(gpct(7.84)).toBe("7.8%");
    expect(gpct(-5.73)).toBe("−5.7%");
    expect(gpct(0.94, 2)).toBe("0.94%");
  });
  it("rounds before choosing the sign: no −0.0% or +0.0%", () => {
    for (const v of [-0.04, -0.0001, 0.04, 0.0001]) {
      expect(signedPct(v)).toBe("0.0%");
      expect(gpct(v)).toBe("0.0%");
    }
    expect(signedPct(-0.004, 2)).toBe("0.00%");
    expect(signedPct(-0.05)).toBe("−0.1%");
    expect(gpct(-0.05)).toBe("−0.1%");
  });
  it("pts", () => {
    expect(pts(1.84)).toBe("+1.8 pts");
    expect(pts(-0.44)).toBe("−0.4 pts");
    expect(pts(0)).toBe("±0.0 pts");
    expect(pts(-0.04)).toBe("±0.0 pts");
  });
  it("axisPct", () => {
    expect(axisPct(8)).toBe("8%");
    expect(axisPct(-4)).toBe("−4%");
    expect(axisPct(0)).toBe("0%");
  });
});

describe("plain numbers and rupees", () => {
  it("decimal", () => {
    expect(decimal(1438.06)).toBe("1,438.1");
    expect(decimal(1438069.4, 0)).toBe("14,38,069");
    expect(decimal(-2.25, 2)).toBe("−2.25");
    expect(decimal(-0.01)).toBe("0.0");
  });
  it("rupees", () => {
    expect(rupees(243107)).toBe("₹2,43,107");
    expect(rupees(-243107)).toBe("−₹2,43,107");
    expect(rupees(999.6)).toBe("₹1,000");
    expect(rupees(-0.4)).toBe("₹0");
  });
  it("rupeesAxis", () => {
    expect(rupeesAxis(50000)).toBe("₹50,000");
    expect(rupeesAxis(150000)).toBe("₹1.5 lakh");
    expect(rupeesAxis(-150000)).toBe("−₹1.5 lakh");
    expect(rupeesAxis(99999.6)).toBe("₹1 lakh");
  });
  it("orDash", () => {
    expect(orDash(null, gpct)).toBe("–");
    expect(orDash(undefined, gpct)).toBe("–");
    expect(orDash(0, gpct)).toBe("0.0%");
  });
});

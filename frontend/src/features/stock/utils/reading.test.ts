import { describe, expect, it } from "vitest";
import analysis from "@/shared/api/__fixtures__/analysis.json";
import { analysisSchema } from "../schemas/analysis";
import { actionSentence, dividendYield, edgeReading, fairValueReading, withoutRepeatedWatch } from "./reading";

const a = analysisSchema.parse((analysis as { data: unknown }).data);

describe("edgeReading", () => {
  it("says there is no edge when setups did no better than an ordinary day", () => {
    const r = edgeReading(0.62, 0.62, 205, true);
    expect(r.tone).toBe("mute");
    expect(r.text).toMatch(/^No edge: .*62%.*same as an ordinary day/);
  });
  it("says so when the edge is real, or negative", () => {
    expect(edgeReading(0.7, 0.6, 200, true)).toMatchObject({ tone: "up" });
    expect(edgeReading(0.5, 0.6, 200, true)).toMatchObject({ tone: "dn" });
  });
  it("warns about a small sample and handles missing numbers", () => {
    expect(edgeReading(0.7, 0.6, 8, false).text).toContain("only 8 past cases");
    expect(edgeReading(null, 0.6, 0, false).text).toMatch(/Not enough past cases/);
  });
});

describe("actionSentence", () => {
  it("says what SELL means for someone who cannot sell short", () => {
    expect(actionSentence("SELL")).toMatch(/avoid buying now.*already hold it/);
    expect(actionSentence("SOMETHING NEW")).toBe("SOMETHING NEW");
  });
});

describe("dividendYield", () => {
  it("is the last dividend over the price shown, with its basis", () => {
    const y = dividendYield({ ...a, price: { ...a.price, ltp: 215 }, fundamentals: { ...a.fundamentals, dividend_per_share: 21.5, dividend_yield_pct: 8.34 } });
    expect(y.value).toBeCloseTo(10, 6); // 21.5 / 215, not the exchange's 8.34
    expect(y.basis).toBe("last dividend Tk 21.50 ÷ price 215.00");
  });
  it("falls back to the exchange figure when no dividend per share is known", () => {
    const y = dividendYield({ ...a, fundamentals: { ...a.fundamentals, dividend_per_share: null, dividend_yield_pct: 4.2 } });
    expect(y).toEqual({ value: 4.2, basis: "exchange figure" });
  });
});

describe("fairValueReading", () => {
  const rows = [100, 120, 140, 160, 400].map((v, i) => ({ method: `m${i}`, inputs: "", fair_value: v, gap_pct: null }));
  it("gives the median, the middle half and the full range, and flags wide disagreement", () => {
    const r = fairValueReading({ ...a, price: { ...a.price, ltp: 100 }, valuation: { ...a.valuation, rows, median_fair_value: 140 } });
    expect(r).toMatchObject({ median: 140, q1: 120, q3: 160, low: 100, high: 400 });
    expect(r?.gapPct).toBeCloseTo(40);
    expect(r?.text).toContain("between 100.00 and 400.00");
  });
  it("needs at least three methods", () => {
    expect(fairValueReading({ ...a, valuation: { ...a.valuation, rows: rows.slice(0, 2) } })).toBeNull();
  });
});

describe("withoutRepeatedWatch", () => {
  it("drops a watch level that repeats a target or the buy zone, and keeps a new one", () => {
    const l = [
      { kind: "entry", price: 224.2, price_to: 221.9 },
      { kind: "target", price: 228.8 },
      { kind: "watch", price: 228.8 },
      { kind: "watch", price: 221.9 },
      { kind: "watch", price: 240 },
    ];
    expect(withoutRepeatedWatch(l).map((x) => `${x.kind}:${x.price}`)).toEqual(["entry:224.2", "target:228.8", "watch:240"]);
  });
});

import { describe, expect, it } from "vitest";
import analysisFixture from "@/shared/api/__fixtures__/analysis.json";
import { analysisSchema, type Analysis } from "../schemas/analysis";
import { distance, indicatorRows, rsiWord, technicalReading } from "./technicals";

const base = analysisSchema.parse((analysisFixture as { data: unknown }).data);
const make = (indicators: Record<string, number | null>, over: Partial<Analysis> = {}): Analysis => ({
  ...base,
  price: { ...base.price, ltp: 100 },
  indicators: { ...base.indicators, ...indicators },
  trend: { ...base.trend, vs_ma: { SMA50: { value: 110, pct: -9 }, SMA200: { value: 120, pct: -16 } } },
  levels: { ...base.levels, price: 100, above: [105, 120], below: [95, 80] },
  ...over,
});

describe("rsiWord", () => {
  it("names the zones", () => {
    expect([20, 40, 50, 60, 80].map((v) => rsiWord(v).word)).toEqual(["oversold", "weak", "neutral", "healthy", "overbought"]);
  });
});

describe("technicalReading", () => {
  it("says downtrend, weak momentum and light volume in a short headline", () => {
    const r = technicalReading(make({ rsi14: 34, macd_hist: -0.4, vol_ratio: 0.5, atr14: 2 }));
    expect(r?.headline).toBe("Trend down, momentum weak, volume light.");
    const text = r?.lines.map((l) => l.text).join(" ") ?? "";
    expect(text).toContain("Downtrend: price is below its 50-day (−9.0%) and 200-day (−16.0%) averages.");
    expect(text).toContain("RSI 34 is weak. MACD is below its signal line");
    expect(text).toContain("Light volume: 0.50× its 20-day average");
    expect(text).toContain("A typical day moves the price about 2.0% (ATR 2.00).");
  });
  it("says uptrend with healthy momentum and heavy volume", () => {
    const a = make({ rsi14: 62, macd_hist: 0.3, vol_ratio: 2 }, { trend: { ...base.trend, vs_ma: { SMA50: { value: 90, pct: 11 }, SMA200: { value: 80, pct: 25 } } } });
    expect(technicalReading(a)?.headline).toBe("Trend up, momentum healthy, volume heavy.");
  });
  it("calls it a mixed trend when price is above one long average and below the other", () => {
    const a = make({}, { trend: { ...base.trend, vs_ma: { SMA50: { value: 90, pct: 5 }, SMA200: { value: 120, pct: -10 } } } });
    expect(technicalReading(a)?.lines[0]?.text).toBe("Mixed trend: above its 50-day average but below its 200-day average.");
  });
  it("names the nearest support and resistance with their distance", () => {
    const l = technicalReading(make({ rsi14: 50 }))?.lines.find((x) => x.topic === "Levels");
    expect(l?.text).toBe("Nearest support 95.00 (5.0% below) and resistance 105.00 (5.0% above).");
  });
});

describe("distance", () => {
  it("is the gap as a share of the price", () => {
    expect(distance(200, 190)).toBe("5.0% below");
    expect(distance(200, 202)).toBe("1.0% above");
  });
});

describe("indicatorRows", () => {
  it("puts a meaning next to each number", () => {
    const rows = indicatorRows(make({ rsi14: 34, macd: -3, macd_signal: -3.4, macd_hist: 0.4, ema9: 99, ema21: 101, sma20: 102, sma50: 110, sma200: 120, bb_lower: 95, bb_upper: 120, atr14: 2, vol_ratio: 0.65 }));
    const by = Object.fromEntries(rows.map((r) => [r.label, r.reading]));
    expect(by["RSI (14)"]).toMatch(/^Weak: sellers have the upper hand/);
    expect(by["MACD / signal / histogram"]).toBe("Above its signal line: momentum improving");
    expect(by["EMA 9 / 21"]).toMatch(/short-term down/);
    expect(by["SMA 20 / 50 / 200"]).toBe("Price is above 0 of the 3 averages");
    expect(by["Bollinger bands (20, 2)"]).toBe("Inside the bands, 20% of the way up");
    expect(by["Volume vs 20-day average"]).toBe("Light");
  });
  it("skips indicators it has no number for", () => {
    expect(indicatorRows({ ...base, indicators: {} })).toEqual([]);
  });
});

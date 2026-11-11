import { describe, expect, it } from "vitest";
import type { Quote } from "@/shared/api";
import type { TechnicalBar } from "../schemas/analysis";
import { applyQuote, levelLines, minuteToTimestamp, patternMarkers, toCandles, toLine, toVolume } from "./chart-model";

const bar = (date: string, o: Partial<TechnicalBar> = {}): TechnicalBar => ({
  date, open: 10, high: 12, low: 9, close: 11, volume: 100,
  sma20: 10.5, sma50: null, sma200: null, ema9: null, ema21: null, bb_upper: null, bb_lower: null, vol_avg20: null, ...o,
});
const quote = (o: Partial<Quote> = {}): Quote => ({
  symbol: "GP", ltp: 13, ycp: 11, open: 11.5, high: 13.5, low: 11.2, close: null, change: 2, percent: 18, volume: 5000,
  value_mn: 1, trades: 1, category: "A", board: null, sector: null, asset_type: "EQ", trade_time: null, ...o,
});

describe("series builders", () => {
  it("skip bars with missing prices or values", () => {
    const bars = [bar("2026-01-01"), bar("2026-01-02", { close: null }), bar("2026-01-03", { sma20: null })];
    expect(toCandles(bars).map((c) => c.time)).toEqual(["2026-01-01", "2026-01-03"]);
    expect(toLine(bars, "sma20").map((p) => p.time)).toEqual(["2026-01-01", "2026-01-02"]);
  });

  it("colours volume by direction", () => {
    const v = toVolume([bar("a", { close: 12 }), bar("b", { close: 8 })], "UP", "DN");
    expect(v.map((x) => x.color)).toEqual(["UP", "DN"]);
  });
});

describe("patternMarkers", () => {
  const colors = { up: "u", down: "d", neutral: "n" };
  const p = (date: string, direction: "bullish" | "bearish" | "neutral", pattern = "X") => ({ date, bars_ago: 0, pattern, direction, high: 1, low: 1 });

  it("places and shapes markers by direction, in ascending time", () => {
    const m = patternMarkers([p("2026-01-03", "bearish"), p("2026-01-01", "bullish"), p("2026-01-02", "neutral")], colors, new Set(["2026-01-01", "2026-01-02", "2026-01-03"]));
    expect(m.map((x) => [x.time, x.position, x.shape])).toEqual([
      ["2026-01-01", "belowBar", "arrowUp"],
      ["2026-01-02", "aboveBar", "circle"],
      ["2026-01-03", "aboveBar", "arrowDown"],
    ]);
  });

  it("drops markers for dates the chart does not have (the library would throw)", () => {
    expect(patternMarkers([p("2030-01-01", "bullish")], colors, new Set(["2026-01-01"]))).toEqual([]);
  });
});

describe("levelLines", () => {
  it("labels resistance and support", () => {
    const l = levelLines({ price: 10, high_52w: 20, low_52w: 5, above: [12, 15], below: [8] });
    expect(l.map((x) => `${x.kind}:${x.title}`)).toEqual(["resistance:R 12", "resistance:R 15", "support:S 8"]);
  });
});

describe("applyQuote", () => {
  const bars = [bar("2026-01-01"), bar("2026-01-02")];

  it("refreshes today's bar in place, keeping its moving averages", () => {
    const out = applyQuote(bars, quote(), "2026-01-02");
    expect(out).toHaveLength(2);
    expect(out[1]).toMatchObject({ date: "2026-01-02", open: 11.5, high: 13.5, low: 11.2, close: 13, volume: 5000, sma20: 10.5 });
  });

  it("appends a new session's bar with unknown averages", () => {
    const out = applyQuote(bars, quote(), "2026-01-03");
    expect(out).toHaveLength(3);
    expect(out[2]).toMatchObject({ date: "2026-01-03", close: 13, sma20: null });
  });

  it("uses the official close once the session has ended", () => {
    expect(applyQuote(bars, quote({ close: 12.4 }), "2026-01-02")[1]?.close).toBe(12.4);
  });

  it("leaves history alone for old sessions, untraded or missing quotes", () => {
    expect(applyQuote(bars, quote(), "2025-12-31")).toEqual(bars);
    expect(applyQuote(bars, quote({ volume: 0 }), "2026-01-03")).toEqual(bars);
    expect(applyQuote(bars, quote({ ltp: null }), "2026-01-03")).toEqual(bars);
    expect(applyQuote(bars, undefined, "2026-01-03")).toEqual(bars);
    expect(applyQuote(bars, quote(), null)).toEqual(bars);
  });

  it("does not mutate its input", () => {
    const before = structuredClone(bars);
    applyQuote(bars, quote(), "2026-01-02");
    expect(bars).toEqual(before);
  });

  it("works from an empty history", () => {
    expect(applyQuote([], quote(), "2026-01-03")).toHaveLength(1);
  });
});

describe("minuteToTimestamp", () => {
  it("builds UTC seconds so the axis shows exchange time unchanged", () => {
    expect(minuteToTimestamp("2026-11-11", "10:05")).toBe(Date.UTC(2026, 10, 11, 10, 5) / 1000);
    expect(new Date(minuteToTimestamp("2026-11-11", "14:30") * 1000).toISOString()).toBe("2026-11-11T14:30:00.000Z");
  });
});

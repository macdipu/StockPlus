import { describe, expect, it } from "vitest";
import type { ChartData } from "../schemas/chart";
import { buildCandles, buildLayers, paletteColor, toChartTime, withLive, type Candle } from "./model";

const data = (over: Partial<ChartData> = {}): ChartData => ({
  symbol: "GP",
  resolution: "D",
  source: "dse-daily",
  candles: { time: [1_700_000_000, 1_700_086_400, 1_700_172_800], open: [10, 11, 12], high: [12, 13, 14], low: [9, 10, 11], close: [11, 12, 13], volume: [100, 200, 300] },
  indicators: [
    { key: "sma(2)", id: "sma", name: "SMA", group: "Moving averages", placement: "overlay", params: { length: 2 }, outputs: [{ key: "sma", label: "SMA", kind: "line" }], scale: null, levels: [], repaints: false, series: { sma: [null, 11.5, 12.5] } },
    { key: "macd", id: "macd", name: "MACD", group: "Momentum", placement: "pane", params: {}, outputs: [{ key: "macd", label: "MACD", kind: "line" }, { key: "hist", label: "Histogram", kind: "histogram" }], scale: null, levels: [], repaints: false, series: { macd: [null, null, 0.4], hist: [null, null, -0.2] } },
  ],
  warnings: [],
  catalog_version: "v1",
  ...over,
});

describe("toChartTime", () => {
  it("puts daily candles on their date and shifts intraday ones to Dhaka time", () => {
    expect(toChartTime(1_700_000_000, "D")).toBe("2023-11-14");
    expect(toChartTime(1_700_000_000, "5")).toBe(1_700_000_000 + 6 * 3600);
  });
});

describe("buildLayers and buildCandles", () => {
  it("splits overlays from panes, skips warm-up nulls and colours histogram columns by sign", () => {
    const m = buildLayers({ data: data(), resolution: "D", specs: ["sma(2)", "macd"] });
    expect(buildCandles(data(), "D")).toHaveLength(3);
    expect(m.overlays.map((s) => [s.key, s.points.length])).toEqual([["sma(2).sma", 2]]);
    expect(m.panes).toHaveLength(1);
    const hist = m.panes[0]!.series.find((s) => s.kind === "histogram")!;
    expect(hist.points).toHaveLength(1);
    expect(hist.points[0]!.color).toMatch(/^#f0646c/); // negative column is red
    expect(m.panes[0]!.series[0]!.title).toBe("MACD MACD");
  });

  it("an indicator keeps its colour from its position in the request", () => {
    const m = buildLayers({ data: data(), resolution: "D", specs: ["x", "sma(2)"] });
    expect(m.overlays[0]!.color).toBe(paletteColor(1, 0));
  });

  it("merges the live candle into daily candles only", () => {
    const live = { day: "2023-11-17", open: 1, high: 2, low: 1, close: 2, volume: 9 };
    expect(buildCandles(data(), "D", live)).toHaveLength(4); // newer day: appended
    expect(buildCandles(data(), "5", live)).toHaveLength(3); // intraday ignores it
  });

  it("passes host annotations through", () => {
    const m = buildLayers({ data: data(), resolution: "D", specs: [], annotations: { priceLines: [{ price: 1, color: "c", title: "t", style: "solid" }] } });
    expect(m.priceLines).toHaveLength(1);
  });
});

describe("withLive", () => {
  const base: Candle[] = [{ time: "2026-11-17" as never, open: 1, high: 2, low: 1, close: 2, volume: 5 }];
  const live = (day: string, volume = 10) => ({ day, open: 2, high: 3, low: 2, close: 3, volume });
  it("replaces the same day, appends a newer day, ignores an older or empty one", () => {
    expect(withLive(base, live("2026-11-17"))).toHaveLength(1);
    expect(withLive(base, live("2026-11-17"))[0]!.close).toBe(3);
    expect(withLive(base, live("2026-11-18"))).toHaveLength(2);
    expect(withLive(base, live("2026-11-16"))).toBe(base);
    expect(withLive(base, live("2026-11-18", 0))).toBe(base);
    expect(withLive(base, null)).toBe(base);
  });
});

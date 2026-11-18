import { describe, expect, it } from "vitest";
import { STYLES, STYLE_GROUPS, baselineValue, isChartStyle, needsOhlc, toHeikinAshi } from "./styles";

const c = (open: number, high: number, low: number, close: number) => ({ time: "t", volume: 7, open, high, low, close });

describe("chart styles", () => {
  it("offers thirteen distinct styles in four groups", () => {
    expect(STYLES).toHaveLength(13);
    expect(new Set(STYLES.map((s) => s.key)).size).toBe(13);
    expect(STYLE_GROUPS).toHaveLength(4);
    expect(STYLES.every((s) => s.label && s.hint)).toBe(true);
    expect(isChartStyle("heikin")).toBe(true);
    expect(isChartStyle("renko")).toBe(false);
  });
});

describe("needsOhlc", () => {
  it("lets a closes-only series use line, area and baseline styles but not candles", () => {
    expect(STYLES.filter((x) => !needsOhlc(x.key)).map((x) => x.key)).toEqual(["line", "line_markers", "step", "area", "baseline"]);
    expect(needsOhlc("candles")).toBe(true);
  });
});

describe("toHeikinAshi", () => {
  it("averages each bar with the previous one and keeps the other fields", () => {
    const [a, b] = toHeikinAshi([c(10, 12, 9, 11), c(11, 13, 10, 12)]);
    expect(a).toMatchObject({ open: 10.5, close: 10.5, high: 12, low: 9, volume: 7, time: "t" });
    expect(b?.close).toBe((11 + 13 + 10 + 12) / 4);
    expect(b?.open).toBe((10.5 + 10.5) / 2);
    expect(b!.high).toBeGreaterThanOrEqual(Math.max(b!.open, b!.close));
    expect(b!.low).toBeLessThanOrEqual(Math.min(b!.open, b!.close));
  });

  it("handles an empty series and leaves its input alone", () => {
    expect(toHeikinAshi([])).toEqual([]);
    const input = [c(10, 12, 9, 11)];
    toHeikinAshi(input);
    expect(input[0]).toEqual(c(10, 12, 9, 11));
  });
});

describe("baselineValue", () => {
  it("is the average of the most recent closes", () => {
    expect(baselineValue([1, 2, 3, 4], 2)).toBe(3.5);
    expect(baselineValue([])).toBe(0);
  });
});

import { describe, expect, it } from "vitest";
import { levelLines, minuteToTimestamp, patternMarkers } from "./chart-model";

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

describe("minuteToTimestamp", () => {
  it("builds UTC seconds so the axis shows exchange time unchanged", () => {
    expect(minuteToTimestamp("2026-01-05", "10:05")).toBe(Date.UTC(2026, 0, 5, 10, 5) / 1000);
  });
});

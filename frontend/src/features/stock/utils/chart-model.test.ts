import { describe, expect, it } from "vitest";
import type { ChartPattern } from "../schemas/chart-patterns";
import { dedupeLines, levelLines, minuteToTimestamp, nearestLevels, patternMarkers, patternShapes, recentPatterns } from "./chart-model";

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

describe("nearestLevels", () => {
  it("keeps only the closest two on each side", () => {
    const l = nearestLevels({ price: 100, high_52w: 200, low_52w: 10, above: [150, 104, 110, 120], below: [95, 40, 90, 99] }, 100);
    expect(l.map((x) => x.price)).toEqual([104, 110, 99, 95]);
    expect(l.map((x) => x.kind)).toEqual(["resistance", "resistance", "support", "support"]);
  });
});

describe("dedupeLines", () => {
  it("keeps the first of two lines at nearly the same price", () => {
    const r = dedupeLines([{ price: 87.2, t: "target" }, { price: 87.25, t: "watch" }, { price: 90, t: "level" }]);
    expect(r.map((x) => x.t)).toEqual(["target", "level"]);
  });
});

describe("recentPatterns", () => {
  const p = (date: string) => ({ date, bars_ago: 0, pattern: "X", direction: "neutral" as const, high: 1, low: 1 });
  it("returns the newest known-date patterns first, capped", () => {
    const r = recentPatterns([p("2026-01-01"), p("2026-01-03"), p("2026-01-02"), p("2030-01-01")], new Set(["2026-01-01", "2026-01-02", "2026-01-03"]), 2);
    expect(r.map((x) => x.date)).toEqual(["2026-01-03", "2026-01-02"]);
  });
});

describe("minuteToTimestamp", () => {
  it("builds UTC seconds so the axis shows exchange time unchanged", () => {
    expect(minuteToTimestamp("2026-01-05", "10:05")).toBe(Date.UTC(2026, 0, 5, 10, 5) / 1000);
  });
});

describe("patternShapes", () => {
  const pt = (day: string, price: number) => ({ day, price, label: "" });
  const pattern: ChartPattern = {
    kind: "double_top", name: "Double top", direction: "bearish", status: "forming", confidence: 70, start: "2026-01-01", end: "2026-01-20",
    points: [pt("2026-01-20", 99), pt("2026-01-01", 100), pt("2026-01-10", 88)],
    lines: [{ role: "neckline", a: pt("2026-01-10", 88), b: pt("2026-01-25", 88) }],
    summary: "",
  };
  const colors = { up: "u", down: "d", neutral: "n" };

  it("joins the swing points in time order and adds the rule line with the name tag", () => {
    const shapes = patternShapes([pattern], colors);
    const zig = shapes.filter((s) => s.id.includes(":z"));
    expect(zig.map((s) => [s.a.time, s.b?.time])).toEqual([["2026-01-01", "2026-01-10"], ["2026-01-10", "2026-01-20"]]);
    const [line] = shapes.filter((s) => s.id.includes(":l"));
    expect(line).toMatchObject({ color: "d", width: 2, dashed: true, label: "Double top (forming)" });
    expect(line?.dots).toHaveLength(3);
  });

  it("draws a confirmed pattern's line solid and colours by direction", () => {
    const [line] = patternShapes([{ ...pattern, direction: "bullish", status: "confirmed" }], colors).filter((s) => s.id.includes(":l"));
    expect(line).toMatchObject({ color: "u", dashed: false });
  });
});

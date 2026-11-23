import { describe, expect, it } from "vitest";
import { indexCloses, relativeStrength, sparkPoints, type DayClose } from "./strength";

const series = (start: string, closes: number[]): DayClose[] =>
  closes.map((close, i) => ({ day: new Date(Date.parse(`${start}T00:00:00Z`) + i * 86_400_000).toISOString().slice(0, 10), close }));

describe("relativeStrength", () => {
  const stock = series("2026-01-01", [100, 102, 104, 106, 110]); // +10% over 4 sessions
  it("is the share's return minus the index's over the same dates", () => {
    const r = relativeStrength(stock, series("2026-01-01", [1000, 1010, 1020, 1030, 1040]), 4);
    expect(r?.stockPct).toBeCloseTo(10);
    expect(r?.indexPct).toBeCloseTo(4);
    expect(r?.diffPts).toBeCloseTo(6);
    expect([r?.from, r?.to]).toEqual(["2026-01-01", "2026-01-05"]);
  });
  it("shows a falling share against a falling market as mostly the market's doing", () => {
    const r = relativeStrength(series("2026-01-01", [100, 97, 95]), series("2026-01-01", [1000, 970, 950]), 2);
    expect(r?.diffPts).toBeCloseTo(0);
  });
  it("reads the index on or before each date when it skips a day", () => {
    const idx = [{ day: "2026-01-01", close: 1000 }, { day: "2026-01-04", close: 1100 }];
    expect(relativeStrength(stock, idx, 4)?.indexPct).toBeCloseTo(10);
  });
  it("is null without enough history or an index that starts too late", () => {
    expect(relativeStrength(stock, series("2026-01-01", [1, 2, 3]), 10)).toBeNull();
    expect(relativeStrength(stock, series("2026-02-01", [1, 2, 3]), 4)).toBeNull();
  });
});

describe("indexCloses", () => {
  it("turns unix seconds into dates", () => {
    expect(indexCloses([1_763_856_000], [5500])).toEqual([{ day: "2025-11-23", close: 5500 }]);
  });
});

describe("sparkPoints", () => {
  it("draws higher values higher on the chart and spans the width", () => {
    const pts = sparkPoints([1, 3, 2], 100, 20, 0).split(" ").map((p) => p.split(",").map(Number) as [number, number]);
    expect(pts[0]).toEqual([0, 20]);
    expect(pts[1]).toEqual([50, 0]);
    expect(pts[2]?.[0]).toBe(100);
  });
  it("draws nothing for fewer than two values", () => {
    expect(sparkPoints([5], 100, 20)).toBe("");
  });
});

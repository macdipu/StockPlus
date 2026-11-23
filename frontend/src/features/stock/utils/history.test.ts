import { describe, expect, it } from "vitest";
import type { DailyBar } from "../schemas/candles";
import { monthlySeasonality, priceTable, weekdaySeasonality, withToday } from "./history";

const bar = (day: string, close: number, volume = 100): DailyBar => ({ day, open: close, high: close, low: close, close, volume, trades: 1 });

describe("priceTable", () => {
  const bars = [bar("2026-11-16", 10), bar("2026-11-17", 12, 300), bar("2026-11-18", 9, 200)];
  it("lists newest first with change on the previous close", () => {
    const t = priceTable(bars, 2)!;
    expect(t.rows.map((r) => r.day)).toEqual(["2026-11-18", "2026-11-17"]);
    expect(t.rows[0]!.change).toBe(-3);
    expect(t.rows[1]!.change).toBe(2); // the bar before the window still supplies the prior close
  });
  it("summarises the window", () => {
    const t = priceTable(bars, 3)!;
    expect([t.maxPrice, t.minPrice, t.maxVolume, t.minVolume]).toEqual([12, 9, 300, 100]);
    expect(t.change).toBe(-1);
    expect(t.changePct).toBeCloseTo(-10);
  });
  it("is null without data", () => expect(priceTable([], 90)).toBeNull());
});

describe("seasonality", () => {
  const bars = [bar("2025-12-30", 100), bar("2026-01-29", 110), bar("2026-02-26", 99), bar("2026-03-30", 100)];
  it("uses full months only (first partial and current month dropped)", () => {
    const m = monthlySeasonality(bars);
    expect(m[11]!.n).toBe(0); // Dec-2025 is only the base
    expect(m[0]!.avgPct).toBeCloseTo(10); // Jan: 110/100
    expect(m[0]!.n).toBe(1);
    expect(m[1]!.avgPct).toBeCloseTo(-10); // Feb: 99/110
    expect(m[1]!.winPct).toBe(0);
    expect(m[2]!.n).toBe(0); // March is the running month
  });
  it("groups by weekday, Monday first", () => {
    const w = weekdaySeasonality([bar("2026-11-22", 100), bar("2026-11-23", 110)]); // Sun, Mon
    expect(w).toHaveLength(1);
    expect(w[0]!.label).toBe("Mon");
    expect(w[0]!.avgPct).toBeCloseTo(10);
  });
});

describe("withToday", () => {
  const bars = [bar("2026-11-18", 9), bar("2026-11-22", 10)];
  const live = (day: string, close: number, volume = 5) => ({ day, open: close, high: close, low: close, close, volume });
  it("appends a newer live session with unknown trades", () => {
    const r = withToday(bars, live("2026-11-23", 11));
    expect(r).toHaveLength(3);
    expect(r[2]).toMatchObject({ day: "2026-11-23", close: 11, trades: null });
  });
  it("replaces the same day but keeps its saved trade count", () => {
    const r = withToday(bars, live("2026-11-22", 12));
    expect(r).toHaveLength(2);
    expect(r[1]).toMatchObject({ close: 12, trades: 1 });
  });
  it("ignores no live bar, no volume, or an older day", () => {
    expect(withToday(bars, null)).toBe(bars);
    expect(withToday(bars, live("2026-11-23", 11, 0))).toBe(bars);
    expect(withToday(bars, live("2026-11-01", 11))).toBe(bars);
  });
});

import type { Quote } from "@/shared/api";
import type { Analysis, TechnicalBar } from "../schemas/analysis";

/** Everything the price chart draws, derived from API data. Pure: no DOM, no chart library. */

export interface CandlePoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}
export interface ValuePoint {
  time: string;
  value: number;
}
export interface VolumePoint extends ValuePoint {
  color: string;
}
export interface PatternMarker {
  time: string;
  position: "aboveBar" | "belowBar";
  shape: "arrowUp" | "arrowDown" | "circle";
  color: string;
  text: string;
}

export const OVERLAYS = [
  { key: "sma20", label: "SMA 20", color: "#2563eb" },
  { key: "sma50", label: "SMA 50", color: "#f59e0b" },
  { key: "sma200", label: "SMA 200", color: "#8b5cf6" },
  { key: "ema9", label: "EMA 9", color: "#06b6d4" },
  { key: "ema21", label: "EMA 21", color: "#ec4899" },
] as const;
export type OverlayKey = (typeof OVERLAYS)[number]["key"];

export function toCandles(bars: readonly TechnicalBar[]): CandlePoint[] {
  const out: CandlePoint[] = [];
  for (const b of bars) {
    if (b.open != null && b.high != null && b.low != null && b.close != null) {
      out.push({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close });
    }
  }
  return out;
}

export function toVolume(bars: readonly TechnicalBar[], up: string, down: string): VolumePoint[] {
  const out: VolumePoint[] = [];
  for (const b of bars) {
    if (b.volume != null && b.open != null && b.close != null) {
      out.push({ time: b.date, value: b.volume, color: b.close >= b.open ? up : down });
    }
  }
  return out;
}

export function toLine(bars: readonly TechnicalBar[], key: OverlayKey): ValuePoint[] {
  const out: ValuePoint[] = [];
  for (const b of bars) {
    const v = b[key];
    if (v != null) out.push({ time: b.date, value: v });
  }
  return out;
}

export function patternMarkers(
  patterns: Analysis["candles"]["patterns"],
  colors: { up: string; down: string; neutral: string },
  knownDates: ReadonlySet<string>,
): PatternMarker[] {
  return patterns
    .filter((p) => knownDates.has(p.date)) // a marker on a date the chart does not have would throw
    .map((p): PatternMarker => {
      if (p.direction === "bullish") return { time: p.date, position: "belowBar", shape: "arrowUp", color: colors.up, text: p.pattern };
      if (p.direction === "bearish") return { time: p.date, position: "aboveBar", shape: "arrowDown", color: colors.down, text: p.pattern };
      return { time: p.date, position: "aboveBar", shape: "circle", color: colors.neutral, text: p.pattern };
    })
    .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0)); // the library requires ascending time
}

export interface LevelLine {
  price: number;
  title: string;
  kind: "resistance" | "support";
}

export function levelLines(levels: Analysis["levels"]): LevelLine[] {
  return [
    ...levels.above.map((price): LevelLine => ({ price, title: `R ${price}`, kind: "resistance" })),
    ...levels.below.map((price): LevelLine => ({ price, title: `S ${price}`, kind: "support" })),
  ];
}

/**
 * Today's bar from a live quote: refresh it if the last bar is today, append it if today is newer, and leave
 * history alone otherwise. Moving averages of a new bar are unknown until the next analysis refresh.
 */
export function applyQuote(bars: readonly TechnicalBar[], q: Quote | undefined, sessionDay: string | null): TechnicalBar[] {
  if (!q || !sessionDay || q.ltp == null || !(q.volume > 0)) return [...bars];
  const last = bars[bars.length - 1];
  const live = {
    open: q.open || q.ltp,
    high: q.high || q.ltp,
    low: q.low || q.ltp,
    close: q.close || q.ltp,
    volume: q.volume,
  };
  if (last && last.date === sessionDay) return [...bars.slice(0, -1), { ...last, ...live }];
  if (!last || sessionDay > last.date) {
    return [
      ...bars,
      { date: sessionDay, ...live, sma20: null, sma50: null, sma200: null, ema9: null, ema21: null, bb_upper: null, bb_lower: null, vol_avg20: null },
    ];
  }
  return [...bars];
}

/** Minute labels ("10:05") become UTC timestamps on `day`, so the axis shows exchange time unchanged. */
export function minuteToTimestamp(day: string, hhmm: string): number {
  const [y = 1970, mo = 1, d = 1] = day.split("-").map(Number);
  const [h = 0, mi = 0] = hhmm.split(":").map(Number);
  return Date.UTC(y, mo - 1, d, h, mi) / 1000;
}

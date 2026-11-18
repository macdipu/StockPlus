import type { Analysis } from "../schemas/analysis";

/** Chart annotations derived from an analysis. Pure: no DOM, no chart library. */

export interface PatternMarker {
  time: string;
  position: "aboveBar" | "belowBar";
  shape: "arrowUp" | "arrowDown" | "circle";
  color: string;
  text: string;
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

/** Minute labels ("10:05") become UTC timestamps on `day`, so the axis shows exchange time unchanged. */
export function minuteToTimestamp(day: string, hhmm: string): number {
  const [y = 1970, mo = 1, d = 1] = day.split("-").map(Number);
  const [h = 0, mi = 0] = hhmm.split(":").map(Number);
  return Date.UTC(y, mo - 1, d, h, mi) / 1000;
}

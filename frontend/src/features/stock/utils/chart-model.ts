import type { Drawing } from "@/features/chart";
import type { Analysis } from "../schemas/analysis";
import type { ChartPattern } from "../schemas/chart-patterns";

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

/** The `n` support and `n` resistance levels closest to the price: far-away levels only add clutter. */
export function nearestLevels(levels: Analysis["levels"], price: number, n = 2): LevelLine[] {
  const closest = (xs: readonly number[]) => [...xs].sort((a, b) => Math.abs(a - price) - Math.abs(b - price)).slice(0, n);
  return [
    // only the nearest on each side is tagged; the colour on the axis tells the rest apart
    ...closest(levels.above).map((p, i): LevelLine => ({ price: p, title: i === 0 ? "Resistance" : "", kind: "resistance" })),
    ...closest(levels.below).map((p, i): LevelLine => ({ price: p, title: i === 0 ? "Support" : "", kind: "support" })),
  ];
}

/** Drops a line that sits within `tolerance` (a fraction) of one already kept, so an earlier (more important) line
 * wins and two tags never stack on the same price. */
export function dedupeLines<T extends { price: number }>(lines: readonly T[], tolerance = 0.004): T[] {
  const kept: T[] = [];
  for (const l of lines) if (!kept.some((k) => Math.abs(k.price - l.price) <= Math.abs(k.price) * tolerance)) kept.push(l);
  return kept;
}

/** The newest `n` candle patterns that fall on a date the chart has. */
export function recentPatterns(patterns: Analysis["candles"]["patterns"], knownDates: ReadonlySet<string>, n = 5): Analysis["candles"]["patterns"] {
  return patterns
    .filter((p) => knownDates.has(p.date))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
    .slice(0, n);
}

/** Minute labels ("10:05") become UTC timestamps on `day`, so the axis shows exchange time unchanged. */
export function minuteToTimestamp(day: string, hhmm: string): number {
  const [y = 1970, mo = 1, d = 1] = day.split("-").map(Number);
  const [h = 0, mi = 0] = hhmm.split(":").map(Number);
  return Date.UTC(y, mo - 1, d, h, mi) / 1000;
}

/** Chart patterns as shapes for the chart: the swing points joined by a thin zig-zag, and each rule line (neckline,
 * upper/lower trendline) on top, dashed while the pattern is only forming. The first line carries the name tag. */
export function patternShapes(patterns: readonly ChartPattern[], colors: { up: string; down: string; neutral: string }): Drawing[] {
  const out: Drawing[] = [];
  patterns.forEach((p, n) => {
    const color = p.direction === "bullish" ? colors.up : p.direction === "bearish" ? colors.down : colors.neutral;
    const id = `auto:${p.kind}:${p.end}:${n}`;
    const pts = [...p.points].sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0));
    pts.slice(1).forEach((to, i) => {
      const from = pts[i];
      if (from) out.push({ id: `${id}:z${i}`, kind: "trend", a: { time: from.day, price: from.price }, b: { time: to.day, price: to.price }, color, width: 1, dashed: true });
    });
    p.lines.forEach((l, i) =>
      out.push({
        id: `${id}:l${i}`,
        kind: "trend",
        a: { time: l.a.day, price: l.a.price },
        b: { time: l.b.day, price: l.b.price },
        color,
        width: 2,
        dashed: p.status === "forming",
        ...(i === 0 ? { label: `${p.name} (${p.status})`, dots: pts.map((q) => ({ time: q.day, price: q.price })) } : {}),
      }),
    );
  });
  return out;
}


/** The user's own drawings on a chart. Pure data and geometry: no DOM, no chart library. */

export type DrawKind = "trend" | "ray" | "hline" | "rect" | "fib" | "measure";
export type Tool = "cursor" | DrawKind;

export const TOOLS: ReadonlyArray<{ key: Tool; label: string; hint: string }> = [
  { key: "cursor", label: "Select", hint: "Click a drawing to select it; Delete removes it" },
  { key: "trend", label: "Trend line", hint: "Click two points" },
  { key: "ray", label: "Ray", hint: "Click two points; the line continues to the right" },
  { key: "hline", label: "Horizontal line", hint: "Click once at a price" },
  { key: "rect", label: "Rectangle", hint: "Click two opposite corners" },
  { key: "fib", label: "Fibonacci", hint: "Click the start and end of a move" },
  { key: "measure", label: "Measure", hint: "Click two points to read the change and the number of bars" },
];

/** A point is a candle's time (a date string on daily charts, seconds on minute charts) and a price. */
export interface DrawPoint {
  time: string | number;
  price: number;
}

export interface Drawing {
  id: string;
  kind: DrawKind;
  a: DrawPoint;
  /** Absent for a horizontal line. */
  b?: DrawPoint;
}

export const needsTwoPoints = (k: DrawKind): boolean => k !== "hline";

const KINDS: readonly string[] = ["trend", "ray", "hline", "rect", "fib", "measure"];
const isPoint = (v: unknown): v is DrawPoint => {
  if (typeof v !== "object" || v === null) return false;
  const p = v as Record<string, unknown>;
  return (typeof p.time === "string" || typeof p.time === "number") && typeof p.price === "number" && Number.isFinite(p.price);
};

/** Stored drawings come from localStorage, so anything unexpected is dropped instead of trusted. */
export function parseDrawings(raw: unknown): Drawing[] {
  if (!Array.isArray(raw)) return [];
  const out: Drawing[] = [];
  for (const r of raw as unknown[]) {
    if (typeof r !== "object" || r === null) continue;
    const d = r as Record<string, unknown>;
    if (typeof d.id !== "string" || typeof d.kind !== "string" || !KINDS.includes(d.kind) || !isPoint(d.a)) continue;
    const kind = d.kind as DrawKind;
    if (needsTwoPoints(kind)) {
      if (!isPoint(d.b)) continue;
      out.push({ id: d.id, kind, a: d.a, b: d.b });
    } else out.push({ id: d.id, kind, a: d.a });
  }
  return out;
}

export const FIB_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] as const;

/** Retracement levels of the move from `a` to `b`: ratio 0 sits at the end of the move, 1 at its start. */
export function fibLevels(a: DrawPoint, b: DrawPoint): Array<{ ratio: number; price: number }> {
  return FIB_RATIOS.map((ratio) => ({ ratio, price: b.price - (b.price - a.price) * ratio }));
}

export function measureText(a: DrawPoint, b: DrawPoint, bars: number): string {
  const diff = b.price - a.price;
  const pct = a.price ? (diff / a.price) * 100 : 0;
  const sign = diff >= 0 ? "+" : "−";
  return `${sign}${Math.abs(diff).toFixed(2)} (${sign}${Math.abs(pct).toFixed(2)}%) · ${bars} bar${bars === 1 ? "" : "s"}`;
}

export interface XY {
  x: number;
  y: number;
}
export type Segment = readonly [XY, XY];

/** A drawing's lines in screen space, for painting and for hit-testing. `width` is the right edge of the pane. */
export function segments(d: Drawing, at: (p: DrawPoint) => XY | null, width: number): Segment[] {
  const a = at(d.a);
  if (!a) return [];
  if (d.kind === "hline") return [[{ x: 0, y: a.y }, { x: width, y: a.y }]];
  const b = d.b ? at(d.b) : null;
  if (!b) return [];
  if (d.kind === "ray") {
    if (b.x === a.x) return [[a, b]];
    const slope = (b.y - a.y) / (b.x - a.x);
    const end = Math.max(width, a.x, b.x);
    return [[a, { x: end, y: a.y + slope * (end - a.x) }]];
  }
  if (d.kind === "rect") {
    const tl = { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y) };
    const br = { x: Math.max(a.x, b.x), y: Math.max(a.y, b.y) };
    const tr = { x: br.x, y: tl.y };
    const bl = { x: tl.x, y: br.y };
    return [[tl, tr], [tr, br], [br, bl], [bl, tl]];
  }
  if (d.kind === "fib" && d.b) {
    const left = Math.min(a.x, b.x);
    const right = Math.max(width, a.x, b.x);
    return fibLevels(d.a, d.b).flatMap((l): Segment[] => {
      const p = at({ time: d.a.time, price: l.price });
      return p ? [[{ x: left, y: p.y }, { x: right, y: p.y }]] : [];
    });
  }
  return [[a, b]]; // trend, measure
}

export function distanceToSegment(p: XY, [a, b]: Segment): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

/** The topmost drawing within `tolerance` pixels of the click (later drawings sit on top). */
export function hitTest(drawings: readonly Drawing[], p: XY, at: (q: DrawPoint) => XY | null, width: number, tolerance = 7): string | null {
  for (let i = drawings.length - 1; i >= 0; i--) {
    const d = drawings[i] as Drawing;
    if (segments(d, at, width).some((s) => distanceToSegment(p, s) <= tolerance)) return d.id;
  }
  return null;
}

/** With the magnet on, a click snaps to the candle's open, high, low or close, whichever is closest. */
export function snapPrice(price: number, candle: { open: number; high: number; low: number; close: number } | undefined): number {
  if (!candle) return price;
  return [candle.open, candle.high, candle.low, candle.close].reduce((best, v) => (Math.abs(v - price) < Math.abs(best - price) ? v : best));
}

let counter = 0;
export const newId = (): string => `d${Date.now().toString(36)}${(counter++).toString(36)}`;

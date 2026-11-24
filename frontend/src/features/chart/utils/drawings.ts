/** The user's own drawings on a chart. Pure data and geometry: no DOM, no chart library. */

export type DrawKind = "trend" | "ray" | "hline" | "vline" | "channel" | "rect" | "fib" | "measure" | "long" | "short" | "text";
export type Tool = "cursor" | DrawKind;

export type ToolGroup = "pointer" | "lines" | "shapes" | "trade" | "note";

export const TOOLS: ReadonlyArray<{ key: Tool; label: string; hint: string; group: ToolGroup }> = [
  { key: "cursor", label: "Select", hint: "Click a drawing to select it; Delete removes it", group: "pointer" },
  { key: "trend", label: "Trend line", hint: "Click two points", group: "lines" },
  { key: "ray", label: "Ray", hint: "Click two points; the line continues to the right", group: "lines" },
  { key: "hline", label: "Horizontal line", hint: "Click once at a price", group: "lines" },
  { key: "vline", label: "Vertical line", hint: "Click once on a date to mark it", group: "lines" },
  { key: "channel", label: "Channel", hint: "Click two points for the line, then a third where the parallel line should run", group: "lines" },
  { key: "rect", label: "Rectangle", hint: "Click two opposite corners", group: "shapes" },
  { key: "fib", label: "Fibonacci", hint: "Click the start and end of a move", group: "shapes" },
  { key: "measure", label: "Measure", hint: "Click two points to read the change and the number of bars", group: "shapes" },
  { key: "long", label: "Long", hint: "Click the entry, then the stop, then the target: it shows the risk, reward and ratio", group: "trade" },
  { key: "short", label: "Short", hint: "Click the entry, then the stop, then the target: it shows the risk, reward and ratio", group: "trade" },
  { key: "text", label: "Note", hint: "Click where the note goes, then type it and press Enter", group: "note" },
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
  /** Absent for the one-point kinds (horizontal and vertical line, note). For a position it is the stop. */
  b?: DrawPoint;
  /** The third point: where a channel's parallel line runs, or a position's target. */
  c?: DrawPoint;
  /** The words of a note. */
  text?: string;
  /** Styling for shapes the app draws itself (chart patterns); the user's own drawings leave these out. */
  color?: string;
  dashed?: boolean;
  width?: number;
  /** A tag drawn at the first point. */
  label?: string;
  /** Small circles on key points (the swing highs and lows of a pattern). */
  dots?: readonly DrawPoint[];
}

/** Colours and line widths the user can give a drawing (stored with it, so they survive a reload). */
export const COLORS: ReadonlyArray<{ value: string; name: string }> = [
  { value: "#6d7cff", name: "Blue" },
  { value: "#e5a50a", name: "Amber" },
  { value: "#22b573", name: "Green" },
  { value: "#e5484d", name: "Red" },
  { value: "#c084fc", name: "Purple" },
  { value: "#94a3b8", name: "Grey" },
];
export const WIDTHS: readonly number[] = [1, 2, 3];

const ONE: readonly DrawKind[] = ["hline", "vline", "text"];
const THREE: readonly DrawKind[] = ["channel", "long", "short"];

/** How many clicks place this kind of drawing. */
export const pointsNeeded = (k: DrawKind): 1 | 2 | 3 => (ONE.includes(k) ? 1 : THREE.includes(k) ? 3 : 2);

const KINDS: readonly string[] = ["trend", "ray", "hline", "vline", "channel", "rect", "fib", "measure", "long", "short", "text"];
const MAX_TEXT = 120;
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
    const style = {
      ...(typeof d.color === "string" && /^#[0-9a-fA-F]{6}$/.test(d.color) ? { color: d.color } : {}),
      ...(typeof d.width === "number" && WIDTHS.includes(d.width) ? { width: d.width } : {}),
    };
    const need = pointsNeeded(kind);
    if (need >= 2 && !isPoint(d.b)) continue;
    if (need === 3 && !isPoint(d.c)) continue;
    if (kind === "text" && !(typeof d.text === "string" && d.text.trim().length > 0 && d.text.length <= MAX_TEXT)) continue;
    out.push({
      id: d.id,
      kind,
      a: d.a,
      ...(need >= 2 ? { b: d.b as DrawPoint } : {}),
      ...(need === 3 ? { c: d.c as DrawPoint } : {}),
      ...(kind === "text" ? { text: (d.text as string).trim() } : {}),
      ...style,
    });
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

/** The pane's size and how wide a position box is, in pixels, for kinds whose shape depends on them. */
export interface View {
  height?: number;
  box?: number;
}

const edges = (x1: number, y1: number, x2: number, y2: number): Segment[] => {
  const [l, r] = [Math.min(x1, x2), Math.max(x1, x2)];
  const [t, bt] = [Math.min(y1, y2), Math.max(y1, y2)];
  return [[{ x: l, y: t }, { x: r, y: t }], [{ x: r, y: t }, { x: r, y: bt }], [{ x: r, y: bt }, { x: l, y: bt }], [{ x: l, y: bt }, { x: l, y: t }]];
};

/** Roughly how wide a note is, so it can be hit-tested without measuring text. */
export const noteWidth = (text: string): number => Math.max(28, text.length * 6.6 + 12);
export const NOTE_HEIGHT = 18;

/** How far (in pixels, straight up or down) the channel's parallel line sits from the line through `a` and `b`, at `c`. */
export function channelOffset(a: XY, b: XY, c: XY): number {
  if (b.x === a.x) return 0;
  const onBase = a.y + ((b.y - a.y) / (b.x - a.x)) * (c.x - a.x);
  return c.y - onBase;
}

/** A drawing's lines in screen space, for painting and for hit-testing. `width` is the right edge of the pane. */
export function segments(d: Drawing, at: (p: DrawPoint) => XY | null, width: number, view: View = {}): Segment[] {
  const a = at(d.a);
  if (!a) return [];
  if (d.kind === "hline") return [[{ x: 0, y: a.y }, { x: width, y: a.y }]];
  if (d.kind === "vline") return [[{ x: a.x, y: 0 }, { x: a.x, y: view.height ?? 0 }]];
  if (d.kind === "text") return edges(a.x, a.y - NOTE_HEIGHT, a.x + noteWidth(d.text ?? ""), a.y);
  if (d.kind === "long" || d.kind === "short") {
    const w = view.box ?? 120;
    const stop = d.b ? at({ time: d.a.time, price: d.b.price }) : null;
    const target = d.c ? at({ time: d.a.time, price: d.c.price }) : null;
    return [
      [{ x: a.x, y: a.y }, { x: a.x + w, y: a.y }],
      ...(stop ? edges(a.x, a.y, a.x + w, stop.y) : []),
      ...(target ? edges(a.x, a.y, a.x + w, target.y) : []),
    ];
  }
  const b = d.b ? at(d.b) : null;
  if (!b) return [];
  if (d.kind === "channel") {
    const c = d.c ? at(d.c) : null;
    if (!c) return [[a, b]]; // still being drawn: just the base line
    const off = channelOffset(a, b, c);
    return [[a, b], [{ x: a.x, y: a.y + off }, { x: b.x, y: b.y + off }]];
  }
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
export function hitTest(drawings: readonly Drawing[], p: XY, at: (q: DrawPoint) => XY | null, width: number, tolerance = 7, view: View = {}): string | null {
  for (let i = drawings.length - 1; i >= 0; i--) {
    const d = drawings[i] as Drawing;
    if (d.kind === "text") {
      const o = at(d.a); // a note is hit anywhere on its text, not only along the edge of its box
      if (o && p.x >= o.x - tolerance && p.x <= o.x + noteWidth(d.text ?? "") + tolerance && p.y >= o.y - NOTE_HEIGHT - tolerance && p.y <= o.y + tolerance) return d.id;
      continue;
    }
    if (d.kind === "long" || d.kind === "short") {
      // a position is a box: clicking anywhere inside its green or red zone selects it
      const a = at(d.a);
      const ys = [a?.y, d.b ? at({ time: d.a.time, price: d.b.price })?.y : undefined, d.c ? at({ time: d.a.time, price: d.c.price })?.y : undefined].filter((v): v is number => v != null);
      if (a && ys.length && p.x >= a.x - tolerance && p.x <= a.x + (view.box ?? 120) + tolerance && p.y >= Math.min(...ys) - tolerance && p.y <= Math.max(...ys) + tolerance) return d.id;
    }
    if (segments(d, at, width, view).some((s) => distanceToSegment(p, s) <= tolerance)) return d.id;
  }
  return null;
}

/** With the magnet on, a click snaps to the candle's open, high, low or close, whichever is closest. */
export function snapPrice(price: number, candle: { open: number; high: number; low: number; close: number } | undefined): number {
  if (!candle) return price;
  return [candle.open, candle.high, candle.low, candle.close].reduce((best, v) => (Math.abs(v - price) < Math.abs(best - price) ? v : best));
}

export type DragMode = "a" | "b" | "c" | "move";

/**
 * The drawing after the pointer moved from `from` to `here` (both already on candles). Dragging a handle replaces that
 * point; dragging the body shifts every point by the same number of candles and the same price. `times` are the chart's
 * candle times in order, so a shift lands on real candles and stops at the ends. Some kinds are constrained: a horizontal
 * line only moves in price, a vertical line only in time, and a position's stop and target only in price (they sit under
 * the entry's date).
 */
export function dragDrawing(orig: Drawing, mode: DragMode, from: DrawPoint, here: DrawPoint, times: readonly (string | number)[]): Drawing {
  const index = (t: string | number) => times.findIndex((x) => String(x) === String(t));
  if (orig.kind === "hline") return { ...orig, a: { time: orig.a.time, price: orig.a.price + (here.price - from.price) } };
  if (orig.kind === "vline") return { ...orig, a: { time: here.time, price: orig.a.price } };
  const position = orig.kind === "long" || orig.kind === "short";
  if (position && (mode === "b" || mode === "c")) return { ...orig, [mode]: { time: orig.a.time, price: here.price } };
  if (mode === "a") {
    if (!position) return { ...orig, a: here };
    const under = (p: DrawPoint | undefined) => (p ? { time: here.time, price: p.price } : undefined);
    return { ...orig, a: here, ...(orig.b ? { b: under(orig.b) } : {}), ...(orig.c ? { c: under(orig.c) } : {}) };
  }
  if (mode === "b") return { ...orig, b: here };
  if (mode === "c") return { ...orig, c: here };
  const di = index(here.time) - index(from.time);
  const dp = here.price - from.price;
  const shift = (p: DrawPoint): DrawPoint => {
    const i = index(p.time);
    const t = i < 0 ? p.time : (times[Math.max(0, Math.min(times.length - 1, i + di))] ?? p.time);
    return { time: t, price: p.price + dp };
  };
  const a2 = shift(orig.a);
  const rest = position
    ? { ...(orig.b ? { b: { time: a2.time, price: orig.b.price + dp } } : {}), ...(orig.c ? { c: { time: a2.time, price: orig.c.price + dp } } : {}) }
    : { ...(orig.b ? { b: shift(orig.b) } : {}), ...(orig.c ? { c: shift(orig.c) } : {}) };
  return { ...orig, a: a2, ...rest };
}

export interface PositionStats {
  risk: number;
  reward: number;
  /** Reward divided by risk; null when the stop sits on the entry. */
  ratio: number | null;
  riskPct: number;
  rewardPct: number;
  /** The signed move from entry to target and to stop, as a percentage of the entry. */
  targetMovePct: number;
  stopMovePct: number;
}

/** What a position drawing says: how much is risked, how much could be made, and the ratio between them. */
export function positionStats(d: Drawing): PositionStats | null {
  if (!d.b || !d.c || !d.a.price) return null;
  const entry = d.a.price;
  const risk = Math.abs(entry - d.b.price);
  const reward = Math.abs(d.c.price - entry);
  return {
    risk,
    reward,
    ratio: risk > 0 ? reward / risk : null,
    riskPct: (risk / entry) * 100,
    rewardPct: (reward / entry) * 100,
    targetMovePct: ((d.c.price - entry) / entry) * 100,
    stopMovePct: ((d.b.price - entry) / entry) * 100,
  };
}

/** A date or time for a label: MM-DD on daily charts, HH:MM on minute charts. */
export function timeLabel(t: string | number): string {
  return typeof t === "number" ? new Date(t * 1000).toISOString().slice(11, 16) : t.slice(5); // minute charts: HH:MM; daily: MM-DD
}

/** A short line for the drawings list: "Trend line · 07-28 to 09-07 · 66.98 to 78.74". */
export function describeDrawing(d: Drawing): string {
  const name = TOOLS.find((t) => t.key === d.kind)?.label ?? d.kind;
  if (d.kind === "hline") return `${name} · ${d.a.price.toFixed(2)}`;
  if (d.kind === "vline") return `${name} · ${timeLabel(d.a.time)}`;
  if (d.kind === "text") return `${name} · ${d.text ?? ""}`;
  if (d.kind === "long" || d.kind === "short") {
    const p = positionStats(d);
    return `${name} position · entry ${d.a.price.toFixed(2)}${d.b ? ` · stop ${d.b.price.toFixed(2)}` : ""}${d.c ? ` · target ${d.c.price.toFixed(2)}` : ""}${p?.ratio != null ? ` · ${p.ratio.toFixed(1)}:1` : ""}`;
  }
  if (!d.b) return `${name} · ${d.a.price.toFixed(2)}`;
  if (d.kind === "channel") return `${name} · ${timeLabel(d.a.time)} to ${timeLabel(d.b.time)}`;
  return `${name} · ${timeLabel(d.a.time)} to ${timeLabel(d.b.time)} · ${d.a.price.toFixed(2)} to ${d.b.price.toFixed(2)}`;
}

let counter = 0;
export const newId = (): string => `d${Date.now().toString(36)}${(counter++).toString(36)}`;

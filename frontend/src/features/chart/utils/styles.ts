/** The chart styles, grouped as in the picker. Every style draws from the same candles. */
export type ChartStyle =
  | "bars"
  | "candles"
  | "hollow"
  | "hlc_bars"
  | "line"
  | "line_markers"
  | "step"
  | "area"
  | "hlc_area"
  | "baseline"
  | "columns"
  | "high_low"
  | "heikin";

export interface StyleOption {
  key: ChartStyle;
  label: string;
  hint: string;
}

/** Styles that need open, high and low. A series with closing values only (an index) can use the others. */
const NEEDS_OHLC: ReadonlySet<ChartStyle> = new Set(["bars", "candles", "hollow", "hlc_bars", "hlc_area", "columns", "high_low", "heikin"]);
export const needsOhlc = (s: ChartStyle) => NEEDS_OHLC.has(s);

export const STYLE_GROUPS: ReadonlyArray<ReadonlyArray<StyleOption>> = [
  [
    { key: "bars", label: "Bars", hint: "Open, high, low and close as a vertical bar with ticks" },
    { key: "candles", label: "Candles", hint: "Filled candles: green when the price closed higher, red when lower" },
    { key: "hollow", label: "Hollow candles", hint: "Rising candles are outlined, falling candles are filled" },
    { key: "hlc_bars", label: "HLC bars", hint: "Bars without the open tick: high, low and close only" },
  ],
  [
    { key: "line", label: "Line", hint: "A line through each close" },
    { key: "line_markers", label: "Line with markers", hint: "A line through each close, with a dot on every close" },
    { key: "step", label: "Step line", hint: "A line that holds each close until the next one" },
  ],
  [
    { key: "area", label: "Area", hint: "A line through each close with the area below filled" },
    { key: "hlc_area", label: "HLC area", hint: "Area of the close, with the high and low drawn as lines" },
    { key: "baseline", label: "Baseline", hint: "Closes above the recent average are green, below are red" },
  ],
  [
    { key: "columns", label: "Columns", hint: "A column for each close" },
    { key: "high_low", label: "High-low", hint: "A floating bar from each low to each high" },
    { key: "heikin", label: "Heikin Ashi", hint: "Averaged candles that smooth noise so trends read as runs of one colour" },
  ],
];

export const STYLES: readonly StyleOption[] = STYLE_GROUPS.flat();
export const isChartStyle = (v: unknown): v is ChartStyle => STYLES.some((s) => s.key === v);
export const styleLabel = (k: ChartStyle) => STYLES.find((s) => s.key === k)?.label ?? k;

/**
 * Heikin Ashi candles: each bar is averaged with the one before it. Other fields on the bar (time, volume) are
 * kept as they are, and the input is not changed.
 */
export function toHeikinAshi<T extends { open: number; high: number; low: number; close: number }>(bars: readonly T[]): T[] {
  const out: T[] = [];
  let prevOpen = 0;
  let prevClose = 0;
  bars.forEach((b, i) => {
    const close = (b.open + b.high + b.low + b.close) / 4;
    const open = i === 0 ? (b.open + b.close) / 2 : (prevOpen + prevClose) / 2;
    out.push({ ...b, open, close, high: Math.max(b.high, open, close), low: Math.min(b.low, open, close) });
    prevOpen = open;
    prevClose = close;
  });
  return out;
}

/** The level a Baseline chart splits at: the average close of the most recent `window` candles. */
export function baselineValue(closes: readonly number[], window = 100): number {
  const tail = closes.slice(-window);
  return tail.length ? tail.reduce((a, b) => a + b, 0) / tail.length : 0;
}

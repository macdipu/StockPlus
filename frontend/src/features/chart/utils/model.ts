import type { Time } from "lightweight-charts";
import type { ChartData, IndicatorSeries, Resolution } from "../schemas/chart";

/** Everything the canvas draws, as plain data. Built from the server's response; no chart library in here. */

export interface Candle {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface LinePoint {
  time: Time;
  value: number;
  /** Histogram columns are coloured per point (green above zero, red below). */
  color?: string;
}

export interface SeriesSpec {
  key: string;
  title: string;
  kind: "line" | "histogram" | "area" | "dots";
  color: string;
  points: LinePoint[];
}

export interface PaneSpec {
  key: string;
  title: string;
  series: SeriesSpec[];
  scale: readonly [number, number] | null;
  levels: readonly number[];
}

export interface PriceLineSpec {
  price: number;
  color: string;
  title: string;
  style: "solid" | "dashed" | "dotted";
  width?: 1 | 2;
}

export interface MarkerSpec {
  time: Time;
  position: "aboveBar" | "belowBar";
  shape: "arrowUp" | "arrowDown" | "circle";
  color: string;
  text: string;
}

export interface BandSpec {
  from: number;
  to: number;
  color: string;
}

/** What a host (for example the stock page) can add on top of the price: its own lines, markers and shaded bands. */
export interface Annotations {
  priceLines?: readonly PriceLineSpec[];
  markers?: readonly MarkerSpec[];
  bands?: readonly BandSpec[];
}

/** Today's live candle, merged into a daily chart. `day` is the exchange date, YYYY-MM-DD. */
export interface LiveBar {
  day: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const DHAKA_OFFSET_S = 6 * 3600;

/** Daily candles sit on their trading date; intraday candles are shifted so the axis reads Dhaka time. */
export function toChartTime(unix: number, resolution: Resolution): Time {
  return resolution === "D" ? (new Date(unix * 1000).toISOString().slice(0, 10) as Time) : ((unix + DHAKA_OFFSET_S) as Time);
}

// Distinct from the green/red that mean up/down. Mid-tones so they read on light and dark backgrounds.
export const PALETTE = ["#2f6fe4", "#d98a0b", "#8b5cf6", "#0ea5b7", "#e0529c", "#6b7f90", "#c2693a", "#3f8f6a", "#a855c7", "#b08900"] as const;

/** The colour of an indicator's first output; its other outputs step along the palette. */
export function paletteColor(indicatorIndex: number, outputIndex = 0): string {
  return PALETTE[(indicatorIndex * 3 + outputIndex) % PALETTE.length] as string;
}

const UP = "#35c387";
const DOWN = "#f0646c";

function seriesFor(ind: IndicatorSeries, index: number, times: readonly Time[], histogramColors: { up: string; down: string }): SeriesSpec[] {
  return ind.outputs.map((o, j) => {
    const values = ind.series[o.key] ?? [];
    const points: LinePoint[] = [];
    for (let i = 0; i < times.length; i++) {
      const v = values[i];
      if (v == null) continue;
      points.push(o.kind === "histogram" ? { time: times[i] as Time, value: v, color: v >= 0 ? histogramColors.up : histogramColors.down } : { time: times[i] as Time, value: v });
    }
    return { key: `${ind.key}.${o.key}`, title: ind.outputs.length > 1 ? `${ind.name} ${o.label}` : ind.name, kind: o.kind, color: paletteColor(index, j), points };
  });
}

/** Merge today's live candle into a daily chart: replace the last candle when it is the same day, else append. */
export function withLive(candles: Candle[], live: LiveBar | null | undefined): Candle[] {
  if (!live || !(live.volume > 0) || candles.length === 0) return candles;
  const last = candles[candles.length - 1] as Candle;
  const bar: Candle = { time: live.day as Time, open: live.open, high: live.high, low: live.low, close: live.close, volume: live.volume };
  if (last.time === live.day) return [...candles.slice(0, -1), bar];
  return String(live.day) > String(last.time) ? [...candles, bar] : candles;
}

export interface Layers {
  overlays: SeriesSpec[];
  panes: PaneSpec[];
  priceLines: PriceLineSpec[];
  markers: MarkerSpec[];
  bands: BandSpec[];
}

/** The candles, with today's live candle merged into a daily chart. This is what changes on every price tick. */
export function buildCandles(data: ChartData, resolution: Resolution, live?: LiveBar | null): Candle[] {
  const c = data.candles;
  const candles: Candle[] = c.time.map((t, i) => ({ time: toChartTime(t, resolution), open: c.open[i] as number, high: c.high[i] as number, low: c.low[i] as number, close: c.close[i] as number, volume: c.volume[i] as number }));
  return resolution === "D" ? withLive(candles, live) : candles;
}

export interface LayerInput {
  data: ChartData;
  resolution: Resolution;
  /** The requested specs in order: an indicator's colour comes from its position here, so chips and lines agree. */
  specs: readonly string[];
  annotations?: Annotations;
}

/** Indicator lines and panels plus the host's annotations. Changes only when the data or the choices change. */
export function buildLayers({ data, resolution, specs, annotations }: LayerInput): Layers {
  const times: Time[] = data.candles.time.map((t) => toChartTime(t, resolution));
  const overlays: SeriesSpec[] = [];
  const panes: PaneSpec[] = [];
  for (const ind of data.indicators) {
    const idx = Math.max(0, specs.indexOf(ind.key));
    const series = seriesFor(ind, idx, times, { up: UP + "aa", down: DOWN + "aa" });
    if (ind.placement === "overlay") overlays.push(...series.filter((s) => s.kind !== "histogram"));
    else panes.push({ key: ind.key, title: ind.name, series, scale: ind.scale, levels: ind.levels });
  }
  return { overlays, panes, priceLines: [...(annotations?.priceLines ?? [])], markers: [...(annotations?.markers ?? [])], bands: [...(annotations?.bands ?? [])] };
}

import { useMemo, useSyncExternalStore } from "react";
import { createLocalStore } from "@/shared/lib/local-store";

/** What the stock chart draws on top of the candles. Each layer is switched on its own. */
export const LAYERS = [
  { key: "levels", label: "Support and resistance", title: "The two nearest support and two nearest resistance levels" },
  { key: "plan", label: "Trade plan", title: "Buy zone, stop and targets, with the plan written beside the chart" },
  { key: "patterns", label: "Candle patterns", title: "Arrows on the latest candle patterns; names are listed under the chart" },
  { key: "shapes", label: "Chart patterns", title: "Possible double tops and bottoms, head and shoulders, triangles and channels, drawn on the chart (rule-based, not a signal)" },
  { key: "averages", label: "Moving averages", title: "SMA 20, 50 and 200 (EMA 9 and 21 on minute charts)" },
  { key: "bands", label: "Bollinger bands", title: "Bollinger bands (20, 2) on daily charts" },
  { key: "rsi", label: "RSI", title: "Relative Strength Index (14) in its own panel" },
  { key: "macd", label: "MACD", title: "MACD (12, 26, 9) in its own panel, daily charts" },
] as const;

export type Layer = (typeof LAYERS)[number]["key"];

/** Candles and volume only. */
export const CLEAN: readonly Layer[] = [];
/** Everything the analysis can draw. */
export const TRADER: readonly Layer[] = LAYERS.map((l) => l.key);
const DEFAULT: readonly Layer[] = ["levels"];

const store = createLocalStore<readonly Layer[]>("dse.stock.layers", DEFAULT);
const isLayer = (v: unknown): v is Layer => LAYERS.some((l) => l.key === v);

/** The chosen layers, remembered per browser. */
export function useLayers(): [ReadonlySet<Layer>, (next: readonly Layer[]) => void] {
  const raw = useSyncExternalStore(store.subscribe, store.get, store.getServer);
  const layers = useMemo(() => new Set<Layer>(Array.isArray(raw) ? raw.filter(isLayer) : DEFAULT), [raw]); // stable until the choice changes
  return [layers, store.set];
}

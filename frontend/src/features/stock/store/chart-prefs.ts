import { useSyncExternalStore } from "react";
import { createLocalStore } from "@/shared/lib/local-store";

/** off: prices and volume only. basic: moving averages, support/resistance, pattern labels. full: basic plus the
 * trade plan drawn on the chart (buy zone, stop, targets, watch levels), Bollinger bands, RSI and MACD. */
export type AnalysisLevel = "off" | "basic" | "full";
export const ANALYSIS_LEVELS: ReadonlyArray<{ key: AnalysisLevel; label: string; title: string }> = [
  { key: "off", label: "Off", title: "Prices and volume only" },
  { key: "basic", label: "Basic", title: "Moving averages, support and resistance lines, candle pattern labels" },
  { key: "full", label: "Full", title: "Basic plus the trade plan on the chart (buy zone, stop, targets, watch levels), Bollinger bands, RSI and MACD" },
];

const store = createLocalStore<AnalysisLevel>("dse.stock.analysis", "basic");
const isLevel = (v: unknown): v is AnalysisLevel => v === "off" || v === "basic" || v === "full";

/** How much analysis the stock chart draws, remembered per browser. */
export function useAnalysisLevel(): [AnalysisLevel, (level: AnalysisLevel) => void] {
  const raw = useSyncExternalStore(store.subscribe, store.get, store.getServer);
  return [isLevel(raw) ? raw : "basic", store.set];
}

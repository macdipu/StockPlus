import { useSyncExternalStore } from "react";
import { createLocalStore, type LocalStore } from "@/shared/lib/local-store";
import { isChartStyle, type ChartStyle } from "../utils/styles";

/**
 * Everything a user chooses about a chart, as plain JSON. It is remembered per browser today; the same shape can
 * be stored per account later (saved layouts and templates) without changing anything that reads it.
 */
export interface ChartSpec {
  style: ChartStyle;
  /** Indicators the user added, as canonical spec strings such as "rsi(14)" or "macd(12,26,9)". */
  indicators: string[];
}

export const DEFAULT_SPEC: ChartSpec = { style: "candles", indicators: [] };
const MAX_INDICATORS = 8;

function clean(raw: Partial<ChartSpec> | null | undefined): ChartSpec {
  const indicators = Array.isArray(raw?.indicators) ? raw.indicators.filter((s): s is string => typeof s === "string").slice(0, MAX_INDICATORS) : [];
  return { style: isChartStyle(raw?.style) ? raw.style : DEFAULT_SPEC.style, indicators: [...new Set(indicators)] };
}

const stores = new Map<string, LocalStore<ChartSpec>>();
function storeFor(scope: string): LocalStore<ChartSpec> {
  let s = stores.get(scope);
  if (!s) {
    s = createLocalStore<ChartSpec>(`dse.chart.spec.${scope}`, DEFAULT_SPEC);
    stores.set(scope, s);
  }
  return s;
}

/** `scope` separates charts that should not share choices (e.g. "stock" and "market"). */
export function useChartSpec(scope: string): [ChartSpec, (patch: Partial<ChartSpec>) => void] {
  const store = storeFor(scope);
  const raw = useSyncExternalStore(store.subscribe, store.get, store.getServer);
  const spec = clean(raw);
  return [spec, (patch) => store.set(clean({ ...spec, ...patch }))];
}

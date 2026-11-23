import { useMemo, useSyncExternalStore } from "react";
import { createLocalStore, type LocalStore } from "@/shared/lib/local-store";
import { parseDrawings, type Drawing } from "../utils/drawings";

const stores = new Map<string, LocalStore<unknown>>();
const storeFor = (key: string): LocalStore<unknown> => {
  let s = stores.get(key);
  if (!s) {
    s = createLocalStore<unknown>(`dse.chart.drawings.${key}`, []);
    stores.set(key, s);
  }
  return s;
};

/** The drawings for one chart (a symbol on one timeframe), remembered in this browser. */
export function useDrawings(key: string): [readonly Drawing[], (next: readonly Drawing[]) => void] {
  const store = storeFor(key);
  const raw = useSyncExternalStore(store.subscribe, store.get, store.getServer);
  const drawings = useMemo(() => parseDrawings(raw), [raw]);
  return [drawings, (next) => store.set(next)];
}

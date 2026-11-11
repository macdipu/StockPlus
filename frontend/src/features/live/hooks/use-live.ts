"use client";

import { useEffect, useSyncExternalStore } from "react";
import type { FeedStatus, Market, Quote } from "@/shared/api";
import { useLiveContext } from "../components/LiveProvider";
import type { ConnectionStatus, LiveState } from "../store/live-store";

function useLiveSelector<T>(select: (s: LiveState) => T): T {
  const { store } = useLiveContext();
  return useSyncExternalStore(
    store.subscribe,
    () => select(store.getState()),
    () => select(store.getServerState()),
  );
}

export const useQuote = (symbol: string | null | undefined): Quote | undefined =>
  useLiveSelector((s) => (symbol ? s.quotes[symbol.toUpperCase()] : undefined));
export const useConnection = (): ConnectionStatus => useLiveSelector((s) => s.connection);
export const useMarket = (): Market | null => useLiveSelector((s) => s.market);
export const useFeed = (): FeedStatus | null => useLiveSelector((s) => s.feed);
export const useLatencyMs = (): number | null => useLiveSelector((s) => s.latencyMs);

/** Keep these symbols on the live stream while the calling component is mounted. */
export function useLiveSymbols(symbols: readonly string[], opts: { primary?: boolean } = {}): void {
  const { registry } = useLiveContext();
  const key = symbols.join(",");
  const primary = opts.primary ?? false;
  useEffect(() => registry.register(key ? key.split(",") : [], primary), [registry, key, primary]);
}

/** Put prices from a REST call into the store (watchlist rows and the search box before any tick). */
export function useSeedQuotes(): (quotes: readonly Quote[]) => void {
  const { store } = useLiveContext();
  return store.seedQuotes.bind(store);
}

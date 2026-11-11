"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { buildUrl } from "@/shared/api";
import { SymbolRegistry } from "../hooks/symbol-registry";
import { heartbeatEvent, marketEvent, parseEvent, quoteEvent, snapshotEvent, universeEvent } from "../store/events";
import { LiveStore } from "../store/live-store";

interface LiveContextValue {
  store: LiveStore;
  registry: SymbolRegistry;
}

const LiveContext = createContext<LiveContextValue | null>(null);

export function useLiveContext(): LiveContextValue {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLive* must be used inside <LiveProvider>");
  return ctx;
}

const RECONNECT_DEBOUNCE_MS = 300;

export function LiveProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  // Created once per provider; useState's lazy initialiser is the render-safe way to hold a stable object.
  const [ctx] = useState<LiveContextValue>(() => ({ store: new LiveStore(), registry: new SymbolRegistry() }));
  const { store, registry } = ctx;

  useEffect(() => {
    let es: EventSource | null = null;
    let openedFor = "";
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const symbols = registry.symbols();
      const key = symbols.join(",");
      if (es && key === openedFor) return;
      es?.close();
      openedFor = key;
      store.setConnection(es ? "reconnecting" : "connecting");
      const source = new EventSource(buildUrl("/stream", { symbols: key || null }));
      es = source;
      source.onerror = () => store.setConnection(source.readyState === EventSource.CLOSED ? "offline" : "reconnecting");
      source.addEventListener("snapshot", (e) => {
        const s = parseEvent(snapshotEvent, (e as MessageEvent<string>).data);
        if (s) store.applySnapshot(s);
      });
      source.addEventListener("quote", (e) => {
        const q = parseEvent(quoteEvent, (e as MessageEvent<string>).data);
        if (q) store.applyQuote(q, q._meta.received_ms, Date.now());
      });
      source.addEventListener("market", (e) => {
        const m = parseEvent(marketEvent, (e as MessageEvent<string>).data);
        if (m) store.applyMarket(m);
      });
      source.addEventListener("heartbeat", (e) => {
        const h = parseEvent(heartbeatEvent, (e as MessageEvent<string>).data);
        if (h) store.applyFeed(h.feed);
      });
      source.addEventListener("universe", (e) => {
        if (parseEvent(universeEvent, (e as MessageEvent<string>).data)) {
          // The worker rebuilt the scanner universe: everything derived from it is stale.
          void queryClient.invalidateQueries({ queryKey: ["scanner"] });
          void queryClient.invalidateQueries({ queryKey: ["market"] });
        }
      });
    };

    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(connect, RECONNECT_DEBOUNCE_MS); // several components register at once on navigation
    };
    schedule();
    const off = registry.onChange(schedule);
    return () => {
      off();
      clearTimeout(timer);
      es?.close();
    };
  }, [registry, store, queryClient]);

  return <LiveContext.Provider value={ctx}>{children}</LiveContext.Provider>;
}

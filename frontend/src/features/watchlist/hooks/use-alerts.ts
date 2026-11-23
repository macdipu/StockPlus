"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { companyApi, type StockAlert } from "@/features/company";
import { createLocalStore } from "@/shared/lib/local-store";

const enabledStore = createLocalStore<boolean>("dse.alerts.enabled", false);
const SEEN_KEY = "dse.alerts.seen";
const POLL_MS = 120_000;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
function write(key: string, v: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* storage unavailable: notifications still work for this tab */
  }
}

export type NotifyState = "off" | "on" | "blocked" | "unsupported";

type Permission = NotificationPermission | "unsupported";
const noSubscription = () => () => {};
const readPermission = (): Permission => ("Notification" in window ? Notification.permission : "unsupported");
const serverPermission = (): Permission => "unsupported"; // the server cannot know; React re-reads in the browser after hydrating

/**
 * Watchlist notifications. When switched on (and the browser allows it), the watched symbols are checked every
 * two minutes; each new alert (buy zone with a bullish candle, stop broken, target hit, breakout, bearish candle)
 * shows one desktop notification. Alert keys include the session day, so an event notifies once per day.
 */
export function useWatchlistAlerts(symbols: readonly string[]) {
  const router = useRouter();
  const enabled = useSyncExternalStore(enabledStore.subscribe, enabledStore.get, enabledStore.getServer);
  const [, refresh] = useState(0); // the browser has no change event worth listening to; re-read after we ask
  const permission = useSyncExternalStore(noSubscription, readPermission, serverPermission);
  const state: NotifyState = permission === "unsupported" ? "unsupported" : permission === "denied" ? "blocked" : enabled && permission === "granted" ? "on" : "off";

  const enable = useCallback(async () => {
    if (!("Notification" in window)) return;
    const p = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
    enabledStore.set(p === "granted");
    refresh((n) => n + 1);
    if (p === "granted") {
      new Notification("Watchlist alerts are on", { body: "You will get a notice when a watched share enters its buy zone, breaks its stop or hits its target." });
    }
  }, []);
  const disable = useCallback(() => enabledStore.set(false), []);

  const q = useQuery({
    queryKey: ["alerts", [...symbols].sort()],
    queryFn: async () => (await companyApi.alerts(symbols)).data,
    enabled: symbols.length > 0,
    refetchInterval: POLL_MS,
    staleTime: POLL_MS / 2,
  });

  const notified = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (state !== "on" || !q.data) return;
    notified.current ??= new Set(read<string[]>(SEEN_KEY, []));
    const seen = notified.current;
    for (const a of q.data as StockAlert[]) {
      if (seen.has(a.key)) continue;
      seen.add(a.key);
      const n = new Notification(`${a.symbol} · ${a.severity === "warning" ? "Warning" : "Alert"}`, { body: a.message, tag: a.key });
      n.onclick = () => {
        window.focus();
        router.push(`/stock/${a.symbol}`);
      };
    }
    write(SEEN_KEY, [...seen].slice(-300));
  }, [q.data, state, router]);

  return { state, enable, disable, alerts: q.data ?? [], loading: q.isFetching };
}

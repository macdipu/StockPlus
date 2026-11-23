"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { universeApi } from "../services/universe-api";

export const universeKey = ["universe", "status"] as const;

/** What the scanners, picks and market tables are computed from, and when the worker last rebuilt it. */
export const useUniverseStatus = (refetchMs = 15_000) =>
  useQuery({
    queryKey: universeKey,
    queryFn: async () => (await universeApi.status()).data,
    staleTime: 5_000,
    refetchInterval: refetchMs,
  });

const WAIT_MS = 1_500;
const MAX_WAIT_TRIES = 20;

/** Ask the worker to pull fresh data from DSE and rebuild; resolve once a newer version is published, then
 * refetch every query so the page shows it. */
export function useRescan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const before = (await universeApi.status()).data.version;
      await universeApi.rescan();
      for (let i = 0; i < MAX_WAIT_TRIES; i++) {
        await new Promise((r) => setTimeout(r, WAIT_MS));
        const now = (await universeApi.status()).data;
        if (now.version !== before) return;
      }
    },
    onSettled: () => qc.invalidateQueries(),
  });
}

/** A clock that ticks, for "updated 12s ago" labels. */
export function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}

export function ago(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s ago`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m ago`;
}

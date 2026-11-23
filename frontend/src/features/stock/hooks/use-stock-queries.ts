"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { ApiError } from "@/shared/api";
import { stockApi } from "../services/stock-api";
import type { PeContext, RelativeStrength } from "../utils/summary";
import { indexCloses, relativeStrength } from "../utils/strength";

const key = (symbol: string, part: string, ...rest: unknown[]) => ["stock", symbol.toUpperCase(), part, ...rest] as const;

export const analysisKey = (symbol: string) => key(symbol, "analysis");

export const useAnalysis = (symbol: string) =>
  useQuery({
    queryKey: analysisKey(symbol),
    queryFn: async () => (await stockApi.analysis(symbol)).data,
    staleTime: 15_000,
    retry: (count, e) => count < 2 && !(e instanceof ApiError && e.status === 404), // an unknown symbol will not appear
  });

export const useTechnicals = (symbol: string) =>
  useQuery({ queryKey: key(symbol, "technicals"), queryFn: async () => (await stockApi.technicals(symbol)).data, staleTime: 60_000 });

export const useVpa = (symbol: string) =>
  useQuery({ queryKey: key(symbol, "vpa"), queryFn: () => stockApi.vpa(symbol), staleTime: 60_000 });

/** Minute bars grow while the market runs, so poll gently. */
export const useIntraday = (symbol: string) =>
  useQuery({
    queryKey: key(symbol, "intraday"),
    queryFn: () => stockApi.intraday(symbol),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

/** Full daily history (oldest first) for the price table and seasonality; it only changes after the close. */
export const useCandles = (symbol: string) =>
  useQuery({ queryKey: key(symbol, "candles"), queryFn: async () => (await stockApi.candles(symbol)).data, staleTime: 5 * 60_000 });

/** Code → company name for every instrument, so search works on names. Changes rarely. */
export const useNames = () =>
  useQuery({
    queryKey: ["stock", "directory"],
    queryFn: async () => new Map((await stockApi.directory()).data.flatMap((r) => (r.name ? [[r.symbol, r.name] as const] : []))),
    staleTime: 6 * 60 * 60_000,
  });

/** Possible chart patterns on the daily chart. They only change when a new bar closes. */
export const useChartPatterns = (symbol: string, enabled = true) =>
  useQuery({ queryKey: key(symbol, "chart-patterns"), queryFn: async () => (await stockApi.chartPatterns(symbol)).data, staleTime: 5 * 60_000, enabled });

/** The order book of one share. DSE refreshes it about every 10 s, so a gentle poll while the tab is open. */
export const useDepth = (symbol: string) =>
  useQuery({ queryKey: key(symbol, "depth"), queryFn: async () => (await stockApi.depth(symbol)).data, staleTime: 8_000, refetchInterval: 15_000 });

/** The market and sector P/E medians a share is compared with (shared across shares, so cached for a while). */
export function usePeContext(sector: string | null): PeContext | null {
  const q = useQuery({ queryKey: ["market", "pe-context"], queryFn: async () => (await stockApi.peContext()).data, staleTime: 30 * 60_000 });
  return useMemo(() => {
    if (!q.data) return null;
    const s = sector ? q.data.by_sector[sector] : undefined;
    return { marketMedian: q.data.market.median_pe, marketWeighted: q.data.market.weighted_pe, sector: sector && s ? { name: sector, companies: s.instruments, median: s.median_pe } : null };
  }, [q.data, sector]);
}

const SESSIONS_1M = 21;
const SESSIONS_3M = 63;

/** How the share has done against the DSEX index over the last month and three months. */
export function useRelativeStrength(symbol: string): RelativeStrength | null {
  const candles = useCandles(symbol).data;
  const index = useQuery({ queryKey: ["market", "dsex-closes"], queryFn: async () => (await stockApi.indexCloses()).data.candles, staleTime: 30 * 60_000 });
  return useMemo(() => {
    if (!candles || !index.data) return null;
    const idx = indexCloses(index.data.time, index.data.close);
    const stock = candles.map((c) => ({ day: c.day, close: c.close }));
    return { m1: relativeStrength(stock, idx, SESSIONS_1M), m3: relativeStrength(stock, idx, SESSIONS_3M) };
  }, [candles, index.data]);
}

/** What changed since the previous session. It moves with the price, so it refreshes with the analysis. */
export const useChanges = (symbol: string) =>
  useQuery({ queryKey: key(symbol, "changes"), queryFn: async () => (await stockApi.changes(symbol)).data, staleTime: 30_000, refetchInterval: 60_000 });

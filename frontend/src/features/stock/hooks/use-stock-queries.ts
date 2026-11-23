"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/shared/api";
import { stockApi } from "../services/stock-api";

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

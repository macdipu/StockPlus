"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Resolution } from "../schemas/chart";
import { chartApi } from "../services/chart-api";

/** How often each timeframe can have changed: a 1-minute chart every minute, a daily chart every ten. */
const REFRESH_MS: Record<Resolution, number> = { "1": 60_000, "5": 120_000, "30": 300_000, "60": 300_000, D: 600_000 };

/** Candles plus indicator series from the server. Changing the indicator list keeps the previous chart on screen. */
export const useChartData = (symbol: string, resolution: Resolution, indicators: readonly string[]) =>
  useQuery({
    queryKey: ["chart", symbol.toUpperCase(), resolution, [...indicators].sort().join(",")],
    queryFn: async ({ signal }) => (await chartApi.chart(symbol, resolution, indicators, resolution === "1" ? 2 : 1, signal)).data,
    staleTime: REFRESH_MS[resolution] / 2,
    refetchInterval: REFRESH_MS[resolution],
    placeholderData: keepPreviousData,
    retry: 1,
  });

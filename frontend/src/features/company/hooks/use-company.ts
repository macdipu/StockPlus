"use client";

import { useQuery } from "@tanstack/react-query";
import type { Resolution } from "../schemas/company";
import { companyApi } from "../services/company-api";

export const useCompany = (symbol: string) =>
  useQuery({
    queryKey: ["company", symbol.toUpperCase()],
    queryFn: async () => (await companyApi.company(symbol)).data,
    staleTime: 10 * 60_000,
    retry: 1,
  });

const REFRESH: Record<Resolution, number> = { "1": 60_000, "5": 120_000, "30": 300_000, "60": 300_000, D: 600_000 };

/** Intraday/daily candles for the chart's timeframe tabs; refreshed at the pace each resolution changes. */
export const useBars = (symbol: string, resolution: Resolution, enabled = true) =>
  useQuery({
    queryKey: ["bars", symbol.toUpperCase(), resolution],
    queryFn: async () => (await companyApi.bars(symbol, resolution, resolution === "1" ? 2 : 1)).data,
    staleTime: REFRESH[resolution] / 2,
    refetchInterval: REFRESH[resolution],
    enabled,
  });

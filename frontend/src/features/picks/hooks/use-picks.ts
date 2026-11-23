"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { PickFilters } from "../schemas/picks";
import { picksApi } from "../services/picks-api";

export const usePicks = (f: PickFilters) =>
  useQuery({
    queryKey: ["picks", f],
    queryFn: () => picksApi.picks(f),
    staleTime: 30_000,
    refetchInterval: 20_000,
    placeholderData: keepPreviousData,
  });

/** Manual rescan: ask the worker to rebuild, then refetch quickly until a newer universe version lands. */
export const useRescan = (currentVersion: number | undefined) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await picksApi.rescan();
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        await qc.invalidateQueries({ queryKey: ["picks"] });
        const hit = qc.getQueriesData<{ meta: { universe_version: number } }>({ queryKey: ["picks"] }).some(([, d]) => d && d.meta.universe_version !== currentVersion);
        if (hit) return;
      }
    },
  });
};

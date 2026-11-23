"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
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


/** The published back-test of the buckets. It changes only when a new run is published. */
export const useTrackRecord = () =>
  useQuery({ queryKey: ["picks", "track-record"], queryFn: async () => (await picksApi.trackRecord()).data, staleTime: 60 * 60_000 });

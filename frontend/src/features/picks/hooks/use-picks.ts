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


"use client";

import { useSyncExternalStore } from "react";
import { createLocalStore } from "@/shared/lib/local-store";
import type { PickFilters } from "../schemas/picks";

export const DEFAULT_FILTERS: PickFilters = { include: [], exclude: [], category: "", minValueMn: "", buckets: [] };
const store = createLocalStore<PickFilters>("dse.picks.filters", DEFAULT_FILTERS);

/** Filters survive a reload (per browser). */
export function useSavedFilters(): [PickFilters, (f: PickFilters) => void] {
  const f = useSyncExternalStore(store.subscribe, store.get, store.getServer);
  return [{ ...DEFAULT_FILTERS, ...f }, store.set];
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scannerApi, type PresetFilters } from "../services/scanner-api";
import type { ScanBody } from "../utils/rules";

// Every key starts with "scanner": the live stream's `universe` event invalidates that prefix, so scan results
// refresh the moment the worker publishes a new universe.
export const usePresets = () =>
  useQuery({ queryKey: ["scanner", "presets"], queryFn: async () => (await scannerApi.presets()).data, staleTime: Infinity });

export const useFields = () =>
  useQuery({ queryKey: ["scanner", "fields"], queryFn: async () => (await scannerApi.fields()).data, staleTime: Infinity });

export const usePresetScan = (key: string, filters: PresetFilters, enabled = true) =>
  useQuery({
    queryKey: ["scanner", "preset", key, filters],
    queryFn: () => scannerApi.runPreset(key, filters),
    enabled,
    placeholderData: (p) => p,
  });

/** `body` null = nothing submitted yet. Re-runs automatically when the universe changes. */
export const useCustomScan = (body: ScanBody | null) =>
  useQuery({
    queryKey: ["scanner", "custom", body],
    queryFn: () => scannerApi.runCustom(body as ScanBody),
    enabled: body !== null,
    placeholderData: (p) => p,
    retry: false, // a malformed scan is the user's to fix, not worth retrying
  });

const SAVED = ["me", "saved-scans"] as const;

export function useSavedScans(enabled: boolean) {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: SAVED, queryFn: async () => (await scannerApi.savedScans()).data, enabled });
  const save = useMutation({
    mutationFn: ({ name, body }: { name: string; body: ScanBody }) => scannerApi.saveScan(name, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: SAVED }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => scannerApi.deleteScan(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: SAVED }),
  });
  return { list, save, remove };
}

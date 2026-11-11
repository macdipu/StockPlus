"use client";

import { useQuery } from "@tanstack/react-query";
import { marketApi, type MoverKind } from "../services/market-api";

// All keys start with "market": the live stream's `universe` event invalidates that prefix.
export const useSectors = () => useQuery({ queryKey: ["market", "sectors"], queryFn: async () => (await marketApi.sectors()).data });
export const useMovers = (by: MoverKind) =>
  useQuery({ queryKey: ["market", "movers", by], queryFn: async () => (await marketApi.movers(by)).data, refetchInterval: 60_000 });
export const usePe = () => useQuery({ queryKey: ["market", "pe"], queryFn: async () => (await marketApi.pe()).data });
export const useRange52 = () => useQuery({ queryKey: ["market", "52w"], queryFn: async () => (await marketApi.range52()).data });

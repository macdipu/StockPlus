"use client";

import { useQuery } from "@tanstack/react-query";
import { indicatorsApi } from "../services/indicators-api";

/** The indicator catalog is static for the life of a deployment: fetched once, cached for an hour. */
export const useCatalog = () =>
  useQuery({ queryKey: ["indicators", "catalog"], queryFn: async () => (await indicatorsApi.catalog()).data, staleTime: 3_600_000, gcTime: 3_600_000 });

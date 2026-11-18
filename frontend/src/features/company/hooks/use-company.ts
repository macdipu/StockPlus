"use client";

import { useQuery } from "@tanstack/react-query";
import { companyApi } from "../services/company-api";

export const useCompany = (symbol: string) =>
  useQuery({
    queryKey: ["company", symbol.toUpperCase()],
    queryFn: async () => (await companyApi.company(symbol)).data,
    staleTime: 10 * 60_000,
    retry: 1,
  });

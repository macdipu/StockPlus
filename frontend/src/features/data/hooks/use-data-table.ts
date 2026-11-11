"use client";

import { useQuery } from "@tanstack/react-query";
import { dataApi, type DataTab } from "../services/data-api";

/** Keys start with "market" so the stream's `universe` event refreshes the table. */
export const useDataTable = (tab: DataTab, sector: string | null) =>
  useQuery({
    queryKey: ["market", tab === "matrix" ? "data-matrix" : "ta-values", sector],
    queryFn: async () => (await (tab === "matrix" ? dataApi.matrix(sector) : dataApi.ta(sector))).data,
    placeholderData: (p) => p,
  });

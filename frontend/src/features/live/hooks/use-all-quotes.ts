"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { envelope, quoteSchema, request } from "@/shared/api";
import { useSeedQuotes } from "./use-live";

/** Every instrument's latest quote: powers the symbol search and seeds the live store with prices. */
export function useAllQuotes() {
  const seed = useSeedQuotes();
  return useQuery({
    queryKey: ["quotes", "all"],
    queryFn: async () => {
      const { data } = await request("/quotes", { schema: envelope(z.array(quoteSchema)) });
      seed(data);
      return data;
    },
    staleTime: 60_000,
  });
}

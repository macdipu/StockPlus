"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "@/features/auth";
import { LiveProvider } from "@/features/live";
import { ApiError } from "@/shared/api";

function makeClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false, // the live stream keeps data fresh; focus refetches would just add load
        // Client errors (bad symbol, bad scan, no access) will not fix themselves.
        retry: (count, e) => count < 2 && !(e instanceof ApiError && e.status >= 400 && e.status < 500),
      },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeClient);
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>
        <LiveProvider>{children}</LiveProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

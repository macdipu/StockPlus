"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { ApiError } from "@/shared/api";
import { useAuth } from "@/features/auth";
import type { Watchlist } from "../schemas/watchlist";
import { watchlistApi } from "../services/watchlist-api";
import {
  clearGuestSymbols,
  getGuestSymbols,
  getServerGuestSymbols,
  guestListWasCustomised,
  setGuestSymbols,
  subscribeGuest,
} from "../store/guest-store";

export const DEFAULT_LIST_NAME = "Watchlist";
const KEY = ["me", "watchlists"] as const;

export interface WatchlistApi {
  mode: "guest" | "account";
  symbols: readonly string[];
  loading: boolean;
  error: string | null;
  has: (symbol: string) => boolean;
  add: (symbol: string) => void;
  remove: (symbol: string) => void;
}

/** The unknown codes the API named when it refused a list (so an import can drop just those). */
export function unknownSymbols(e: unknown): string[] {
  if (e instanceof ApiError && Array.isArray(e.extra.unknown)) {
    return e.extra.unknown.filter((s): s is string => typeof s === "string");
  }
  return [];
}

/** One interface over two stores: a localStorage list for visitors, the account's default list when signed in. */
export function useWatchlist(): WatchlistApi {
  const { state } = useAuth();
  const queryClient = useQueryClient();
  const signedIn = state.status === "authenticated";
  const guest = useSyncExternalStore(subscribeGuest, getGuestSymbols, getServerGuestSymbols);

  const lists = useQuery({ queryKey: KEY, queryFn: async () => (await watchlistApi.list()).data, enabled: signedIn });
  const main: Watchlist | undefined = lists.data?.find((w) => w.name === DEFAULT_LIST_NAME) ?? lists.data?.[0];

  const store = (w: Watchlist) =>
    queryClient.setQueryData<Watchlist[]>(KEY, (old = []) =>
      old.some((x) => x.id === w.id) ? old.map((x) => (x.id === w.id ? w : x)) : [...old, w],
    );

  const addM = useMutation({
    mutationFn: async (symbol: string) =>
      (main ? await watchlistApi.add(main.id, [symbol]) : await watchlistApi.create(DEFAULT_LIST_NAME, [symbol])).data,
    onSuccess: store,
  });
  const removeM = useMutation({
    mutationFn: async (symbol: string) => (main ? (await watchlistApi.remove(main.id, symbol)).data : undefined),
    onSuccess: (w) => w && store(w),
  });

  // First sign-in with a customised guest list and no account list yet: carry it over, once.
  const imported = useRef(false);
  useEffect(() => {
    if (!signedIn || !lists.isSuccess || lists.data.length > 0 || imported.current || !guestListWasCustomised()) return;
    imported.current = true;
    const symbols = [...getGuestSymbols()];
    void (async () => {
      try {
        store((await watchlistApi.create(DEFAULT_LIST_NAME, symbols)).data);
        clearGuestSymbols();
      } catch (e) {
        const bad = new Set(unknownSymbols(e));
        if (bad.size) {
          try {
            store((await watchlistApi.create(DEFAULT_LIST_NAME, symbols.filter((s) => !bad.has(s)))).data);
            clearGuestSymbols();
          } catch {
            /* keep the guest list; the user can add symbols by hand */
          }
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `store` only closes over the stable queryClient
  }, [signedIn, lists.isSuccess, lists.data]);

  if (!signedIn) {
    return {
      mode: "guest",
      symbols: guest,
      loading: state.status === "loading",
      error: null,
      has: (s) => guest.includes(s.toUpperCase()),
      add: (s) => setGuestSymbols([...new Set([...guest, s.toUpperCase()])]),
      remove: (s) => setGuestSymbols(guest.filter((x) => x !== s.toUpperCase())),
    };
  }
  const symbols = main?.symbols ?? [];
  const failure = addM.error ?? removeM.error ?? lists.error;
  return {
    mode: "account",
    symbols,
    loading: lists.isPending,
    error: failure instanceof Error ? failure.message : null,
    has: (s) => symbols.includes(s.toUpperCase()),
    add: (s) => addM.mutate(s.toUpperCase()),
    remove: (s) => removeM.mutate(s.toUpperCase()),
  };
}

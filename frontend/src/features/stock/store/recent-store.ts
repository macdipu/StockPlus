import { createLocalStore } from "@/shared/lib/local-store";

const MAX_RECENT = 8;
const store = createLocalStore<readonly string[]>("dse.recent-symbols", []);

export const subscribeRecent = store.subscribe;
export const getRecent = store.get;
export const getServerRecent = store.getServer;

/** Put a symbol at the front of the recently viewed list (newest first, no duplicates, capped). */
export function pushRecent(symbol: string): void {
  const code = symbol.toUpperCase();
  const current = store.get();
  if (current[0] === code) return;
  store.set([code, ...current.filter((s) => s !== code)].slice(0, MAX_RECENT));
}

export function clearRecent(): void {
  store.set([]);
}

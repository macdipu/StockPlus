import { useSyncExternalStore } from "react";

/**
 * Whether the browser can reach the API right now. Any answer from the server (even an error page) means yes; a network
 * failure or a request that timed out means no. The shell shows a banner while it is no, so a stuck page is explained.
 */
let offline = false;
const listeners = new Set<() => void>();

const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

function set(next: boolean): void {
  if (offline === next) return;
  offline = next;
  for (const fn of listeners) fn();
}

export const connection = {
  markOffline: () => set(true),
  markOnline: () => set(false),
  get: () => offline,
  subscribe,
};

export const useOffline = (): boolean => useSyncExternalStore(connection.subscribe, connection.get, () => false);

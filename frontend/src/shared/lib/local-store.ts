/**
 * A tiny localStorage-backed store for `useSyncExternalStore`. Snapshots are cached so React sees a stable
 * reference until the value really changes; the server snapshot is always the fallback (no hydration mismatch).
 * Storage can be unavailable (private mode, blocked site data): the value then lives in memory for the tab.
 */
export interface LocalStore<T> {
  subscribe: (listener: () => void) => () => void;
  get: () => T;
  getServer: () => T;
  set: (value: T) => void;
}

export function createLocalStore<T>(key: string, fallback: T): LocalStore<T> {
  const listeners = new Set<() => void>();
  let cached: { raw: string | null; value: T } | null = null;
  let memory: string | null = null;

  const readRaw = (): string | null => {
    try {
      return localStorage.getItem(key);
    } catch {
      return memory;
    }
  };
  const get = (): T => {
    const raw = readRaw();
    if (cached && cached.raw === raw) return cached.value;
    let value = fallback;
    try {
      value = raw == null ? fallback : (JSON.parse(raw) as T);
    } catch {
      value = fallback;
    }
    cached = { raw, value };
    return value;
  };
  const set = (value: T) => {
    const raw = JSON.stringify(value);
    memory = raw;
    try {
      localStorage.setItem(key, raw);
    } catch {
      /* in-memory only */
    }
    listeners.forEach((l) => l());
  };
  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    const onStorage = (e: StorageEvent) => {
      if (e.key === key) listener();
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(listener);
      window.removeEventListener("storage", onStorage);
    };
  };
  return { subscribe, get, getServer: () => fallback, set };
}

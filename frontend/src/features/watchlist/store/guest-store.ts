/**
 * The anonymous watchlist, kept in localStorage (as the legacy app did) and shared between components.
 * Every storage access is guarded: it can throw (private mode, blocked site data) and must never break a page.
 */

export const GUEST_KEY = "dse.guest.watchlist";
export const DEFAULT_GUEST_SYMBOLS: readonly string[] = ["GP", "BATBC", "SQURPHARMA", "BRACBANK", "ROBI"];

const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedValue: readonly string[] = DEFAULT_GUEST_SYMBOLS;

function readRaw(): string | null {
  try {
    return window.localStorage.getItem(GUEST_KEY);
  } catch {
    return null;
  }
}

const normalise = (symbols: readonly string[]): readonly string[] => [
  ...new Set(symbols.map((s) => s.trim().toUpperCase()).filter(Boolean)),
];

export function parseSymbols(raw: string | null): readonly string[] {
  if (raw == null) return DEFAULT_GUEST_SYMBOLS;
  try {
    const v: unknown = JSON.parse(raw);
    if (Array.isArray(v) && v.every((s) => typeof s === "string")) {
      return normalise(v as string[]);
    }
  } catch {
    // fall through to the default
  }
  return DEFAULT_GUEST_SYMBOLS;
}

/** A stable reference while the stored value is unchanged (required by useSyncExternalStore). */
export function getGuestSymbols(): readonly string[] {
  const raw = readRaw();
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedValue = parseSymbols(raw);
  }
  return cachedValue;
}

export const getServerGuestSymbols = (): readonly string[] => DEFAULT_GUEST_SYMBOLS;

/** True once the visitor has changed the list (so there is something worth importing at sign-in). */
export function guestListWasCustomised(): boolean {
  return readRaw() != null;
}

export function setGuestSymbols(input: readonly string[]): void {
  const symbols = normalise(input); // stored exactly as it will be read back
  try {
    window.localStorage.setItem(GUEST_KEY, JSON.stringify(symbols));
  } catch {
    // storage unavailable: keep working for this page view
    cachedRaw = undefined;
    cachedValue = symbols;
  }
  for (const l of listeners) l();
}

export function clearGuestSymbols(): void {
  try {
    window.localStorage.removeItem(GUEST_KEY);
  } catch {
    // ignore
  }
  cachedRaw = undefined;
  for (const l of listeners) l();
}

export function subscribeGuest(l: () => void): () => void {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => {
    if (e.key === GUEST_KEY) l(); // another tab changed it
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(l);
    window.removeEventListener("storage", onStorage);
  };
}

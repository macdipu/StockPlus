import type { FeedStatus, Market, Quote } from "@/shared/api";

export type ConnectionStatus = "connecting" | "live" | "reconnecting" | "offline";

export interface LiveState {
  connection: ConnectionStatus;
  quotes: Readonly<Record<string, Quote>>;
  market: Market | null;
  feed: FeedStatus | null;
  /** Browser clock minus the API's `received_ms` for the latest quote: tick → screen, in ms. */
  latencyMs: number | null;
}

export const initialState: LiveState = {
  connection: "connecting",
  quotes: {},
  market: null,
  feed: null,
  latencyMs: null,
};

type Listener = () => void;

/**
 * A minimal external store (for `useSyncExternalStore`). Quotes arrive every few seconds for hundreds of
 * symbols, and each component should re-render only for the symbol it shows, so state is replaced
 * immutably and selectors compare by reference.
 */
export class LiveStore {
  private state: LiveState = initialState;
  private listeners = new Set<Listener>();

  readonly getState = (): LiveState => this.state;
  readonly getServerState = (): LiveState => initialState;

  readonly subscribe = (l: Listener): (() => void) => {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  };

  private set(patch: Partial<LiveState>): void {
    this.state = { ...this.state, ...patch };
    for (const l of this.listeners) l();
  }

  setConnection(connection: ConnectionStatus): void {
    if (connection !== this.state.connection) this.set({ connection });
  }

  /** Full state on (re)connect. Quotes for symbols we did not ask for this time are kept. */
  applySnapshot(s: { market: Market | null; quotes: Record<string, Quote>; feed: FeedStatus }): void {
    this.set({
      connection: "live",
      market: s.market ?? this.state.market,
      quotes: { ...this.state.quotes, ...s.quotes },
      feed: s.feed,
    });
  }

  applyQuote(q: Quote, receivedMs: number, nowMs: number): void {
    this.set({ quotes: { ...this.state.quotes, [q.symbol]: q }, latencyMs: Math.max(0, nowMs - receivedMs) });
  }

  /** Seed quotes from a REST call (the search box and watchlist need prices before any tick). */
  seedQuotes(quotes: readonly Quote[]): void {
    const next = { ...this.state.quotes };
    for (const q of quotes) next[q.symbol] ??= q;
    this.set({ quotes: next });
  }

  applyMarket(market: Market): void {
    this.set({ market });
  }

  applyFeed(feed: FeedStatus): void {
    this.set({ feed });
  }
}

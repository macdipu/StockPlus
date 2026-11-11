import { describe, expect, it, vi } from "vitest";
import type { FeedStatus, Market, Quote } from "@/shared/api";
import { LiveStore } from "./live-store";

const q = (symbol: string, ltp: number): Quote => ({
  symbol, ltp, ycp: 1, open: 1, high: 1, low: 1, close: null, change: 0, percent: 0, volume: 1, value_mn: 1, trades: 1,
  category: null, board: null, sector: null, asset_type: "EQ", trade_time: null,
});
const feed = { ready: true } as FeedStatus;
const market = { trade_time: "t" } as Market;

describe("LiveStore", () => {
  it("replaces state immutably and notifies subscribers", () => {
    const s = new LiveStore();
    const listener = vi.fn();
    const off = s.subscribe(listener);
    const before = s.getState();
    s.applyQuote(q("GP", 10), 1000, 1040);
    expect(s.getState()).not.toBe(before);
    expect(before.quotes).toEqual({});
    expect(s.getState().quotes.GP?.ltp).toBe(10);
    expect(s.getState().latencyMs).toBe(40);
    expect(listener).toHaveBeenCalledTimes(1);
    off();
    s.applyQuote(q("GP", 11), 1, 2);
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("keeps an unchanged quote's object identity, so rows for other symbols do not re-render", () => {
    const s = new LiveStore();
    s.applyQuote(q("GP", 10), 0, 0);
    const gp = s.getState().quotes.GP;
    s.applyQuote(q("BATBC", 5), 0, 0);
    expect(s.getState().quotes.GP).toBe(gp);
  });

  it("never reports negative latency when the clocks disagree", () => {
    const s = new LiveStore();
    s.applyQuote(q("GP", 1), 5000, 4000);
    expect(s.getState().latencyMs).toBe(0);
  });

  it("a snapshot marks the stream live and merges quotes; a missing market keeps the old one", () => {
    const s = new LiveStore();
    s.applyMarket(market);
    s.applyQuote(q("OLD", 1), 0, 0);
    s.applySnapshot({ market: null, quotes: { GP: q("GP", 2) }, feed });
    const st = s.getState();
    expect(st.connection).toBe("live");
    expect(st.market).toBe(market);
    expect(Object.keys(st.quotes).sort()).toEqual(["GP", "OLD"]);
    expect(st.feed).toBe(feed);
  });

  it("seeding never overwrites a fresher streamed quote", () => {
    const s = new LiveStore();
    s.applyQuote(q("GP", 99), 0, 0);
    s.seedQuotes([q("GP", 1), q("ROBI", 3)]);
    expect(s.getState().quotes.GP?.ltp).toBe(99);
    expect(s.getState().quotes.ROBI?.ltp).toBe(3);
  });

  it("does not notify when the connection status is unchanged", () => {
    const s = new LiveStore();
    const l = vi.fn();
    s.subscribe(l);
    s.setConnection("connecting");
    expect(l).not.toHaveBeenCalled();
    s.setConnection("reconnecting");
    expect(l).toHaveBeenCalledTimes(1);
  });
});

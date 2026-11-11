import { describe, expect, it } from "vitest";
import { z } from "zod";
import { envelope, feedStatusSchema, marketSchema, quoteSchema } from "@/shared/api";
import feed from "@/shared/api/__fixtures__/feed-status.json";
import market from "@/shared/api/__fixtures__/market.json";
import quotes from "@/shared/api/__fixtures__/quotes.json";
import { heartbeatEvent, marketEvent, parseEvent, quoteEvent, snapshotEvent, universeEvent } from "./events";

describe("live schemas vs. real API responses", () => {
  it("quotes, market and feed status", () => {
    expect(envelope(z.array(quoteSchema)).safeParse(quotes).success).toBe(true);
    expect(envelope(marketSchema).safeParse(market).success).toBe(true);
    expect(envelope(feedStatusSchema).safeParse(feed).success).toBe(true);
  });

  it("parses each SSE event shape", () => {
    const q = quotes.data[0]!;
    const meta = { received_ms: 1, published_ms: 2 };
    expect(parseEvent(quoteEvent, JSON.stringify({ ...q, _meta: meta }))?.symbol).toBe(q.symbol);
    expect(parseEvent(marketEvent, JSON.stringify({ ...market.data, _meta: meta }))?.session.is_open).toBeTypeOf("boolean");
    expect(parseEvent(snapshotEvent, JSON.stringify({ market: market.data, quotes: { [q.symbol]: q }, feed: feed.data }))).not.toBeNull();
    expect(parseEvent(snapshotEvent, JSON.stringify({ market: null, quotes: {}, feed: feed.data }))).not.toBeNull(); // before the first poll
    expect(parseEvent(heartbeatEvent, JSON.stringify({ feed: feed.data, server_ms: 1, dropped: 0 }))).not.toBeNull();
    expect(parseEvent(universeEvent, '{"version":3,"rows":400,"build_ms":9}')).toEqual({ version: 3, rows: 400 });
  });

  it("drops malformed events instead of throwing", () => {
    for (const bad of ["not json", "{}", "null", '{"symbol":1}', ""]) expect(parseEvent(quoteEvent, bad)).toBeNull();
  });
});

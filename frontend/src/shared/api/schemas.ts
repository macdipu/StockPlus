import { z } from "zod";

/** Schemas for payloads several features share. They mirror the backend DTOs (snake_case) exactly. */

const n = z.number().nullable();

export const quoteSchema = z.object({
  symbol: z.string(),
  ltp: n,
  ycp: n,
  open: n,
  high: n,
  low: n,
  close: n,
  change: n,
  percent: n,
  volume: z.number(),
  value_mn: n,
  trades: n,
  category: z.string().nullable(),
  board: z.string().nullable(),
  sector: z.string().nullable(),
  asset_type: z.string().nullable(),
  trade_time: z.string().nullable(),
});
export type Quote = z.infer<typeof quoteSchema>;

export const sessionSchema = z.object({
  day: z.string().nullable(),
  is_open: z.boolean(),
  trading_day: z.boolean(),
  phase: z.string().nullable(),
  opening: z.string().nullable(),
  closing: z.string().nullable(),
});
export type Session = z.infer<typeof sessionSchema>;

export const marketSchema = z.object({
  session: sessionSchema,
  trade_time: z.string().nullable(),
  indices: z.array(z.object({ key: z.string(), value: n, change: n, percent: n })),
  totals: z.record(z.string(), z.unknown()),
  breadth: z.object({
    advanced: z.number().optional(),
    declined: z.number().optional(),
    unchanged: z.number().optional(),
    traded: z.number().optional(),
  }),
});
export type Market = z.infer<typeof marketSchema>;

export const feedStatusSchema = z.object({
  ready: z.boolean(),
  stale: z.boolean(),
  market_open: z.boolean().nullable(),
  trade_time: z.string().nullable(),
  symbols: z.number(),
  poll_interval_s: z.number().nullable(),
  last_poll_age_ms: z.number().nullable(),
  last_success_age_ms: z.number().nullable(),
  last_change_age_ms: z.number().nullable(),
  polls: z.number(),
  not_modified: z.number(),
  changes: z.number(),
  last_error: z.string().nullable(),
});
export type FeedStatus = z.infer<typeof feedStatusSchema>;

/** Timing the API adds to every pushed event. */
export const eventMetaSchema = z.object({ received_ms: z.number(), published_ms: z.number() });

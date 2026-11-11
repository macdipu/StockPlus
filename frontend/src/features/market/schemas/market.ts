import { z } from "zod";

const n = z.number().nullable();

export const sectorRowSchema = z.object({
  sector: z.string(),
  instruments: z.number(),
  advanced: z.number(),
  declined: z.number(),
  avg_change_pct: n,
  turnover_mn: n,
  median_pe: n,
  avg_rsi: n,
  ret_1m: n,
  turnover_share_pct: n,
});
export type SectorRow = z.infer<typeof sectorRowSchema>;

const peGroup = z.object({ instruments: z.number(), median_pe: n, weighted_pe: n });
export const peSummarySchema = z.object({
  market: peGroup,
  by_sector: z.record(z.string(), peGroup),
  by_category: z.record(z.string(), peGroup),
  note: z.string(),
});
export type PeSummary = z.infer<typeof peSummarySchema>;

export const rangeRowSchema = z.object({
  symbol: z.string(),
  sector: z.string().nullable(),
  ltp: n,
  low_52w: n,
  high_52w: n,
  range_position_pct: n,
  pct_from_52w_high: n,
  pct_from_52w_low: n,
});
export type RangeRow = z.infer<typeof rangeRowSchema>;

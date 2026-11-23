import { z } from "zod";
import { envelope } from "@/shared/api";

const stats = z.object({
  n: z.number(),
  mean_pct: z.number().optional(),
  median_pct: z.number().optional(),
  hit_rate_pct: z.number().optional(),
  excess_pct: z.number().optional(),
  beat_market_pct: z.number().optional(),
});
export type BucketStats = z.infer<typeof stats>;

const correlation = z.object({ days: z.number(), mean_ic: z.number().optional(), share_of_days_positive_pct: z.number().optional() });

export const trackRecordSchema = envelope(
  z
    .object({
      generated_at: z.string(),
      rows: z.number(),
      days: z.number(),
      shares: z.number(),
      from: z.string(),
      to: z.string(),
      horizons: z.array(z.number()),
      by_bucket: z.record(z.string(), z.record(z.string(), stats)),
      rank_correlation: z.record(z.string(), z.record(z.string(), correlation)),
      notes: z.array(z.string()),
    })
    .nullable(),
);

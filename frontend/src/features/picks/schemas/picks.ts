import { z } from "zod";
import { metaSchema } from "@/shared/api";

const n = z.number().nullable();

export const BUCKETS = ["buy_zone", "wait_pullback", "watch", "avoid"] as const;
export type Bucket = (typeof BUCKETS)[number];

export const pickSchema = z.object({
  symbol: z.string(),
  name: z.string().nullable(),
  sector: z.string().nullable(),
  category: z.string().nullable(),
  ltp: n,
  change_pct: n,
  pe: n,
  pb: n,
  dividend_yield_pct: n,
  rsi14: n,
  setup_score: n,
  patterns: z.array(z.string()).nullable(),
  vpa: z.string().nullable(),
  low_52w: n,
  high_52w: n,
  value_mn: n,
  pick_score: z.number(),
  value_score: z.number(),
  entry_score: z.number(),
  bucket: z.enum(BUCKETS),
  bucket_label: z.string(),
  reasons: z.array(z.string()),
  warnings: z.array(z.string()),
});
export type Pick = z.infer<typeof pickSchema>;

export const picksResponseSchema = z.object({
  data: z.array(pickSchema),
  meta: metaSchema.extend({
    count: z.number(),
    counts: z.record(z.string(), z.number()),
    sectors: z.array(z.string()),
    universe_version: z.number(),
    built_at_ms: z.number(),
    build_ms: z.number(),
    trade_time: z.string().nullable(),
    live: z.boolean(),
  }),
});

export interface PickFilters {
  include: string[];
  exclude: string[];
  category: string;
  minValueMn: string;
  buckets: Bucket[];
}

export const rescanSchema = z.object({ data: z.object({ accepted: z.boolean(), version: z.number().nullable() }), meta: metaSchema });

import { z } from "zod";
import { metaSchema } from "@/shared/api";

export const ruleSchema = z.object({
  field: z.string(),
  op: z.string(),
  value: z.unknown().optional(),
  field2: z.string().nullish(),
});
export type ApiRule = z.infer<typeof ruleSchema>;

export const presetSchema = z.object({
  key: z.string(),
  name: z.string(),
  group: z.string(),
  description: z.string(),
  premarket: z.boolean(),
  match: z.enum(["all", "any"]),
  rules: z.array(ruleSchema),
  sort_field: z.string(),
  sort_desc: z.boolean(),
});
export type Preset = z.infer<typeof presetSchema>;

export const fieldsSchema = z.object({
  fields: z.record(z.string(), z.string()),
  ops: z.array(z.string()),
  default_columns: z.array(z.string()),
});
export type Fields = z.infer<typeof fieldsSchema>;

export const scanRowSchema = z.record(z.string(), z.unknown());
export type ScanRow = z.infer<typeof scanRowSchema>;

export const scanResultSchema = z.object({
  data: z.array(scanRowSchema),
  meta: metaSchema.extend({
    matched: z.number(),
    scanned: z.number(),
    live: z.boolean(),
    universe_version: z.number(),
    trade_time: z.string().nullable(),
  }),
});
export type ScanResult = z.infer<typeof scanResultSchema>;

export const savedScanSchema = z.object({
  id: z.string(),
  name: z.string(),
  definition: z.record(z.string(), z.unknown()),
  created_at: z.string(),
  updated_at: z.string(),
});
export type SavedScan = z.infer<typeof savedScanSchema>;

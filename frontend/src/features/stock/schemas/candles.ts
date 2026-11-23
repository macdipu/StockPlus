import { z } from "zod";
import { envelope } from "@/shared/api";

export const dailyBarSchema = z.object({
  day: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  trades: z.number().nullable(),
});
export type DailyBar = z.infer<typeof dailyBarSchema>;

export const candlesSchema = envelope(z.array(dailyBarSchema));

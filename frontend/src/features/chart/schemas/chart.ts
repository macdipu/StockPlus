import { z } from "zod";

const n = z.number().nullable();

export const RESOLUTIONS = ["1", "5", "30", "60", "D"] as const;
export type Resolution = (typeof RESOLUTIONS)[number];
export const RESOLUTION_LABEL: Record<Resolution, string> = { "1": "1min", "5": "5min", "30": "30min", "60": "1h", D: "D" };

const output = z.object({ key: z.string(), label: z.string(), kind: z.enum(["line", "histogram", "area", "dots"]) });

export const indicatorSchema = z.object({
  key: z.string(),
  id: z.string(),
  name: z.string(),
  group: z.string(),
  placement: z.enum(["overlay", "pane"]),
  params: z.record(z.string(), z.number()),
  outputs: z.array(output),
  scale: z.tuple([z.number(), z.number()]).nullable(),
  levels: z.array(z.number()),
  repaints: z.boolean(),
  series: z.record(z.string(), z.array(n)),
});
export type IndicatorSeries = z.infer<typeof indicatorSchema>;

export const chartSchema = z.object({
  symbol: z.string(),
  resolution: z.string(),
  source: z.string(),
  ohlc: z.boolean(),
  candles: z.object({
    time: z.array(z.number()),
    open: z.array(z.number()),
    high: z.array(z.number()),
    low: z.array(z.number()),
    close: z.array(z.number()),
    volume: z.array(z.number()),
  }),
  indicators: z.array(indicatorSchema),
  warnings: z.array(z.string()),
  catalog_version: z.string(),
});
export type ChartData = z.infer<typeof chartSchema>;

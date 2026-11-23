import { z } from "zod";
import { envelope } from "@/shared/api";

const point = z.object({ day: z.string(), price: z.number(), label: z.string() });

export const chartPatternSchema = z.object({
  kind: z.string(),
  name: z.string(),
  direction: z.enum(["bullish", "bearish", "neutral"]),
  status: z.enum(["forming", "confirmed"]),
  confidence: z.number(),
  start: z.string(),
  end: z.string(),
  points: z.array(point),
  lines: z.array(z.object({ role: z.string(), a: point, b: point })),
  summary: z.string(),
});
export type ChartPattern = z.infer<typeof chartPatternSchema>;

export const chartPatternsSchema = envelope(z.array(chartPatternSchema));

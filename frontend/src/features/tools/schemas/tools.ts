import { z } from "zod";

const n = z.number().nullable();

export const returnSchema = z.object({
  symbol: z.string(),
  buy_date: z.string(),
  buy_price: z.number(),
  sell_date: z.string(),
  sell_price: z.number(),
  quantity: z.number(),
  fee_pct: z.number(),
  cost: z.number(),
  proceeds: z.number(),
  profit: z.number(),
  return_pct: z.number(),
  days: z.number(),
  annualised_pct: n,
  note: z.string(),
});
export type ReturnResult = z.infer<typeof returnSchema>;

export const correlationSchema = z.object({
  symbols: z.array(z.string()),
  days: z.number(),
  matrix: z.array(z.array(n)),
});
export type Correlation = z.infer<typeof correlationSchema>;

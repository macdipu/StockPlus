import { z } from "zod";
import { envelope } from "@/shared/api";

const level = z.object({ price: z.number(), quantity: z.number(), orders: z.number() });
const side = z.object({ levels: z.array(level), total_quantity: z.number(), total_orders: z.number(), average_price: z.number().nullable() });

export const depthSchema = envelope(
  z.object({
    symbol: z.string(),
    buyers: side,
    sellers: side,
    spread: z.number().nullable(),
    as_of: z.string().nullable(),
    fetched_at: z.string(),
    market_open: z.boolean().nullable(),
    stats: z.record(z.string(), z.union([z.number(), z.string()]).nullable()),
  }),
);
export type Depth = z.infer<typeof depthSchema>["data"];
export type DepthSide = Depth["buyers"];

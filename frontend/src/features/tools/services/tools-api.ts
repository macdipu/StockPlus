import { buildUrl, envelope, request } from "@/shared/api";
import { correlationSchema, returnSchema } from "../schemas/tools";

export interface ReturnParams {
  symbol: string;
  buyDate: string;
  sellDate: string;
  quantity: number;
  feePct: number;
}

export const toolsApi = {
  returnBetween: (p: ReturnParams) =>
    request("/tools/return", {
      query: { symbol: p.symbol.trim().toUpperCase(), buy_date: p.buyDate, sell_date: p.sellDate || null, quantity: p.quantity, fee_pct: p.feePct },
      schema: envelope(returnSchema),
    }),
  correlation: (symbols: readonly string[], days: number) =>
    request("/tools/correlation", { query: { symbols, days }, schema: envelope(correlationSchema) }),
  csvUrl: (symbol: string) => buildUrl(`/data/${encodeURIComponent(symbol.trim().toUpperCase())}.csv`),
};

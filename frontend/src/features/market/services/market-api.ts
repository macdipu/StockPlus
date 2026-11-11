import { z } from "zod";
import { envelope, quoteSchema, request } from "@/shared/api";
import { peSummarySchema, rangeRowSchema, sectorRowSchema } from "../schemas/market";

export type MoverKind = "gainers" | "losers" | "value" | "volume" | "trades";

export const marketApi = {
  sectors: () => request("/market/sectors", { schema: envelope(z.array(sectorRowSchema)) }),
  movers: (by: MoverKind, limit = 10) =>
    request("/market/movers", { query: { by, limit }, schema: envelope(z.array(quoteSchema)) }),
  pe: () => request("/market/pe", { schema: envelope(peSummarySchema) }),
  range52: (limit = 15, near: "high" | "low" = "high") =>
    request("/market/52-week", { query: { limit, near }, schema: envelope(z.array(rangeRowSchema)) }),
};

import { z } from "zod";
import { envelope, request } from "@/shared/api";
import { alertSchema, barSchema, companySchema, type Resolution } from "../schemas/company";

const sym = (s: string) => encodeURIComponent(s.toUpperCase());

export const companyApi = {
  company: (symbol: string) => request(`/stocks/${sym(symbol)}/company`, { schema: envelope(companySchema) }),
  bars: (symbol: string, resolution: Resolution, pages = 1) =>
    request(`/stocks/${sym(symbol)}/bars`, { query: { resolution, pages }, schema: envelope(z.array(barSchema)) }),
  alerts: (symbols: readonly string[]) =>
    request("/alerts", { query: { symbols: symbols.join(",") }, schema: envelope(z.array(alertSchema)) }),
};

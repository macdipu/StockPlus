import { z } from "zod";
import { envelope, request } from "@/shared/api";
import { alertSchema, companySchema } from "../schemas/company";

const sym = (s: string) => encodeURIComponent(s.toUpperCase());

export const companyApi = {
  company: (symbol: string) => request(`/stocks/${sym(symbol)}/company`, { schema: envelope(companySchema) }),
  alerts: (symbols: readonly string[]) =>
    request("/alerts", { query: { symbols: symbols.join(",") }, schema: envelope(z.array(alertSchema)) }),
};
